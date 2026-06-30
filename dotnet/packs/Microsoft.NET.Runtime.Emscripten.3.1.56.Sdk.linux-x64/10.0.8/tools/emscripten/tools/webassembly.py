# Copyright 2011 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

"""Utilties for manipulating WebAssembly binaries from python.
"""

from collections import namedtuple
from enum import IntEnum
from functools import wraps
import logging
import os
import sys

from . import utils

sys.path.append(utils.path_from_root('third_party'))

import leb128

logger = logging.getLogger('webassembly')

WASM_PAGE_SIZE = 65536

MAGIC = b'\0asm'

VERSION = b'\x01\0\0\0'

HEADER_SIZE = 8

LIMITS_HAS_MAX = 0x1

SEG_PASSIVE = 0x1

PREFIX_MATH = 0xfc
PREFIX_THREADS = 0xfe
PREFIX_SIMD = 0xfd

SYMBOL_BINDING_MASK = 0x3
SYMBOL_BINDING_GLOBAL = 0x0
SYMBOL_BINDING_WEAK = 0x1
SYMBOL_BINDING_LOCAL = 0x2


def to_leb(num):
  return leb128.u.encode(num)


def read_uleb(iobuf):
  return leb128.u.decode_reader(iobuf)[0]


def read_sleb(iobuf):
  return leb128.i.decode_reader(iobuf)[0]


def memoize(method):

  @wraps(method)
  def wrapper(self, *args, **kwargs):
    assert not kwargs
    key = (method.__name__, args)
    if key not in self._cache:
      self._cache[key] = method(self, *args, **kwargs)
    return self._cache[key]

  return wrapper


def once(method):

  @wraps(method)
  def helper(self, *args, **kwargs):
    key = method
    if key not in self._cache:
      self._cache[key] = method(self, *args, **kwargs)

  return helper


class Type(IntEnum):
  I32 = 0x7f # -0x1
  I64 = 0x7e # -0x2
  F32 = 0x7d # -0x3
  F64 = 0x7c # -0x4
  V128 = 0x7b # -0x5
  FUNCREF = 0x70 # -0x10
  EXTERNREF = 0x6f # -0x11
  VOID = 0x40 # -0x40


class OpCode(IntEnum):
  NOP = 0x01
  BLOCK = 0x02
  END = 0x0b
  BR = 0x0c
  BR_TABLE = 0x0e
  CALL = 0x10
  DROP = 0x1a
  LOCAL_GET = 0x20
  LOCAL_SET = 0x21
  LOCAL_TEE = 0x22
  GLOBAL_GET = 0x23
  GLOBAL_SET = 0x24
  RETURN = 0x0f
  I32_CONST = 0x41
  I64_CONST = 0x42
  F32_CONST = 0x43
  F64_CONST = 0x44
  I32_ADD = 0x6a
  I64_ADD = 0x7c
  REF_NULL = 0xd0
  ATOMIC_PREFIX = 0xfe
  MEMORY_PREFIX = 0xfc


class MemoryOpCode(IntEnum):
  MEMORY_INIT = 0x08
  MEMORY_DROP = 0x09
  MEMORY_COPY = 0x0a
  MEMORY_FILL = 0x0b


class AtomicOpCode(IntEnum):
  ATOMIC_NOTIFY = 0x00
  ATOMIC_WAIT32 = 0x01
  ATOMIC_WAIT64 = 0x02
  ATOMIC_I32_STORE = 0x17
  ATOMIC_I32_RMW_CMPXCHG = 0x48


class SecType(IntEnum):
  CUSTOM = 0
  TYPE = 1
  IMPORT = 2
  FUNCTION = 3
  TABLE = 4
  MEMORY = 5
  TAG = 13
  GLOBAL = 6
  EXPORT = 7
  START = 8
  ELEM = 9
  DATACOUNT = 12
  CODE = 10
  DATA = 11


class ExternType(IntEnum):
  FUNC = 0
  TABLE = 1
  MEMORY = 2
  GLOBAL = 3
  TAG = 4


