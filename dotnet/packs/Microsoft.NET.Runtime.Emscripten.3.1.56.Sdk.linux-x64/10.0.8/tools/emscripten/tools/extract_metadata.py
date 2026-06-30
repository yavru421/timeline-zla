# Copyright 2022 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import logging
from typing import List, Dict

from . import webassembly, utils
from .webassembly import OpCode, AtomicOpCode, MemoryOpCode
from .shared import exit_with_error
from .settings import settings


logger = logging.getLogger('extract_metadata')


def skip_function_header(module):
  num_local_decls = module.read_uleb()
  while num_local_decls:
    local_count = module.read_uleb()  # noqa
    local_type = module.read_type()  # noqa
    num_local_decls -= 1


def is_orig_main_wrapper(module, function):
  module.get_types()
  module.get_function_types()
  module.seek(function.offset)
  skip_function_header(module)
  end = function.offset + function.size
  while module.tell() != end:
    opcode = module.read_byte()
    try:
      opcode = OpCode(opcode)
    except ValueError:
      return False
    if opcode == OpCode.CALL:
      callee = module.read_uleb()
      callee_type = module.get_function_type(callee)
      if len(callee_type.params) != 0:
        return False
    elif opcode in (OpCode.LOCAL_GET, OpCode.LOCAL_SET):
      module.read_uleb()  # local index
    elif opcode in (OpCode.END, OpCode.RETURN):
      pass
    else:
      # Any other opcodes and we assume this not a simple wrapper
      return False

  assert opcode == OpCode.END
  return True


def get_const_expr_value(expr):
  assert len(expr) == 2
  assert expr[1][0] == OpCode.END
  opcode, immediates = expr[0]
  if opcode in (OpCode.I32_CONST, OpCode.I64_CONST):
    assert len(immediates) == 1
    return immediates[0]
  elif opcode in (OpCode.GLOBAL_GET,):
    return 0
  else:
    exit_with_error('unexpected opcode in const expr: ' + str(opcode))


def get_global_value(globl):
  return get_const_expr_value(globl.init)


def parse_function_for_memory_inits(module, func_index, offset_map):
  """Very limited function parser that uses `memory.init` instructions
  to derive segment offset.

  When segments are passive they don't have an offset but (at least with
  llvm-generated code) are loaded during the start function
  (`__wasm_init_memory`) using `memory.init` instructions.

  Here we parse the `__wasm_init_memory` function and make many assumptions
  about its layout.  For example, we assume the first argument to `memory.init`
  is either an `i32.const` or the result of an `i32.add`.
  """
  segments = module.get_segments()
  func = module.get_function(func_index)
  module.seek(func.offset)
  skip_function_header(module)
  end = func.offset + func.size
  const_values = []
  call_targets = []
  while module.tell() != end:
    opcode = OpCode(module.read_byte())
    if opcode in (OpCode.END, OpCode.NOP, OpCode.DROP, OpCode.I32_ADD, OpCode.I64_ADD):
      pass
    elif opcode in (OpCode.BLOCK,):
      module.read_type()
    elif opcode in (OpCode.I32_CONST, OpCode.I64_CONST):
      const_values.append(module.read_sleb())
    elif opcode in (OpCode.GLOBAL_SET, OpCode.BR, OpCode.GLOBAL_GET, OpCode.LOCAL_SET, OpCode.LOCAL_GET, OpCode.LOCAL_TEE):
      module.read_uleb()
    elif opcode == OpCode.CALL:
      call_targets.append(module.read_uleb())
    elif opcode == OpCode.MEMORY_PREFIX:
      opcode = MemoryOpCode(module.read_byte())
      if opcode == MemoryOpCode.MEMORY_INIT:
        segment_idx = module.read_uleb()
        segment = segments[segment_idx]
        offset = to_unsigned(const_values[-3])
        offset_map[segment] = offset
        memory = module.read_uleb()
        assert memory == 0
      elif opcode == MemoryOpCode.MEMORY_FILL:
        memory = module.read_uleb() # noqa
        assert memory == 0
      elif opcode == MemoryOpCode.MEMORY_DROP:
        segment = module.read_uleb() # noqa
      else:
        assert False, "unknown: %s" % opcode
    elif opcode == OpCode.ATOMIC_PREFIX:
      opcode = AtomicOpCode(module.read_byte())
      if opcode in (AtomicOpCode.ATOMIC_I32_RMW_CMPXCHG, AtomicOpCode.ATOMIC_I32_STORE,
                    AtomicOpCode.ATOMIC_NOTIFY, AtomicOpCode.ATOMIC_WAIT32,
                    AtomicOpCode.ATOMIC_WAIT64):
        module.read_uleb()
        module.read_uleb()
      else:
        assert False, "unknown: %s" % opcode
    elif opcode == OpCode.BR_TABLE:
      count = module.read_uleb()
      for _ in range(count):
        depth = module.read_uleb() # noqa
      default = module.read_uleb() # noqa
    else:
      assert False, "unknown: %s" % opcode

  # Recursion is safe here because the layout of the wasm-ld-generated
  # start function has a specific structure and has at most on level
  # of call stack depth.
  for t in call_targets:
    parse_function_for_memory_inits(module, t, offset_map)