class DylinkType(IntEnum):
  MEM_INFO = 1
  NEEDED = 2
  EXPORT_INFO = 3
  IMPORT_INFO = 4


class InvalidWasmError(BaseException):
  pass


Section = namedtuple('Section', ['type', 'size', 'offset', 'name'])
Limits = namedtuple('Limits', ['flags', 'initial', 'maximum'])
Import = namedtuple('Import', ['kind', 'module', 'field', 'type'])
Export = namedtuple('Export', ['name', 'kind', 'index'])
Global = namedtuple('Global', ['type', 'mutable', 'init'])
Dylink = namedtuple('Dylink', ['mem_size', 'mem_align', 'table_size', 'table_align', 'needed', 'export_info', 'import_info'])
Table = namedtuple('Table', ['elem_type', 'limits'])
FunctionBody = namedtuple('FunctionBody', ['offset', 'size'])
DataSegment = namedtuple('DataSegment', ['flags', 'init', 'offset', 'size'])
FuncType = namedtuple('FuncType', ['params', 'returns'])


class Module:
  """Extremely minimal wasm module reader.  Currently only used
  for parsing the dylink section."""
  def __init__(self, filename):
    self.buf = None # Set this before FS calls below in case they throw.
    self.filename = filename
    self.size = os.path.getsize(filename)
    self.buf = open(filename, 'rb')
    magic = self.buf.read(4)
    version = self.buf.read(4)
    if magic != MAGIC or version != VERSION:
      raise InvalidWasmError(f'{filename} is not a valid wasm file')
    self._cache = {}

  def __del__(self):
    assert not self.buf, '`__exit__` should have already been called, please use context manager'

  def __enter__(self):
    return self

  def __exit__(self, _exc_type, _exc_val, _exc_tb):
    if self.buf:
      self.buf.close()
      self.buf = None

  def read_at(self, offset, count):
    self.buf.seek(offset)
    return self.buf.read(count)

  def read_byte(self):
    return self.buf.read(1)[0]

  def read_uleb(self):
    return read_uleb(self.buf)

  def read_sleb(self):
    return read_sleb(self.buf)

  def read_string(self):
    size = self.read_uleb()
    return self.buf.read(size).decode('utf-8')

  def read_limits(self):
    flags = self.read_byte()
    initial = self.read_uleb()
    maximum = 0
    if flags & LIMITS_HAS_MAX:
      maximum = self.read_uleb()
    return Limits(flags, initial, maximum)

  def read_type(self):
    return Type(self.read_uleb())

  def read_init(self):
    code = []
    while 1:
      opcode = OpCode(self.read_byte())
      args = []
      if opcode == OpCode.GLOBAL_GET:
        args.append(self.read_uleb())
      elif opcode in (OpCode.I32_CONST, OpCode.I64_CONST):
        args.append(self.read_sleb())
      elif opcode in (OpCode.REF_NULL,):
        args.append(self.read_type())
      elif opcode in (OpCode.END, OpCode.I32_ADD, OpCode.I64_ADD):
        pass
      else:
        raise Exception('unexpected opcode %s' % opcode)
      code.append((opcode, args))
      if opcode == OpCode.END:
        break
    return code

  def seek(self, offset):
    return self.buf.seek(offset)

  def tell(self):
    return self.buf.tell()

  def skip(self, count):
    self.buf.seek(count, os.SEEK_CUR)

  def sections(self):
    """Generator that lazily returns sections from the wasm file."""
    offset = HEADER_SIZE
    while offset < self.size:
      self.seek(offset)
      section_type = SecType(self.read_byte())
      section_size = self.read_uleb()
      section_offset = self.buf.tell()
      name = None
      if section_type == SecType.CUSTOM:
        name = self.read_string()

      yield Section(section_type, section_size, section_offset, name)
      offset = section_offset + section_size

  @memoize
  def get_types(self):
    type_section = self.get_section(SecType.TYPE)
    if not type_section:
      return []
    self.seek(type_section.offset)
    num_types = self.read_uleb()
    types = []
    for _ in range(num_types):
      type_form = self.read_byte()
      assert type_form == 0x60

      params = []
      num_params = self.read_uleb()
      for _ in range(num_params):
        params.append(self.read_type())

      returns = []
      num_returns = self.read_uleb()
      for _ in range(num_returns):
        returns.append(self.read_type())

      types.append(FuncType(params, returns))

    return types

  def parse_features_section(self):
    features = []
    sec = self.get_custom_section('target_features')
    if sec:
      self.seek(sec.offset)
      self.read_string()  # name
      feature_count = self.read_uleb()
      while feature_count:
        prefix = self.read_byte()
        features.append((chr(prefix), self.read_string()))
        feature_count -= 1
    return features

  @memoize
  def parse_dylink_section(self):
    dylink_section = next(self.sections())
    assert dylink_section.type == SecType.CUSTOM
    self.seek(dylink_section.offset)
    # section name
    needed = []
    export_info = {}
    import_info = {}
    self.read_string()  # name

    if dylink_section.name == 'dylink':
      mem_size = self.read_uleb()
      mem_align = self.read_uleb()
      table_size = self.read_uleb()
      table_align = self.read_uleb()

      needed_count = self.read_uleb()
      while needed_count:
        libname = self.read_string()
        needed.append(libname)
        needed_count -= 1
    elif dylink_section.name == 'dylink.0':
      section_end = dylink_section.offset + dylink_section.size
      while self.tell() < section_end:
        subsection_type = self.read_uleb()
        subsection_size = self.read_uleb()
        end = self.tell() + subsection_size
        if subsection_type == DylinkType.MEM_INFO:
          mem_size = self.read_uleb()
          mem_align = self.read_uleb()
          table_size = self.read_uleb()
          table_align = self.read_uleb()
        elif subsection_type == DylinkType.NEEDED:
          needed_count = self.read_uleb()
          while needed_count:
            libname = self.read_string()
            needed.append(libname)
            needed_count -= 1
        elif subsection_type == DylinkType.EXPORT_INFO:
          count = self.read_uleb()
          while count:
            sym = self.read_string()
            flags = self.read_uleb()
            export_info[sym] = flags
            count -= 1
        elif subsection_type == DylinkType.IMPORT_INFO:
          count = self.read_uleb()
          while count:
            module = self.read_string()
            field = self.read_string()
            flags = self.read_uleb()
            import_info.setdefault(module, {})
            import_info[module][field] = flags
            count -= 1
        else:
          print(f'unknown subsection: {subsection_type}')
          # ignore unknown subsections
          self.skip(subsection_size)
        assert self.tell() == end
    else:
      utils.exit_with_error('error parsing shared library')

    return Dylink(mem_size, mem_align, table_size, table_align, needed, export_info, import_info)

  @memoize
  def get_exports(self):
    export_section = self.get_section(SecType.EXPORT)
    if not export_section:
      return []

    self.seek(export_section.offset)
    num_exports = self.read_uleb()
    exports = []
    for _ in range(num_exports):
      name = self.read_string()
      kind = ExternType(self.read_byte())
      index = self.read_uleb()
      exports.append(Export(name, kind, index))

    return exports

  @memoize
  def get_imports(self):
    import_section = self.get_section(SecType.IMPORT)
    if not import_section:
      return []

    self.seek(import_section.offset)
    num_imports = self.read_uleb()
    imports = []
    for _ in range(num_imports):
      mod = self.read_string()
      field = self.read_string()
      kind = ExternType(self.read_byte())
      type_ = None
      if kind == ExternType.FUNC:
        type_ = self.read_uleb()
      elif kind == ExternType.GLOBAL:
        type_ = self.read_sleb()
        self.read_byte()  # mutable
      elif kind == ExternType.MEMORY:
        self.read_limits()  # limits
      elif kind == ExternType.TABLE:
        type_ = self.read_sleb()
        self.read_limits()  # limits
      elif kind == ExternType.TAG:
        self.read_byte()  # attribute
        type_ = self.read_uleb()
      else:
        raise AssertionError()
      imports.append(Import(kind, mod, field, type_))

    return imports

  @memoize
  def get_globals(self):
    global_section = self.get_section(SecType.GLOBAL)
    if not global_section:
      return []
    globls = []
    self.seek(global_section.offset)
    num_globals = self.read_uleb()
    for _ in range(num_globals):
      global_type = self.read_type()
      mutable = self.read_byte()
      init = self.read_init()
      globls.append(Global(global_type, mutable, init))
    return globls

  @memoize
  def get_start(self):
    start_section = self.get_section(SecType.START)
    if not start_section:
      return None
    self.seek(start_section.offset)
    return self.read_uleb()

  @memoize
  def get_functions(self):
    code_section = self.get_section(SecType.CODE)
    if not code_section:
      return []
    functions = []
    self.seek(code_section.offset)
    num_functions = self.read_uleb()
    for _ in range(num_functions):
      body_size = self.read_uleb()
      start = self.tell()
      functions.append(FunctionBody(start, body_size))
      self.seek(start + body_size)
    return functions

  def get_section(self, section_code):
    return next((s for s in self.sections() if s.type == section_code), None)

  @memoize
  def get_custom_section(self, name):
    for section in self.sections():
      if section.type == SecType.CUSTOM and section.name == name:
        return section
    return None

  @memoize
  def get_segments(self):
    segments = []
    data_section = self.get_section(SecType.DATA)
    self.seek(data_section.offset)
    num_segments = self.read_uleb()
    for _ in range(num_segments):
      flags = self.read_uleb()
      if (flags & SEG_PASSIVE):
        init = None
      else:
        init = self.read_init()
      size = self.read_uleb()
      offset = self.tell()
      segments.append(DataSegment(flags, init, offset, size))
      self.seek(offset + size)
    return segments

  @memoize
  def get_tables(self):
    table_section = self.get_section(SecType.TABLE)
    if not table_section:
      return []

    self.seek(table_section.offset)
    num_tables = self.read_uleb()
    tables = []
    for _ in range(num_tables):
      elem_type = self.read_type()
      limits = self.read_limits()
      tables.append(Table(elem_type, limits))

    return tables

  @memoize
  def get_function_types(self):
    function_section = self.get_section(SecType.FUNCTION)
    if not function_section:
      return []

    self.seek(function_section.offset)
    num_types = self.read_uleb()
    func_types = []
    for _ in range(num_types):
      func_types.append(self.read_uleb())
    return func_types

  def has_name_section(self):
    return self.get_custom_section('name') is not None

  @once
  def _calc_indexes(self):
    self.imports_by_kind = {}
    for i in self.get_imports():
      self.imports_by_kind.setdefault(i.kind, [])
      self.imports_by_kind[i.kind].append(i)

  def num_imported_funcs(self):
    self._calc_indexes()
    return len(self.imports_by_kind.get(ExternType.FUNC, []))

  def num_imported_globals(self):
    self._calc_indexes()
    return len(self.imports_by_kind.get(ExternType.GLOBAL, []))

  def get_function(self, idx):
    self._calc_indexes()
    assert idx >= self.num_imported_funcs()
    return self.get_functions()[idx - self.num_imported_funcs()]

  def get_global(self, idx):
    self._calc_indexes()
    assert idx >= self.num_imported_globals()
    return self.get_globals()[idx - self.num_imported_globals()]

  def get_function_type(self, idx):
    self._calc_indexes()
    if idx < self.num_imported_funcs():
      imp = self.imports_by_kind[ExternType.FUNC][idx]
      func_type = imp.type
    else:
      func_type = self.get_function_types()[idx - self.num_imported_funcs()]
    return self.get_types()[func_type]


def parse_dylink_section(wasm_file):
  with Module(wasm_file) as module:
    return module.parse_dylink_section()


def get_exports(wasm_file):
  with Module(wasm_file) as module:
    return module.get_exports()


def get_imports(wasm_file):
  with Module(wasm_file) as module:
    return module.get_imports()


def get_weak_imports(wasm_file):
  weak_imports = []
  dylink_sec = parse_dylink_section(wasm_file)
  for symbols in dylink_sec.import_info.values():
    for symbol, flags in symbols.items():
      if flags & SYMBOL_BINDING_MASK == SYMBOL_BINDING_WEAK:
        weak_imports.append(symbol)
  return weak_imports

# SIG # Begin Windows Authenticode signature block
# MIInOAYJKoZIhvcNAQcCoIInKTCCJyUCAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCDkO3FKhvR1agIC
# T0YwshiGh+0eGRYn8pzKigdExm/jfKCCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
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
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCDesTUNjRI2xOb5iJu6kxfrkW2fPVHN
# YGMsxgLvSfkFIjBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# AILqQsNG+2n1d+JVMZU97xvJR7UkhLhoAsOnRTi0oV1xa6EE/EOrpb1GAzt4MBC/
# SlRkuGqypeMyAruWdx19ZEOOjDu46ghSjFl7n9QWUzi5gC1JgOrpqY/jLMLS5SMO
# OKLd+j4es5zlP0uPQkhsbWs7m+OZK7Kdh8NpmRyDWFYSlqZv37pY9t2X9CJ9j6A4
# 2DAlFIPCTXR+EMFKiw+9fk2/o+uNIn3IPX0KgQwrBVRoD5WCmd7IHr0z8ikbVZ1R
# IhPuhG+vWYo6KakUbNVo5m1XAgNWvV+27QY2losJOal5i9pgnd6ZSWtG8rKEY8bm
# Dql9dBAj2bi8Gk4Go7ikgE+hgheXMIIXkwYKKwYBBAGCNwMDATGCF4Mwghd/Bgkq
# hkiG9w0BBwKgghdwMIIXbAIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQg8I1JPUj7ZP8yECTQJB9ljzes/mK2/z/ZiJJA0HLXJqgCBmnnW60rDRgTMjAy
# NjA0MzAwMDUwNDcuMzI1WjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
# BgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1p
# Y3Jvc29mdCBDb3Jwb3JhdGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2Eg
# T3BlcmF0aW9uczEnMCUGA1UECxMeblNoaWVsZCBUU1MgRVNOOkEwMDAtMDVFMC1E
# OTQ3MSUwIwYDVQQDExxNaWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNloIIR7TCC
# ByAwggUIoAMCAQICEzMAAAIruwBQ/007mqEAAQAAAiswDQYJKoZIhvcNAQELBQAw
# fDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1Jl
# ZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMd
# TWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwHhcNMjYwMjE5MTk0MDExWhcN
# MjcwNTE3MTk0MDExWjCByzELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2EgT3BlcmF0aW9uczEnMCUG
# A1UECxMeblNoaWVsZCBUU1MgRVNOOkEwMDAtMDVFMC1EOTQ3MSUwIwYDVQQDExxN
# aWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNlMIICIjANBgkqhkiG9w0BAQEFAAOC
# Ag8AMIICCgKCAgEAl95oujg97MlKkJuEKoJKyj23LCv0Md32HLS/PlTNbjmN26KI
# uRscGrk4EH+iRRyE06MUu4I6ipSvDhS8y+lE5dI8RCubeg7jnICV3b7rYpqE5Tkt
# At5MiE1wQF6I/4KeoUUfc+lkYqdSrZIpW93SVwo0Kk/T9grro6/lc/K/mfow5dPY
# 4v4nP+Bt+K95lcI7P/xp8fT7t9VfK1xYnDYgM8abm2sKW3fKan85Vk9r5xt5BfZe
# jIkRG7yd1xy1MB0LIdLf060hcf7P8gqqSVmCeqApRu9Lb7BR9GkT/MAeHD/whWti
# C75NuotznCQZfqaiox00gcvZr8EzxA5Z83KNDbfEeqUj012YAbLHB4aCnwtFkJjs
# 2NpHl2wJkU3GTMl8+b/wCW5qCNMtOwWs77eTZF3XRvUxK0FsLbBciCqxJQ4Fnx3g
# qE7tcLtnIg93Su9s93GtoM6BA8U9o/QVyFCmok803UD0bADGjt3VNM2hsDDJcLUi
# cg4deGBIGaFLub0vDLoDKnazY6Yci+ucioY6QFm4WJCBzv9LmY7vebT/M2TalyEY
# eLXX1hyTwE5/a/nMZMrodsdFS3X8dZZivV9zYx9DbYALOSQf8DpZMrrncZhU31lc
# kay9+4rKTmfGjwBYL8kenDU5BqZBaN+SUY3IjZmYlOKk/VLcvleYLnRZNY8CAwEA
# AaOCAUkwggFFMB0GA1UdDgQWBBQ+Fo7kE1CW7W3d45r2ZLtBWdnlNjAfBgNVHSME
# GDAWgBSfpxVdAF5iXYP05dJlpxtTNRnpcjBfBgNVHR8EWDBWMFSgUqBQhk5odHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBUaW1l
# LVN0YW1wJTIwUENBJTIwMjAxMCgxKS5jcmwwbAYIKwYBBQUHAQEEYDBeMFwGCCsG
# AQUFBzAChlBodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01p
# Y3Jvc29mdCUyMFRpbWUtU3RhbXAlMjBQQ0ElMjAyMDEwKDEpLmNydDAMBgNVHRMB
# Af8EAjAAMBYGA1UdJQEB/wQMMAoGCCsGAQUFBwMIMA4GA1UdDwEB/wQEAwIHgDAN
# BgkqhkiG9w0BAQsFAAOCAgEAzvwirHIhDPJK9X6h+E5X0+uhDaE48V8PNdKchKtD
# 3a4C8H4E98ftYM+wkB7VHXr6jEOah8gy4ZuqU/ddQmJBjfuoPjFO3zGE6+nd0sYn
# icASKFpH0eIO0orRszClOOuShGHo33XaFIKLwv8XEaWgCzuad/wNuPAcoSYjLbQU
# DQ7bE/x2ghcERQlEW8v3/HNZJMvBfMZAlxc/vzLWeXdZVhY8DiNoHmR1qvV4oQzo
# HnuZ0tpKKOVep/FxtttFE3r1X/qYJqSB+9Vyg1SGExhmSbOsj5Xydml6sNTBODUe
# qJDbGNz9TN9R+gzGEXyRjQTXqefeZFxod2MwN3AosoPo5iefIf307454CKblBXzg
# 6Q4xcdInNWKCwDcYQhd0YUvamDOyuNDRISrIWLmgJCBtlwSmIoN6/9P29LI74wcL
# OeQGKJzJtwPKnF/+pPVX3NJr/XbaJx7lhnwNm/qhNqqQp4cxm3Qx6u4jkmRMNNZz
# bqQDH9XONZPSKE0Ns94sOsOGWaCzsoOEyjG6dZK6U+La4qf8t9Ar+ZIcqggzaml0
# KQZDmDjfC4LaEN2plTl+4seY3a58f71MU1EooF761nS+1JPJKZktM7aNk6Mu2k+a
# Acwk734/YifwTfxNb4RQZISQr2ez1b7DEp005pMdhWpdpVZM7bgCOOHw/7siyXWj
# EEswggdxMIIFWaADAgECAhMzAAAAFcXna54Cm0mZAAAAAAAVMA0GCSqGSIb3DQEB
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
# BAsTHm5TaGllbGQgVFNTIEVTTjpBMDAwLTA1RTAtRDk0NzElMCMGA1UEAxMcTWlj
# cm9zb2Z0IFRpbWUtU3RhbXAgU2VydmljZaIjCgEBMAcGBSsOAwIaAxUACaw/dMpB
# 6aP9ABm+5ZsL7ArakTmggYMwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDANBgkqhkiG9w0BAQsFAAIFAO2dDY0wIhgPMjAyNjA0MjkyMzA2NTNaGA8y
# MDI2MDQzMDIzMDY1M1owdzA9BgorBgEEAYRZCgQBMS8wLTAKAgUA7Z0NjQIBADAK
# AgEAAgIBIQIB/zAHAgEAAgISpzAKAgUA7Z5fDQIBADA2BgorBgEEAYRZCgQCMSgw
# JjAMBgorBgEEAYRZCgMCoAowCAIBAAIDB6EgoQowCAIBAAIDAYagMA0GCSqGSIb3
# DQEBCwUAA4IBAQARvIHFTchSC5etEN/gsMWRgez9DiPHpZnSiqn3TNDU977JEbBa
# 5/XGxHyBYOvihNQuNDQwG12ncdFiHCYDp1ygYjXZ5Cpy0YcCUiExqzWqQsj3OTCK
# D52HKC/wB+ax8Mv0MUx6cDYrrcQ8pkJCmy1L8rRQPmFH7dZMNsySbgwFxENbWUIp
# U1cOR3vpyGkLb8uUaZFAWildF99tMQr3W5NJOQgL6KQ/q/WC6XI9lVUDLhyokAXa
# O1vJso7IWk99CXxAAsxB5/ZukNAmORQK0vuatK9/MACTkKUAgo2qhZ0JoYZ/fiQX
# 7HYdc09Cu+fBiRieUOvbphrsMd0bBhSbP4I4MYIEDTCCBAkCAQEwgZMwfDELMAkG
# A1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQx
# HjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMdTWljcm9z
# b2Z0IFRpbWUtU3RhbXAgUENBIDIwMTACEzMAAAIruwBQ/007mqEAAQAAAiswDQYJ
# YIZIAWUDBAIBBQCgggFKMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRABBDAvBgkq
# hkiG9w0BCQQxIgQg8soa3cXlqVus6vCHC4Xs7gmhVvhTh3Fr14e0n/Z4aDcwgfoG
# CyqGSIb3DQEJEAIvMYHqMIHnMIHkMIG9BCByDiP0P5BX7WAPjNjmPtQcd2owQ+v1
# gwLT09rxZL9uUjCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNo
# aW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29y
# cG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEw
# AhMzAAACK7sAUP9NO5qhAAEAAAIrMCIEIHrdxcrcwtkq7jSWYYCCMJ0N6v0kMGQR
# 5R2VHkgxyUyaMA0GCSqGSIb3DQEBCwUABIICAG+Ps9fpBrRdrSFKJRYcEHvcS4EL
# 8bMTe6HupluCMKDyBUyqaGmT8LYuvF1Ex/kv2AmG911e0M4p0zpwYtUjiiCDDf/X
# vYaH4yltzX/6QRogWc3VMXhijxTfUB85yJygvQ8wnErGGS6y1RLTMBzIZWlVTiHW
# c/wPO/t2BaMbKtX+/tTI0D/bXu7MI0S19cjPGRO0Dx9jT9agLs1fYUGa+kI/Krra
# p0JLtxhs7FR5KhSHk1MwLa5AFMYbuX/tqvsloLsyyYmBqtk0W84wbCB470UXSkpB
# BsB0PMxCks6N98SBWcVjEsaODJj2zsgvkReDwNTuPNpzEccGRd5rnwG5FdtjX6fI
# F5aLlQ71O8ybKaQT6Ax8fjZovgWZDMI056tQwhNVv437cji8Mh2qOiaecFuE1yuZ
# e2KWeutfKRviLLohSbcqS/gSPbR9GCb5RyGvJ4OB33nT6BbM+rzb6Jls2SKFv1om
# 3F9vYySpBeyag+m7r0q2yaA7dyuVQV8Dxb/gtlrwHtgk84aMx4MXwioT4Go9o71d
# 6Ytcxyff2/Qdkgft7z+jBgY9EIrc/IAY0BVdHRJiD+u0/6u2KaHyx4kdnGyb5Dig
# iKB21jiqEERZP+3gX8j9n8vIKskUMpdnI8KN2il6Flzf6T4SOHaWlNwhExda1MZQ
# ZVvRX6CgkiPV3vb6
# SIG # End Windows Authenticode signature block