@webassembly.memoize
def get_passive_segment_offsets(module):
  start_func_index = module.get_start()
  assert start_func_index is not None
  offset_map = {}
  parse_function_for_memory_inits(module, start_func_index, offset_map)
  return offset_map


def to_unsigned(val):
  if val < 0:
    return val & ((2 ** 32) - 1)
  else:
    return val


def find_segment_with_address(module, address):
  segments = module.get_segments()
  active = [s for s in segments if s.init]

  for seg in active:
    offset = to_unsigned(get_const_expr_value(seg.init))
    if offset is None:
      continue
    if address >= offset and address < offset + seg.size:
      return (seg, address - offset)

  passive = [s for s in segments if not s.init]
  if passive:
    offset_map = get_passive_segment_offsets(module)
    for seg, offset in offset_map.items():
      if address >= offset and address < offset + seg.size:
        return (seg, address - offset)

  raise AssertionError('unable to find segment for address: %s' % address)


def data_to_string(data):
  data = data.decode('utf8')
  # We have at least one test (test/utf8.cpp) that uses a double
  # backslash in the C++ source code, in order to represent a single backslash.
  # This is because these strings historically were written and read back via
  # JSON and a single slash is interpreted as an escape char there.
  # Technically this escaping is no longer needed and could be removed
  # but in order to maintain compatibility we strip out the double
  # slashes here.
  data = data.replace('\\\\', '\\')
  return data


def get_section_strings(module, export_map, section_name):
  start_name = f'__start_{section_name}'
  stop_name = f'__stop_{section_name}'
  if start_name not in export_map or stop_name not in export_map:
    logger.debug(f'no start/stop symbols found for section: {section_name}')
    return {}

  start = export_map[start_name]
  end = export_map[stop_name]
  start_global = module.get_global(start.index)
  end_global = module.get_global(end.index)
  start_addr = to_unsigned(get_global_value(start_global))
  end_addr = to_unsigned(get_global_value(end_global))

  seg = find_segment_with_address(module, start_addr)
  if not seg:
    exit_with_error(f'unable to find segment starting at __start_{section_name}: {start_addr}')
  seg, seg_offset = seg

  asm_strings = {}
  str_start = seg_offset
  data = module.read_at(seg.offset, seg.size)
  size = end_addr - start_addr
  end = seg_offset + size
  while str_start < end:
    str_end = data.find(b'\0', str_start)
    asm_strings[start_addr - seg_offset + str_start] = data_to_string(data[str_start:str_end])
    str_start = str_end + 1
  return asm_strings


def get_main_reads_params(module, export_map):
  if settings.STANDALONE_WASM:
    return True

  main = export_map.get('main') or export_map.get('__main_argc_argv')
  if not main or main.kind != webassembly.ExternType.FUNC:
    return False

  main_func = module.get_function(main.index)
  if is_orig_main_wrapper(module, main_func):
    # If main is simple wrapper function then we know that __original_main
    # doesn't read arguments.
    return False

  # By default assume params are read
  return True


def get_named_globals(module, exports):
  named_globals = {}
  internal_start_stop_symbols = set(['__start_em_asm', '__stop_em_asm',
                                     '__start_em_lib_deps', '__stop_em_lib_deps',
                                     '__em_lib_deps'])
  internal_prefixes = ('__em_js__', '__em_lib_deps')
  for export in exports:
    if export.kind == webassembly.ExternType.GLOBAL:
      if export.name in internal_start_stop_symbols or any(export.name.startswith(p) for p in internal_prefixes):
        continue
      g = module.get_global(export.index)
      named_globals[export.name] = str(get_global_value(g))
  return named_globals


def get_function_exports(module):
  rtn = {}
  for e in module.get_exports():
    if e.kind == webassembly.ExternType.FUNC:
      rtn[e.name] = module.get_function_type(e.index)
  return rtn


def update_metadata(filename, metadata):
  imports = []
  invoke_funcs = []
  with webassembly.Module(filename) as module:
    for i in module.get_imports():
      if i.kind == webassembly.ExternType.FUNC:
        if i.field.startswith('invoke_'):
          invoke_funcs.append(i.field)
        else:
          imports.append(i.field)
      elif i.kind in (webassembly.ExternType.GLOBAL, webassembly.ExternType.TAG):
        imports.append(i.field)

    metadata.function_exports = get_function_exports(module)
    metadata.all_exports = [utils.removeprefix(e.name, '__em_js__') for e in module.get_exports()]

  metadata.imports = imports
  metadata.invokeFuncs = invoke_funcs


def get_string_at(module, address):
  seg, offset = find_segment_with_address(module, address)
  data = module.read_at(seg.offset, seg.size)
  str_end = data.find(b'\0', offset)
  return data_to_string(data[offset:str_end])


class Metadata:
  imports: List[str]
  export: List[str]
  asmConsts: Dict[int, str]
  jsDeps: List[str]
  emJsFuncs: Dict[str, str]
  emJsFuncTypes: Dict[str, str]
  features: List[str]
  invokeFuncs: List[str]
  mainReadsParams: bool
  namedGlobals: List[str]

  def __init__(self):
    pass


def extract_metadata(filename):
  import_names = []
  invoke_funcs = []
  em_js_funcs = {}
  em_js_func_types = {}

  with webassembly.Module(filename) as module:
    exports = module.get_exports()
    imports = module.get_imports()

    export_map = {e.name: e for e in exports}
    for e in exports:
      if e.kind == webassembly.ExternType.GLOBAL and e.name.startswith('__em_js__'):
        name = utils.removeprefix(e.name, '__em_js__')
        globl = module.get_global(e.index)
        string_address = to_unsigned(get_global_value(globl))
        em_js_funcs[name] = get_string_at(module, string_address)

    for i in imports:
      if i.kind == webassembly.ExternType.FUNC:
        if i.field.startswith('invoke_'):
          invoke_funcs.append(i.field)
        else:
          if i.field in em_js_funcs:
            types = module.get_types()
            em_js_func_types[i.field] = types[i.type]
          import_names.append(i.field)
      elif i.kind in (webassembly.ExternType.GLOBAL, webassembly.ExternType.TAG):
        import_names.append(i.field)

    features = module.parse_features_section()
    features = ['--enable-' + f[1] for f in features if f[0] == '+']
    features = [f.replace('--enable-atomics', '--enable-threads') for f in features]
    features = [f.replace('--enable-simd128', '--enable-simd') for f in features]
    features = [f.replace('--enable-nontrapping-fptoint', '--enable-nontrapping-float-to-int') for f in features]

    # If main does not read its parameters, it will just be a stub that
    # calls __original_main (which has no parameters).
    metadata = Metadata()
    metadata.imports = import_names
    metadata.function_exports = get_function_exports(module)
    metadata.all_exports = [utils.removeprefix(e.name, '__em_js__') for e in exports]
    metadata.asmConsts = get_section_strings(module, export_map, 'em_asm')
    metadata.jsDeps = [d for d in get_section_strings(module, export_map, 'em_lib_deps').values() if d]
    metadata.emJsFuncs = em_js_funcs
    metadata.emJsFuncTypes = em_js_func_types
    metadata.features = features
    metadata.invokeFuncs = invoke_funcs
    metadata.mainReadsParams = get_main_reads_params(module, export_map)
    metadata.namedGlobals = get_named_globals(module, exports)

    # print("Metadata parsed: " + pprint.pformat(metadata))
    return metadata

# SIG # Begin Windows Authenticode signature block
# MIInOAYJKoZIhvcNAQcCoIInKTCCJyUCAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCAJHBS8d6EuL5Wm
# jkFJ7oEKOi/TDT5uJ9OojwtswlBzN6CCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
# yB5Nk4i7AAAAAAHIMA0GCSqGSIb3DQEBCwUAMFcxCzAJBgNVBAYTAlVTMR4wHAYD
# VQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xKDAmBgNVBAMTH01pY3Jvc29mdCBD
# b2RlIFNpZ25pbmcgUENBIDIwMjQwHhcNMjYwNDE2MTg1NzQxWhcNMjcwNDE1MTg1
# NzQxWjBjMQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UE
# BxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMQ0wCwYD
# VQQDEwQuTkVUMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwl+wA/w7
# EJQXqK9sWcPvkEKwAK9Q9+IB/8tDYCypoK8la2SL/98/HgGFFZu9W4DlOfVG8RIj
# AACgEmJzR8l+Mditl5DgZrsDF0YRLAkw/ktlh9tVgp5/eT+yWE7zKCTkk2/GCizi
# V9c8KgEMU2b1rR8d+tGOARU6Yttqd1A8UzQxIqT6SIm1IikHd0hZCFoxDe3RfBUe
# jdcQNihJjepT+emvqyFzEEWB1lxN/QBCwhPMIc8UNRL6I+p2YuH88iiSo6GbEiB3
# lDr2+piMBLCrWyD2l6p+wkpVjgLSJ3L9R/gC1ZTqqZ/FtAavGmGAEzhhTbUfJDUK
# C0Sxwd1IQqROtwIDAQABo4IBmzCCAZcwDgYDVR0PAQH/BAQDAgeAMB8GA1UdJQQY
# MBYGCisGAQQBgjdMCAEGCCsGAQUFBwMDMB0GA1UdDgQWBBTB24U/3lfQ13JsMqqm
# /2NXdP1x8jBFBgNVHREEPjA8pDowODEeMBwGA1UECxMVTWljcm9zb2Z0IENvcnBv
# cmF0aW9uMRYwFAYDVQQFEw00NjQyMjMrNTA3NTk2MB8GA1UdIwQYMBaAFH9ZP1Qh
# 2q1P7wXl5qPXLQaUEggxMGAGA1UdHwRZMFcwVaBToFGGT2h0dHA6Ly93d3cubWlj
# cm9zb2Z0LmNvbS9wa2lvcHMvY3JsL01pY3Jvc29mdCUyMENvZGUlMjBTaWduaW5n
# JTIwUENBJTIwMjAyNC5jcmwwbQYIKwYBBQUHAQEEYTBfMF0GCCsGAQUFBzAChlFo
# dHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01pY3Jvc29mdCUy
# MENvZGUlMjBTaWduaW5nJTIwUENBJTIwMjAyNC5jcnQwDAYDVR0TAQH/BAIwADAN
# BgkqhkiG9w0BAQsFAAOCAgEAo1MnRHqvdP9ICF05SJtG4m+iwBoiywJ35tvxpR7+
# ENVsGi8OQTcS2BYCbkI94U55iKqakK3dome3Iy8D+q0u5Z4nKbC8J3gT+qjYh/+2
# sfHNnXbIaOjGnzbZvjoMogUVuDSa9nvh/RZVG74W1p73cFPgeJ3bHSExhBa0iBOO
# gYfQUkIRO99MEGB6CxyPUBj7OCEGmB4rYN/n7Nl0Iavqz+zr/F5yWWe6gkh0PfkB
# bgb/nKqNTujO0JlbOvbUvUOWyrpFi4WD/bLKbuF31X4C7peiOspulH1WLm8eqpZe
# OYTpAX8FdFJfM0eapmG0KMrKdtwwc15CSrL7n/eI9K8CzwV3qhUdEnFz4IUJZWKu
# emb21Ac29/K8SyNPGOZ7mnJa+fPpsZAzxubfRm2j/oXXO+KoxMInb445GffAVm8X
# 7rc1PhQH0UftLGN2AVmimvC9DGfO8K6No5+iwBHG3/sOs4Xbpu91Q1GwlBKOF3MZ
# VmnmcsJPppg42pUjvmiWOsmQE1MnaeY1h5TFQpXaLKe1mohQiod35IcMCf4Zygj4
# mjXUnek64JOXo7KAN08llblR9yCUoJ92gdLMUAQf92+lP5TywDfEix4ACwfedSM7
# Bp14wu7WORELjS7sJxV+poO5Q73nxrPngBB+PBZFPcnHNUAlPW/QFfqCSTJ6aAJx
# rB0wgga9MIIEpaADAgECAhMzAAAAOTu2Nxm/Bh1nAAAAAAA5MA0GCSqGSIb3DQEB
# DAUAMIGIMQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UE
# BxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMTIwMAYD
# VQQDEylNaWNyb3NvZnQgUm9vdCBDZXJ0aWZpY2F0ZSBBdXRob3JpdHkgMjAxMTAe
# Fw0yNDA4MDgyMDU0MThaFw0zNjAzMjIyMjEzMDRaMFcxCzAJBgNVBAYTAlVTMR4w
# HAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xKDAmBgNVBAMTH01pY3Jvc29m
# dCBDb2RlIFNpZ25pbmcgUENBIDIwMjQwggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAw
# ggIKAoICAQDYAZwe4zjHqpUWBzWtuub+CGPXx/EyoXph3zyDXtYKS2ld3YYN9uFs
# B9Oi3B26Z7AbpAgzYra8qNHbUvxFuiP8hC/2y0mPISqW30LlrrAT6/ams2HA8Qlv
# 6p42+SbCNbPGzToN21QE70FS+LXH9N2k8nLM/EHgnTNJf8h0TmyfUKmszNa+lTxD
# ieyy/rhBG+98OkArobPPWtbr9c3qzmDJ7J3kUcAm6cltdSHIIFNHESgw6taY1Scy
# GyBevqIl120XjrIHiPM7tRckHytH1ZGsmvEplR0P7Tn9t5meFvZNEYttkFvad1IE
# guTlA5LSscXAphi+rVy3zhklhyCFeGK0yU0+jzbcuURKIxybmRwK5BfVZx0xEVqE
# 4wM3yN5D/uW+GpVHYYAGe7bTrtW1Z13x2qj2Jdqz7NtI4tNyzlVrIf62nYBNe3rO
# YS/repVdHlR61YbLLETlibs9jFzAre4sO5RTxvS1yho7JqJ59oKLRnRyLhIOSZyT
# CVZosXeS0ZZJoGEWSs4cUgsMqBiKtD4WgO2PlT3LeaQh5Io3CCA5tJ5ZCvtCsnqa
# JXKhptE/xmEETIRyZRjjplUKKd+sFFVGJJVMvvrw1nhIBKOLO4cTepiG39jEiEP4
# iHzGYCcQuvaLpDFFwqzgt0pBP8SJIKX5dtjDNYrZGd+ZzV5DKJVNZQIDAQABo4IB
# TjCCAUowDgYDVR0PAQH/BAQDAgGGMBAGCSsGAQQBgjcVAQQDAgEAMB0GA1UdDgQW
# BBR/WT9UIdqtT+8F5eaj1y0GlBIIMTAZBgkrBgEEAYI3FAIEDB4KAFMAdQBiAEMA
# QTAPBgNVHRMBAf8EBTADAQH/MB8GA1UdIwQYMBaAFHItOgIxkEO5FAVO4eqnxzHR
# I4k0MFoGA1UdHwRTMFEwT6BNoEuGSWh0dHA6Ly9jcmwubWljcm9zb2Z0LmNvbS9w
# a2kvY3JsL3Byb2R1Y3RzL01pY1Jvb0NlckF1dDIwMTFfMjAxMV8wM18yMi5jcmww
# XgYIKwYBBQUHAQEEUjBQME4GCCsGAQUFBzAChkJodHRwOi8vd3d3Lm1pY3Jvc29m
# dC5jb20vcGtpL2NlcnRzL01pY1Jvb0NlckF1dDIwMTFfMjAxMV8wM18yMi5jcnQw
# DQYJKoZIhvcNAQEMBQADggIBABSUHzgoT+6J5+nyyDCq0pTdVmCsAxYAHXcpjlDt
# xazPHewf1v4kOg8V7A5+w+VuMDMGHi8rLXBKn5I8+DVEUYGs8jLuckc0IeC6owOL
# UrU3CYdaKRMaO55+T7jwWJ27tPkx0rlR03tFU0z1YYpcv6Yhaw6N2sUPT+Avjpec
# nrftoE33pCAkucUvnGH0iL4J9CZLFQVTGFSOUBbv6oZy4bBBRFMxvH779IY4JDvp
# ZKVfbcuhpDeL3Z3e8mukOmkfct+GojNapsWsQYujlJ8jZen5Lrp/3YkxZ2Ay06aT
# pK/5oOVknwog1TDQsbY+MDyguTph5tQ0CLfzDaJG2x91BrBT9UG87C6HLkqiwrx9
# PSKN3wz05rHEfWO+RuKl+0U1/AHQT6NCOjhKI39/c7hWbdKjh5uuWFkBOvXGTNrn
# hNTAdOXTTYByvYExO8yryv34PAdqo1vPDE/1heVebr2RramvRUi9kWswKwPqwz7n
# +iRmM+B6YDGRweEurM1kimAb9FYrAs38YHlPnarl1vW3dGrmJTgefAz3DmCnXN0n
# veIPsS+KXBIWweeCToAJMGE7v/XS3h9qQ6niWQAAVQ1kUAml3zuS4MisCgi2F6Yo
# K2WAo1EgXK/lXvDxVjIVU0JdL+KvCfwFJkDeVuJ9dNXGNi+AOxk0BtYd9hxwL30B
# Elj9MYIZ5TCCGeECAQEwbjBXMQswCQYDVQQGEwJVUzEeMBwGA1UEChMVTWljcm9z
# b2Z0IENvcnBvcmF0aW9uMSgwJgYDVQQDEx9NaWNyb3NvZnQgQ29kZSBTaWduaW5n
# IFBDQSAyMDI0AhMzAAAByCQ6yB5Nk4i7AAAAAAHIMA0GCWCGSAFlAwQCAQUAoIGu
# MBkGCSqGSIb3DQEJAzEMBgorBgEEAYI3AgEEMBwGCisGAQQBgjcCAQsxDjAMBgor
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCAaen99fs3LgE5l4Bztv4h1b0q6aD9G
# yl/kbGD9RPJruzBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# ADlbo42SzZQHsFWTZliGr0uxV03CRowMfzYnnMyw9GS8/5F0jYjHyomi02WRwQI0
# uIKF3cSmMkzp0xh5qLrSPFFnR+dSCmc6mrtpXu+PVFyt6453WW1rnrxGdTciDLcD
# SN8tK3qPG/1hEmjM0fHkMLm7IbPQsiBFgNDXyCXOWVybrZUJkQi3zsxqg/n4AseX
# EvqonGkATLnGswzbgf2pobOr+BK7caERKa3aGb0l9rW3rqsRZ5uoJ0zM8rFANWu/
# RLgjyWZe7NUwiInAHJuLxI1ZkdLleeadTekWVHPBEbIvgZmtPCGzb1cqTohQ87eV
# CWxyWEufN4jm+oj9P16dM0mhgheXMIIXkwYKKwYBBAGCNwMDATGCF4Mwghd/Bgkq
# hkiG9w0BBwKgghdwMIIXbAIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQgn27IQOGLicN+ultphtkLjQCM6HwKgnvhoes+bquDHM0CBmnnsMEWrBgTMjAy
# NjA0MzAwMDUwNTEuNDM4WjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
# BgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1p
# Y3Jvc29mdCBDb3Jwb3JhdGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2Eg
# T3BlcmF0aW9uczEnMCUGA1UECxMeblNoaWVsZCBUU1MgRVNOOjg5MDAtMDVFMC1E
# OTQ3MSUwIwYDVQQDExxNaWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNloIIR7TCC
# ByAwggUIoAMCAQICEzMAAAIiQdL2qv/Itf8AAQAAAiIwDQYJKoZIhvcNAQELBQAw
# fDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1Jl
# ZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMd
# TWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwHhcNMjYwMjE5MTkzOTU2WhcN
# MjcwNTE3MTkzOTU2WjCByzELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2EgT3BlcmF0aW9uczEnMCUG
# A1UECxMeblNoaWVsZCBUU1MgRVNOOjg5MDAtMDVFMC1EOTQ3MSUwIwYDVQQDExxN
# aWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNlMIICIjANBgkqhkiG9w0BAQEFAAOC
# Ag8AMIICCgKCAgEAtbniibpCLlLAACaPwGOQ2Uah+24YL+wlhjZRHW0RqCE63ROl
# rJ+ezWjbtQU3YwWxXL+0X4sbXtMfh0b10qrA/lnkl/+v8vcBNDM/sUT0xiGNtCu2
# kA2uvDss1clHlAsqcmQv4Fv98rTv2Tp1PR9q4u+5CT/AAa6sstVMV/zrHhILx7I/
# MopFk9AEba41m1zBxc0jqOYUHH1JjFyqlls+vjdPlMp4RstZ/naFuFmYKR/GOVu4
# aUqJFo9TPy7uMIt6Og8/b1VrpHIFBRoywJeGGaToWoex7ogv2pVyJjEH/AtwPKv+
# v9YRaHiGQeFBpMsMQfzkkzkrC+vt/aQ6szOwoDqX+Fe/fZDfeMjPblySOU/0ogOT
# HSGSIRFtPm4fOUag4eWFt/6Gr+eET8cOTj5R+uEFeiiZJdBSBJTFaCzaPFFkUHDA
# 9e/ce1gEowui7GjWe8itKnBEiLC9cIkJnX0AcXKqxQqSEH55kBZDqfSMl1Fqs2vL
# Zqc/BOml4PW9XogE9z1U4KzpT4v4WGQnz8V/+oxrcj48tQosDpiWpqIZklP/wjgH
# p30U9hthzEVKQl9c7PgJg5nUDNV0Wm+GEgCywJQ8xgrICO+557iY6FwJYiZr+zX6
# 71gHAOSqglDlkOpEj7ea9vDHyl1iSaUl7RXkvzJA8ycv4iUVch3BcvwfjLcCAwEA
# AaOCAUkwggFFMB0GA1UdDgQWBBRZB8BqAyeWWxBIrvCrLYrrKmqM0DAfBgNVHSME
# GDAWgBSfpxVdAF5iXYP05dJlpxtTNRnpcjBfBgNVHR8EWDBWMFSgUqBQhk5odHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBUaW1l
# LVN0YW1wJTIwUENBJTIwMjAxMCgxKS5jcmwwbAYIKwYBBQUHAQEEYDBeMFwGCCsG
# AQUFBzAChlBodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01p
# Y3Jvc29mdCUyMFRpbWUtU3RhbXAlMjBQQ0ElMjAyMDEwKDEpLmNydDAMBgNVHRMB
# Af8EAjAAMBYGA1UdJQEB/wQMMAoGCCsGAQUFBwMIMA4GA1UdDwEB/wQEAwIHgDAN
# BgkqhkiG9w0BAQsFAAOCAgEAYgDPp6q6cBtvbcUl7+NqPgrE3tguG6GkXxY7vSWl
# pC0x8Ku6ZJzTjS95/lBt8fwdPNxCl4hWKwJrpewUxwhl1Ot/8UbGdsI92ZkdAOHf
# Z3/bGgiVZuI7j1RQWov6JLTjmB9o/tfszO9MKDeaJ4Af6b8u1/AH2OiQeFz72/NE
# M+32OXnXW58I84NbGYVDxW23MHlngAiDa86hSutpjHlypobbnzK2qKICXiV31mN8
# eP6W7m4BDU9/qV0+udtNwjxfZH3ShOxigCEWMt8ZAUw7xXfHbn4zqQp9/JyuqjJV
# bZwYw4VkBtDzNxP6MQbOVAayOqQWJJiB7W44nw6rh0/k4WlVe8R3OiJ6EnN2jc1+
# PSR1IEJrrw3TIy5G2F3gNP9auSMUoNlPsnGQTrwIt7nWTyoQOVczg43/7nLv7xbV
# 62HEZJhijd47o2it/8jGYtibuTRC9yElqK8Ke0Y3mYPiTCCtH6LLlY/mApua+uCx
# /w/UCQwI/l32WjXhXb/dCuQNEEURj/6aAfckyFYxF4/7ic6fC+A3eOLAKrqgzoh3
# ZC4MXyvJz6qQklj2fRvkQj5vOaPXAH8RDba0rjsHKcis8bEQmAi/jyuPvfKK4rfR
# FSfyy6Anhvoy5Y9Cmg+EMurGXuK1jK9W60C6LEwWTcBZ18TYyJwlgXdIu4rNck0v
# +KkwggdxMIIFWaADAgECAhMzAAAAFcXna54Cm0mZAAAAAAAVMA0GCSqGSIb3DQEB
# CwUAMIGIMQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UE
# BxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMTIwMAYD
# VQQDEylNaWNyb3NvZnQgUm9vdCBDZXJ0aWZpY2F0ZSBBdXRob3JpdHkgMjAxMDAe
# Fw0yMTA5MzAxODIyMjVaFw0zMDA5MzAxODMyMjVaMHwxCzAJBgNVBAYTAlVTMRMw
# EQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVN
# aWNyb3NvZnQgQ29ycG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0
# YW1wIFBDQSAyMDEwMIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA5OGm
# TOe0ciELeaLL1yR5vQ7VgtP97pwHB9KpbE51yMo1V/YBf2xK4OK9uT4XYDP/XE/H
# ZveVU3Fa4n5KWv64NmeFRiMMtY0Tz3cywBAY6GB9alKDRLemjkZrBxTzxXb1hlDc
# wUTIcVxRMTegCjhuje3XD9gmU3w5YQJ6xKr9cmmvHaus9ja+NSZk2pg7uhp7M62A
# W36MEBydUv626GIl3GoPz130/o5Tz9bshVZN7928jaTjkY+yOSxRnOlwaQ3KNi1w
# jjHINSi947SHJMPgyY9+tVSP3PoFVZhtaDuaRr3tpK56KTesy+uDRedGbsoy1cCG
# MFxPLOJiss254o2I5JasAUq7vnGpF1tnYN74kpEeHT39IM9zfUGaRnXNxF803RKJ
# 1v2lIH1+/NmeRd+2ci/bfV+AutuqfjbsNkz2K26oElHovwUDo9Fzpk03dJQcNIIP
# 8BDyt0cY7afomXw/TNuvXsLz1dhzPUNOwTM5TI4CvEJoLhDqhFFG4tG9ahhaYQFz
# ymeiXtcodgLiMxhy16cg8ML6EgrXY28MyTZki1ugpoMhXV8wdJGUlNi5UPkLiWHz
# NgY1GIRH29wb0f2y1BzFa/ZcUlFdEtsluq9QBXpsxREdcu+N+VLEhReTwDwV2xo3
# xwgVGD94q0W29R6HXtqPnhZyacaue7e3PmriLq0CAwEAAaOCAd0wggHZMBIGCSsG
# AQQBgjcVAQQFAgMBAAEwIwYJKwYBBAGCNxUCBBYEFCqnUv5kxJq+gpE8RjUpzxD/
# LwTuMB0GA1UdDgQWBBSfpxVdAF5iXYP05dJlpxtTNRnpcjBcBgNVHSAEVTBTMFEG
# DCsGAQQBgjdMg30BATBBMD8GCCsGAQUFBwIBFjNodHRwOi8vd3d3Lm1pY3Jvc29m
# dC5jb20vcGtpb3BzL0RvY3MvUmVwb3NpdG9yeS5odG0wEwYDVR0lBAwwCgYIKwYB
# BQUHAwgwGQYJKwYBBAGCNxQCBAweCgBTAHUAYgBDAEEwCwYDVR0PBAQDAgGGMA8G
# A1UdEwEB/wQFMAMBAf8wHwYDVR0jBBgwFoAU1fZWy4/oolxiaNE9lJBb186aGMQw
# VgYDVR0fBE8wTTBLoEmgR4ZFaHR0cDovL2NybC5taWNyb3NvZnQuY29tL3BraS9j
# cmwvcHJvZHVjdHMvTWljUm9vQ2VyQXV0XzIwMTAtMDYtMjMuY3JsMFoGCCsGAQUF
# BwEBBE4wTDBKBggrBgEFBQcwAoY+aHR0cDovL3d3dy5taWNyb3NvZnQuY29tL3Br
# aS9jZXJ0cy9NaWNSb29DZXJBdXRfMjAxMC0wNi0yMy5jcnQwDQYJKoZIhvcNAQEL
# BQADggIBAJ1VffwqreEsH2cBMSRb4Z5yS/ypb+pcFLY+TkdkeLEGk5c9MTO1OdfC
# cTY/2mRsfNB1OW27DzHkwo/7bNGhlBgi7ulmZzpTTd2YurYeeNg2LpypglYAA7AF
# vonoaeC6Ce5732pvvinLbtg/SHUB2RjebYIM9W0jVOR4U3UkV7ndn/OOPcbzaN9l
# 9qRWqveVtihVJ9AkvUCgvxm2EhIRXT0n4ECWOKz3+SmJw7wXsFSFQrP8DJ6LGYnn
# 8AtqgcKBGUIZUnWKNsIdw2FzLixre24/LAl4FOmRsqlb30mjdAy87JGA0j3mSj5m
# O0+7hvoyGtmW9I/2kQH2zsZ0/fZMcm8Qq3UwxTSwethQ/gpY3UA8x1RtnWN0SCyx
# TkctwRQEcb9k+SS+c23Kjgm9swFXSVRk2XPXfx5bRAGOWhmRaw2fpCjcZxkoJLo4
# S5pu+yFUa2pFEUep8beuyOiJXk+d0tBMdrVXVAmxaQFEfnyhYWxz/gq77EFmPWn9
# y8FBSX5+k77L+DvktxW/tM4+pTFRhLy/AsGConsXHRWJjXD+57XQKBqJC4822rpM
# +Zv/Cuk0+CQ1ZyvgDbjmjJnW4SLq8CdCPSWU5nR0W2rRnj7tfqAxM328y+l7vzhw
# RNGQ8cirOoo6CGJ/2XBjU02N7oJtpQUQwXEGahC0HVUzWLOhcGbyoYIDUDCCAjgC
# AQEwgfmhgdGkgc4wgcsxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5ndG9u
# MRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRp
# b24xJTAjBgNVBAsTHE1pY3Jvc29mdCBBbWVyaWNhIE9wZXJhdGlvbnMxJzAlBgNV
# BAsTHm5TaGllbGQgVFNTIEVTTjo4OTAwLTA1RTAtRDk0NzElMCMGA1UEAxMcTWlj
# cm9zb2Z0IFRpbWUtU3RhbXAgU2VydmljZaIjCgEBMAcGBSsOAwIaAxUAu8nF1Wcd
# 27A6SZK+1bnIKZLKM7iggYMwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDANBgkqhkiG9w0BAQsFAAIFAO2cue4wIhgPMjAyNjA0MjkxNzEwMDZaGA8y
# MDI2MDQzMDE3MTAwNlowdzA9BgorBgEEAYRZCgQBMS8wLTAKAgUA7Zy57gIBADAK
# AgEAAgIKDgIB/zAHAgEAAgITMzAKAgUA7Z4LbgIBADA2BgorBgEEAYRZCgQCMSgw
# JjAMBgorBgEEAYRZCgMCoAowCAIBAAIDB6EgoQowCAIBAAIDAYagMA0GCSqGSIb3
# DQEBCwUAA4IBAQBKD0+nZAzvWuG+7JZoN7RHr+UNFmSNWDD8XDcrpraoQWO0RqCm
# QkzAo2G012ZP32bydjcb54aZkwNivpMj6ldt3115IaLIq3Byhtxk+p6xU46sYLfL
# ThRpHi9kQFm0cKAziTckQMWdxLoiUQMbKbY3LODp8V+jYXv8gyG8k1TZjdrocTzn
# KNrMuDwaDG/A/3PoFQgTODnj9KGZvCRonw4y+6zqm79vZU+s2IbJ5WoLnCL4BXOO
# mlc1zVl4vVCGdTzSErjTVyM+wKYOOHYeI9alR7uLpGaye6sN+xZa7EolklWfWx13
# G6ekXPTr7IiIG1Vr5tQwYliJxIiEExe2XsKbMYIEDTCCBAkCAQEwgZMwfDELMAkG
# A1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQx
# HjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMdTWljcm9z
# b2Z0IFRpbWUtU3RhbXAgUENBIDIwMTACEzMAAAIiQdL2qv/Itf8AAQAAAiIwDQYJ
# YIZIAWUDBAIBBQCgggFKMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRABBDAvBgkq
# hkiG9w0BCQQxIgQgRePj5KAzYWFHrxFN4hiVsSwDIWE91b6muFN1qE1Q1/4wgfoG
# CyqGSIb3DQEJEAIvMYHqMIHnMIHkMIG9BCAFYF0BCgTnxoIzbJJgzpm3BCDpxxjc
# APkHEbnw0eQJEzCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNo
# aW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29y
# cG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEw
# AhMzAAACIkHS9qr/yLX/AAEAAAIiMCIEICwplrYVXqIGU7/zXAGFWvFEGfGW8CPG
# cWlyWnCNC3xdMA0GCSqGSIb3DQEBCwUABIICAJoSPD/N8iVorvEV0lBftqEtI/16
# b2ORIuOPISAUraJAMIb+CzEvordXgN8rfsyKaySXFFDnoifMCRrXEExZVSz+VE/y
# 0ri/skqh1BCgYKaxzmxiZ90xzRYlNWME+c4SM5JoYsYKUkVOZcokcrS6vrOkYBuB
# +cyWz4E0y0o+zTerfxYuvxyvfPh6nLy+XQ4dYNo9wEzAZ21BS5TLDzzd6k93hy7S
# vD5RgjmKkJMEtDqN7E1Qagp4cvQlfsjJmecV7TilmuGZyfJwCX/EVvXc3nuY6QkI
# 9LDlvJyZ3ipqtJSlo+N572vXe2eUr8opuwHv9qH660iZaHpXm3tcU9jGqo1itEsI
# JFMVvtNcLuCTQl0gvLjb25cQ1waRN//IMaemXPGysx+aqjJNQgNEWuJQiig5ZIu+
# g117EbH9LtlAJHjr0FJ+K6uwEQ6XrQTpSnLs9qOAKZ43Tuyu7e0nTI9sRNHYolfr
# Lqa2nxqBsAy51rWdLD6BDgWfaD85GOwRvmm9hLbtqvJvmDM91HsMwgSEjPcWxzmv
# /ZzUjpfdPGRJN4PM3CH5UlLVJ4oxtnWWlESeCuomllVYG8yeWoNMyP9oLXJhPUlU
# eoSDpfF2yGDGiNbN7HhExi6ef90iUjgyuqp3OVuAT84miLR9jUGMv+3Gjmb7nvtC
# vXBLcOOxBhY5lq7U
# SIG # End Windows Authenticode signature block