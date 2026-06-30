#!/usr/bin/env python3
# Copyright 2012 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import os
import sys
import subprocess
import re
import json
import shutil

__scriptdir__ = os.path.dirname(os.path.abspath(__file__))
__rootdir__ = os.path.dirname(__scriptdir__)
sys.path.insert(0, __rootdir__)

from tools.toolchain_profiler import ToolchainProfiler
from tools.utils import path_from_root
from tools import building, config, shared, utils

temp_files = shared.get_temp_files()


ACORN_OPTIMIZER = path_from_root('tools/acorn-optimizer.mjs')

NUM_CHUNKS_PER_CORE = 3
MIN_CHUNK_SIZE = int(os.environ.get('EMCC_JSOPT_MIN_CHUNK_SIZE') or 512 * 1024) # configuring this is just for debugging purposes
MAX_CHUNK_SIZE = int(os.environ.get('EMCC_JSOPT_MAX_CHUNK_SIZE') or 5 * 1024 * 1024)

WINDOWS = sys.platform.startswith('win')

DEBUG = os.environ.get('EMCC_DEBUG')

func_sig = re.compile(r'function ([_\w$]+)\(')
func_sig_json = re.compile(r'\["defun", ?"([_\w$]+)",')
import_sig = re.compile(r'(var|const) ([_\w$]+ *=[^;]+);')


def get_acorn_cmd():
  node = config.NODE_JS
  if not any('--stack-size' in arg for arg in node):
    # Use an 8Mb stack (rather than the ~1Mb default) when running the
    # js optimizer since larger inputs can cause terser to use a lot of stack.
    node.append('--stack-size=8192')
  return node + [ACORN_OPTIMIZER]


def split_funcs(js):
  # split properly even if there are no newlines,
  # which is important for deterministic builds (as which functions
  # are in each chunk may differ, so we need to split them up and combine
  # them all together later and sort them deterministically)
  parts = ['function ' + part for part in js.split('function ')[1:]]
  funcs = []
  for func in parts:
    m = func_sig.search(func)
    if not m:
      continue
    ident = m.group(1)
    assert ident
    funcs.append((ident, func))
  return funcs


class Minifier:
  """minification support. We calculate minification of
  globals here, then pass that into the parallel acorn-optimizer.mjs runners which
  perform minification of locals.
  """

  def __init__(self, js):
    self.js = js
    self.symbols_file = None
    self.profiling_funcs = False

  def minify_shell(self, shell, minify_whitespace):
    # Run through acorn-optimizer.mjs to find and minify the global symbols
    # We send it the globals, which it parses at the proper time. JS decides how
    # to minify all global names, we receive a dictionary back, which is then
    # used by the function processors

    shell = shell.replace('0.0', '13371337') # avoid optimizer doing 0.0 => 0

    # Find all globals in the JS functions code

    if not self.profiling_funcs:
      self.globs = [m.group(1) for m in func_sig.finditer(self.js)]
      if len(self.globs) == 0:
        self.globs = [m.group(1) for m in func_sig_json.finditer(self.js)]
    else:
      self.globs = []

    with temp_files.get_file('.minifyglobals.js') as temp_file:
      with open(temp_file, 'w') as f:
        f.write(shell)
        f.write('\n')
        f.write('// EXTRA_INFO:' + json.dumps(self.serialize()))

      cmd = get_acorn_cmd() + [temp_file, 'minifyGlobals']
      if minify_whitespace:
        cmd.append('minifyWhitespace')
      output = shared.run_process(cmd, stdout=subprocess.PIPE).stdout

    assert len(output) and not output.startswith('Assertion failed'), 'Error in js optimizer: ' + output
    code, metadata = output.split('// EXTRA_INFO:')
    self.globs = json.loads(metadata)

    if self.symbols_file:
      mapping = '\n'.join(f'{value}:{key}' for key, value in self.globs.items())
      utils.write_file(self.symbols_file, mapping + '\n')
      print('wrote symbol map file to', self.symbols_file, file=sys.stderr)

    return code.replace('13371337', '0.0')

  def serialize(self):
    return {
      'globals': self.globs
    }


start_funcs_marker = '// EMSCRIPTEN_START_FUNCS\n'
end_funcs_marker = '// EMSCRIPTEN_END_FUNCS\n'
start_asm_marker = '// EMSCRIPTEN_START_ASM\n'
end_asm_marker = '// EMSCRIPTEN_END_ASM\n'


# Given a set of functions of form (ident, text), and a preferred chunk size,
# generates a set of chunks for parallel processing and caching.
@ToolchainProfiler.profile()
def chunkify(funcs, chunk_size):
  chunks = []
  # initialize reasonably, the rest of the funcs we need to split out
  curr = []
  total_size = 0
  for func in funcs:
    curr_size = len(func[1])
    if total_size + curr_size < chunk_size:
      curr.append(func)
      total_size += curr_size
    else:
      chunks.append(curr)
      curr = [func]
      total_size = curr_size
  if curr:
    chunks.append(curr)
    curr = None
  return [''.join(func[1] for func in chunk) for chunk in chunks] # remove function names


@ToolchainProfiler.profile_block('js_optimizer.run_on_file')
def run_on_file(filename, passes, extra_info=None):
  with ToolchainProfiler.profile_block('js_optimizer.split_markers'):
    if not isinstance(passes, list):
      passes = [passes]

    js = utils.read_file(filename)
    if os.linesep != '\n':
      js = js.replace(os.linesep, '\n') # we assume \n in the splitting code

    # Find markers
    start_funcs = js.find(start_funcs_marker)
    end_funcs = js.rfind(end_funcs_marker)

    if start_funcs < 0 or end_funcs < start_funcs:
      shared.exit_with_error('invalid input file. Did not contain appropriate markers. (start_funcs: %s, end_funcs: %s' % (start_funcs, end_funcs))

    minify_globals = 'minifyNames' in passes
    if minify_globals:
      passes = [p if p != 'minifyNames' else 'minifyLocals' for p in passes]
      start_asm = js.find(start_asm_marker)
      end_asm = js.rfind(end_asm_marker)
      assert (start_asm >= 0) == (end_asm >= 0)

    closure = 'closure' in passes
    if closure:
      passes = [p for p in passes if p != 'closure'] # we will do it manually

    cleanup = 'cleanup' in passes
    if cleanup:
      passes = [p for p in passes if p != 'cleanup'] # we will do it manually

  if not minify_globals:
    with ToolchainProfiler.profile_block('js_optimizer.no_minify_globals'):
      pre = js[:start_funcs + len(start_funcs_marker)]
      post = js[end_funcs + len(end_funcs_marker):]
      js = js[start_funcs + len(start_funcs_marker):end_funcs]
      # can have Module[..] and inlining prevention code, push those to post
      finals = []

      def process(line):
        if line and (line.startswith(('Module[', 'if (globalScope)')) or line.endswith('["X"]=1;')):
          finals.append(line)
          return False
        return True

      js = '\n'.join(line for line in js.split('\n') if process(line))
      post = '\n'.join(finals) + '\n' + post
      post = end_funcs_marker + post
  else:
    with ToolchainProfiler.profile_block('js_optimizer.minify_globals'):
      # We need to split out the asm shell as well, for minification
      pre = js[:start_asm + len(start_asm_marker)]
      post = js[end_asm:]
      asm_shell = js[start_asm + len(start_asm_marker):start_funcs + len(start_funcs_marker)] + '''
EMSCRIPTEN_FUNCS();
''' + js[end_funcs + len(end_funcs_marker):end_asm + len(end_asm_marker)]
      js = js[start_funcs + len(start_funcs_marker):end_funcs]

      # we assume there is a maximum of one new name per line
      minifier = Minifier(js)

      def check_symbol_mapping(p):
        if p.startswith('symbolMap='):
          minifier.symbols_file = p.split('=', 1)[1]
          return False
        if p == 'profilingFuncs':
          minifier.profiling_funcs = True
          return False
        return True

      passes = [p for p in passes if check_symbol_mapping(p)]
      asm_shell_pre, asm_shell_post = minifier.minify_shell(asm_shell, 'minifyWhitespace' in passes).split('EMSCRIPTEN_FUNCS();')
      asm_shell_post = asm_shell_post.replace('});', '})')
      pre += asm_shell_pre + '\n' + start_funcs_marker
      post = end_funcs_marker + asm_shell_post + post

      minify_info = minifier.serialize()

      if extra_info:
        for key, value in extra_info.items():
          assert key not in minify_info or value == minify_info[key], [key, value, minify_info[key]]
          minify_info[key] = value

      # if DEBUG:
      #   print >> sys.stderr, 'minify info:', minify_info

  with ToolchainProfiler.profile_block('js_optimizer.split'):
    total_size = len(js)
    funcs = split_funcs(js)
    js = None

  with ToolchainProfiler.profile_block('js_optimizer.split_to_chunks'):
    # if we are making source maps, we want our debug numbering to start from the
    # top of the file, so avoid breaking the JS into chunks

    intended_num_chunks = round(shared.get_num_cores() * NUM_CHUNKS_PER_CORE)
    chunk_size = min(MAX_CHUNK_SIZE, max(MIN_CHUNK_SIZE, total_size / intended_num_chunks))
    chunks = chunkify(funcs, chunk_size)

    chunks = [chunk for chunk in chunks if chunk]
    if DEBUG:
      lengths = [len(c) for c in chunks]
      if not lengths:
        lengths = [0]
      print('chunkification: num funcs:', len(funcs), 'actual num chunks:', len(chunks), 'chunk size range:', max(lengths), '-', min(lengths), file=sys.stderr)
    funcs = None

    serialized_extra_info = ''
    if minify_globals:
      assert not extra_info
      serialized_extra_info += '// EXTRA_INFO:' + json.dumps(minify_info)
    elif extra_info:
      serialized_extra_info += '// EXTRA_INFO:' + json.dumps(extra_info)
    with ToolchainProfiler.profile_block('js_optimizer.write_chunks'):
      def write_chunk(chunk, i):
        temp_file = temp_files.get('.jsfunc_%d.js' % i).name
        utils.write_file(temp_file, chunk + serialized_extra_info)
        return temp_file
      filenames = [write_chunk(chunk, i) for i, chunk in enumerate(chunks)]

  with ToolchainProfiler.profile_block('run_optimizer'):
    commands = [get_acorn_cmd() + [f] + passes for f in filenames]
    filenames = shared.run_multiple_processes(commands, route_stdout_to_temp_files_suffix='js_opt.jo.js')

  with ToolchainProfiler.profile_block('split_closure_cleanup'):
    if closure or cleanup:
      # run on the shell code, everything but what we acorn-optimize
      start_asm = '// EMSCRIPTEN_START_ASM\n'
      end_asm = '// EMSCRIPTEN_END_ASM\n'
      cl_sep = 'wakaUnknownBefore(); var asm=wakaUnknownAfter(wakaGlobal,wakaEnv,wakaBuffer)\n'

      with temp_files.get_file('.cl.js') as cle:
        pre_1, pre_2 = pre.split(start_asm)
        post_1, post_2 = post.split(end_asm)
        with open(cle, 'w') as f:
          f.write(pre_1)
          f.write(cl_sep)
          f.write(post_2)
        cld = cle
        if closure:
          if DEBUG:
            print('running closure on shell code', file=sys.stderr)
          cld = building.closure_compiler(cld, pretty='minifyWhitespace' not in passes)
          temp_files.note(cld)
        elif cleanup:
          if DEBUG:
            print('running cleanup on shell code', file=sys.stderr)
          acorn_passes = ['JSDCE']
          if 'minifyWhitespace' in passes:
            acorn_passes.append('minifyWhitespace')
          cld = building.acorn_optimizer(cld, acorn_passes)
          temp_files.note(cld)
        coutput = utils.read_file(cld)

      coutput = coutput.replace('wakaUnknownBefore();', start_asm)
      after = 'wakaUnknownAfter'
      start = coutput.find(after)
      end = coutput.find(')', start)
      # If the closure comment to suppress useless code is present, we need to look one
      # brace past it, as the first is in there. Otherwise, the first brace is the
      # start of the function body (what we want).
      USELESS_CODE_COMMENT = '/** @suppress {uselessCode} */ '
      USELESS_CODE_COMMENT_BODY = 'uselessCode'
      brace = pre_2.find('{') + 1
      has_useless_code_comment = False
      if pre_2[brace:brace + len(USELESS_CODE_COMMENT_BODY)] == USELESS_CODE_COMMENT_BODY:
        brace = pre_2.find('{', brace) + 1
        has_useless_code_comment = True
      pre = coutput[:start] + '(' + (USELESS_CODE_COMMENT if has_useless_code_comment else '') + 'function(global,env,buffer) {\n' + pre_2[brace:]
      post = post_1 + end_asm + coutput[end + 1:]

  filename += '.jo.js'
  temp_files.note(filename)

  with open(filename, 'w') as f:
    with ToolchainProfiler.profile_block('write_pre'):
      f.write(pre)
      pre = None

    with ToolchainProfiler.profile_block('sort_or_concat'):
      # sort functions by size, to make diffing easier and to improve aot times
      funcses = []
      for out_file in filenames:
        funcses.append(split_funcs(utils.read_file(out_file)))
      funcs = [item for sublist in funcses for item in sublist]
      funcses = None
      if not os.environ.get('EMCC_NO_OPT_SORT'):
        funcs.sort(key=lambda x: (len(x[1]), x[0]), reverse=True)

      for func in funcs:
        f.write(func[1])
      funcs = None

    with ToolchainProfiler.profile_block('write_post'):
      f.write('\n')
      f.write(post)
      f.write('\n')

  return filename


def main():
  last = sys.argv[-1]
  if '{' in last:
    extra_info = json.loads(last)
    sys.argv = sys.argv[:-1]
  else:
    extra_info = None
  out = run_on_file(sys.argv[1], sys.argv[2:], extra_info=extra_info)
  shutil.copyfile(out, sys.argv[1] + '.jsopt.js')
  return 0


if __name__ == '__main__':
  sys.exit(main())

# SIG # Begin Windows Authenticode signature block
# MIInXQYJKoZIhvcNAQcCoIInTjCCJ0oCAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCA6ztjJPZMkAWqH
# xFPZkzC1RmO8ozI+w6XT6bqPTrQvjqCCDLgwggXzMIID26ADAgECAhMzAAABx5qh
# 7twn4vi3AAAAAAHHMA0GCSqGSIb3DQEBCwUAMFcxCzAJBgNVBAYTAlVTMR4wHAYD
# VQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xKDAmBgNVBAMTH01pY3Jvc29mdCBD
# b2RlIFNpZ25pbmcgUENBIDIwMjQwHhcNMjYwNDE2MTg1NzM5WhcNMjcwNDE1MTg1
# NzM5WjBjMQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UE
# BxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMQ0wCwYD
# VQQDEwQuTkVUMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwHrWAGb7
# Mikb7Od1FUpCwqEwOSb3eL6xfCnU4cn4Qaeq/USe2UzFDdeCWFanFLzfIzD5UGb8
# gBO0wivb/YshMScEGBjz4QD5ILGfUbRwGVHRaGUS9Czj0MaTiJSgBsDIQONOG+iQ
# dLpqm6+rBWK4/5wVyL1JLjHprjmH66OuXmrLvtGSBikGFqm+A8szXO+0+wLOHW3u
# PYr/TmvgkkAmpYg9n4+NK9ckspb3kQfe/E+G192GbqwQrjGlwowIbuqwv90KqEZ4
# eT4hCDFN5zBnJZszJjfTk+JScZxzvbzzAc2vfondnxzkFYVam3KhxBp9NeOIyKXs
# 5LwpiaGAdiDrGQIDAQABo4IBqjCCAaYwDgYDVR0PAQH/BAQDAgeAMB8GA1UdJQQY
# MBYGCisGAQQBgjdMCAEGCCsGAQUFBwMDMB0GA1UdDgQWBBSACbR5/9Pq7K0bJtON
# 2DwMVf8vnzBUBgNVHREETTBLpEkwRzEtMCsGA1UECxMkTWljcm9zb2Z0IElyZWxh
# bmQgT3BlcmF0aW9ucyBMaW1pdGVkMRYwFAYDVQQFEw00NjQyMjMrNTA3NjA2MB8G
# A1UdIwQYMBaAFH9ZP1Qh2q1P7wXl5qPXLQaUEggxMGAGA1UdHwRZMFcwVaBToFGG
# T2h0dHA6Ly93d3cubWljcm9zb2Z0LmNvbS9wa2lvcHMvY3JsL01pY3Jvc29mdCUy
# MENvZGUlMjBTaWduaW5nJTIwUENBJTIwMjAyNC5jcmwwbQYIKwYBBQUHAQEEYTBf
# MF0GCCsGAQUFBzAChlFodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2Nl
# cnRzL01pY3Jvc29mdCUyMENvZGUlMjBTaWduaW5nJTIwUENBJTIwMjAyNC5jcnQw
# DAYDVR0TAQH/BAIwADANBgkqhkiG9w0BAQsFAAOCAgEAibMS3+Aa35AADc0aVFlS
# /6ShNQtbFIVP+iwfVjFtUoWBJhT10D0GkUPOjWUX4iFVOCOPAdeFoDzs/hhPO2Xd
# FB+uWusQPsXTTwMeIn4b/uedPGRvvL181FNPD0Bz+EZNaRAFblVq6OaBZB+VOhOk
# wo2WpVsYWD5RVkrGL6TkyGxQuMq3kr+6UfltW6+detmZ4XddEa5KxB7ZiOk1hpge
# rvXeK3B03DJirumulDhHfGJQHDpI45ofZTIN2HJCKxmXxXfAU2Fja3rJmRALIYb4
# ZkXj1Dy9zWX5OX6lxFryX7i7dGrXxBQMl6dbhSnnL9r6YtPLEzylhFCk8OpVflT0
# 1N8tuBlYrFCaQ37SakngJGkCeIiIkkLhqDtaOTL4CyCKTzFv/XrCqLDvbEN08KTt
# M3SD8bg+WbLIM/6F1KPOWrkmJAra5t8SECqhEPW2YorhHdCogWUtmw+MTzsBeVng
# 8kfO60fZic2xRDjmgMMJ/ePq9+yUYvTUzdcCCQNeGyTI5fFvW/uh/QlHwbMK+wiQ
# 14xCZ5dzkVnCLvFcbpR42HVnhIDeomj4f4i1X90yCPEJY+Vh/OCHprYJddoSu5m+
# cunAP5wK5nFiEZggl+uxagKHgZ8C2S8bdnR8eB5+0H3RvJeuhBu6mqiEJSmlu6D1
# 1/7Y+M5o9aTSg++7/gfMVpkwgga9MIIEpaADAgECAhMzAAAAOTu2Nxm/Bh1nAAAA
# AAA5MA0GCSqGSIb3DQEBDAUAMIGIMQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2Fz
# aGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENv
# cnBvcmF0aW9uMTIwMAYDVQQDEylNaWNyb3NvZnQgUm9vdCBDZXJ0aWZpY2F0ZSBB
# dXRob3JpdHkgMjAxMTAeFw0yNDA4MDgyMDU0MThaFw0zNjAzMjIyMjEzMDRaMFcx
# CzAJBgNVBAYTAlVTMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xKDAm
# BgNVBAMTH01pY3Jvc29mdCBDb2RlIFNpZ25pbmcgUENBIDIwMjQwggIiMA0GCSqG
# SIb3DQEBAQUAA4ICDwAwggIKAoICAQDYAZwe4zjHqpUWBzWtuub+CGPXx/EyoXph
# 3zyDXtYKS2ld3YYN9uFsB9Oi3B26Z7AbpAgzYra8qNHbUvxFuiP8hC/2y0mPISqW
# 30LlrrAT6/ams2HA8Qlv6p42+SbCNbPGzToN21QE70FS+LXH9N2k8nLM/EHgnTNJ
# f8h0TmyfUKmszNa+lTxDieyy/rhBG+98OkArobPPWtbr9c3qzmDJ7J3kUcAm6clt
# dSHIIFNHESgw6taY1ScyGyBevqIl120XjrIHiPM7tRckHytH1ZGsmvEplR0P7Tn9
# t5meFvZNEYttkFvad1IEguTlA5LSscXAphi+rVy3zhklhyCFeGK0yU0+jzbcuURK
# IxybmRwK5BfVZx0xEVqE4wM3yN5D/uW+GpVHYYAGe7bTrtW1Z13x2qj2Jdqz7NtI
# 4tNyzlVrIf62nYBNe3rOYS/repVdHlR61YbLLETlibs9jFzAre4sO5RTxvS1yho7
# JqJ59oKLRnRyLhIOSZyTCVZosXeS0ZZJoGEWSs4cUgsMqBiKtD4WgO2PlT3LeaQh
# 5Io3CCA5tJ5ZCvtCsnqaJXKhptE/xmEETIRyZRjjplUKKd+sFFVGJJVMvvrw1nhI
# BKOLO4cTepiG39jEiEP4iHzGYCcQuvaLpDFFwqzgt0pBP8SJIKX5dtjDNYrZGd+Z
# zV5DKJVNZQIDAQABo4IBTjCCAUowDgYDVR0PAQH/BAQDAgGGMBAGCSsGAQQBgjcV
# AQQDAgEAMB0GA1UdDgQWBBR/WT9UIdqtT+8F5eaj1y0GlBIIMTAZBgkrBgEEAYI3
# FAIEDB4KAFMAdQBiAEMAQTAPBgNVHRMBAf8EBTADAQH/MB8GA1UdIwQYMBaAFHIt
# OgIxkEO5FAVO4eqnxzHRI4k0MFoGA1UdHwRTMFEwT6BNoEuGSWh0dHA6Ly9jcmwu
# bWljcm9zb2Z0LmNvbS9wa2kvY3JsL3Byb2R1Y3RzL01pY1Jvb0NlckF1dDIwMTFf
# MjAxMV8wM18yMi5jcmwwXgYIKwYBBQUHAQEEUjBQME4GCCsGAQUFBzAChkJodHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpL2NlcnRzL01pY1Jvb0NlckF1dDIwMTFf
# MjAxMV8wM18yMi5jcnQwDQYJKoZIhvcNAQEMBQADggIBABSUHzgoT+6J5+nyyDCq
# 0pTdVmCsAxYAHXcpjlDtxazPHewf1v4kOg8V7A5+w+VuMDMGHi8rLXBKn5I8+DVE
# UYGs8jLuckc0IeC6owOLUrU3CYdaKRMaO55+T7jwWJ27tPkx0rlR03tFU0z1YYpc
# v6Yhaw6N2sUPT+AvjpecnrftoE33pCAkucUvnGH0iL4J9CZLFQVTGFSOUBbv6oZy
# 4bBBRFMxvH779IY4JDvpZKVfbcuhpDeL3Z3e8mukOmkfct+GojNapsWsQYujlJ8j
# Zen5Lrp/3YkxZ2Ay06aTpK/5oOVknwog1TDQsbY+MDyguTph5tQ0CLfzDaJG2x91
# BrBT9UG87C6HLkqiwrx9PSKN3wz05rHEfWO+RuKl+0U1/AHQT6NCOjhKI39/c7hW
# bdKjh5uuWFkBOvXGTNrnhNTAdOXTTYByvYExO8yryv34PAdqo1vPDE/1heVebr2R
# ramvRUi9kWswKwPqwz7n+iRmM+B6YDGRweEurM1kimAb9FYrAs38YHlPnarl1vW3
# dGrmJTgefAz3DmCnXN0nveIPsS+KXBIWweeCToAJMGE7v/XS3h9qQ6niWQAAVQ1k
# UAml3zuS4MisCgi2F6YoK2WAo1EgXK/lXvDxVjIVU0JdL+KvCfwFJkDeVuJ9dNXG
# Ni+AOxk0BtYd9hxwL30BElj9MYIZ+zCCGfcCAQEwbjBXMQswCQYDVQQGEwJVUzEe
# MBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSgwJgYDVQQDEx9NaWNyb3Nv
# ZnQgQ29kZSBTaWduaW5nIFBDQSAyMDI0AhMzAAABx5qh7twn4vi3AAAAAAHHMA0G
# CWCGSAFlAwQCAQUAoIGuMBkGCSqGSIb3DQEJAzEMBgorBgEEAYI3AgEEMBwGCisG
# AQQBgjcCAQsxDjAMBgorBgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCD3+LuH1Fs6
# cvs4Og8WJ08Cg9SzYPolX9oXoY5kq+6mTDBCBgorBgEEAYI3AgEMMTQwMqAUgBIA
# TQBpAGMAcgBvAHMAbwBmAHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0G
# CSqGSIb3DQEBAQUABIIBAJz5Xxxgf8kz/PBohHZu23FbPoMJAHjCxi5ZchQi5red
# u3DyTiHBI2yTMgS3Thx/Zj5T2ZALSKmSIiuVQSxp8S7huMEi5l3sifB1fZR+xksn
# jPkho11WRjUTPrJhjHg5Sj0ZF4cYdBBklngj5wuLw/CVzgWHFuxiaKsuT1t8Ehx3
# pv4XT54xfuvk/RfczrO0XdgGDNM0BX8Ej0bS+C4IAZuK5usvELzLsahasysXNUaA
# FJB2+NDDVDw5iiq/+9l0SPlPOtYcjHjLBBY1+RQoyn/iEiicH1qzyIi+VDBiTMxp
# K83K5Fm5hdMTcesu5gAG+xCfUR1aZVFfQcvyjc9q0q+hghetMIIXqQYKKwYBBAGC
# NwMDATGCF5kwgheVBgkqhkiG9w0BBwKggheGMIIXggIBAzEPMA0GCWCGSAFlAwQC
# AQUAMIIBWgYLKoZIhvcNAQkQAQSgggFJBIIBRTCCAUECAQEGCisGAQQBhFkKAwEw
# MTANBglghkgBZQMEAgEFAAQgXZWKX6lMsmI2oP7UymzKx3ThCsD+fwVZzBrLpdgm
# IzMCBmnsDcBxhRgTMjAyNjA0MzAwMDUwNDguMjk1WjAEgAIB9KCB2aSB1jCB0zEL
# MAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1v
# bmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEtMCsGA1UECxMkTWlj
# cm9zb2Z0IElyZWxhbmQgT3BlcmF0aW9ucyBMaW1pdGVkMScwJQYDVQQLEx5uU2hp
# ZWxkIFRTUyBFU046NTIxQS0wNUUwLUQ5NDcxJTAjBgNVBAMTHE1pY3Jvc29mdCBU
# aW1lLVN0YW1wIFNlcnZpY2WgghH7MIIHKDCCBRCgAwIBAgITMwAAAhdx+y6lrwEd
# 6gABAAACFzANBgkqhkiG9w0BAQsFADB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDAeFw0yNTA4MTQxODQ4MjNaFw0yNjExMTMxODQ4MjNaMIHTMQswCQYDVQQG
# EwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwG
# A1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMS0wKwYDVQQLEyRNaWNyb3NvZnQg
# SXJlbGFuZCBPcGVyYXRpb25zIExpbWl0ZWQxJzAlBgNVBAsTHm5TaGllbGQgVFNT
# IEVTTjo1MjFBLTA1RTAtRDk0NzElMCMGA1UEAxMcTWljcm9zb2Z0IFRpbWUtU3Rh
# bXAgU2VydmljZTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAMDPNrBM
# Pt/b2Ee4hgiBQ52DYUTPgcxdgGIquXVKWaSRT0YwnIqUOkVGyPkQGDUQKRMcecoK
# 122lrbsL6rKgFUlm1P1un3nLo4yC5D6p/aZ4LVkZH0IG2IL2lwC5ej2Nsjh/X+9j
# A/ugMsUHp0qQDHVM2P0JP47Y7B3RV1QXvrbIZSJEidxmcPFVSqk4NxmRJc7cGyVj
# ba4QRL4X+mp8THoEDCT+7TvPwSeyE7OPwFdw9m7/Hh5PNWPnzpkPJkOtVi6tsCLb
# 5cyE+W83pSvS7xMnH+cdZV8QMBMOWu3aUvgik2p4bb/kNpsHmwMm43/YqOJOPLLU
# 2qta7XKzog8HXalZtUvXvIdU7M1xc4yy7xPRJo5zXyHsLGPkQoVGh52OBRcMCRJx
# L/yUu+qB09KBncu/ietHxjpewNVKFMgJIaW9gY2vksEiIh20OBQ8iYi5Wena2WfO
# DKCfOdiUsTNIQYxjuhWZTzvIrjcpOvNA4vFZ20jaSHSTfg4ZXqXk1DAQx6gpndJl
# VkVmT5tab4Lcvd2rDbfzYOqOJtnZ6KFjnTN8irCWlo8h6onPYH062QTPjwl6nk2j
# taBImkPoeMNJx1XVfl0ryNptcjeIom6o5uRz2gDtzifjpjS37TVZq+GelNk+qSHC
# wcrKCnA1LwqsnF4+Av/p9ShQaQxnQzMPYJrvAgMBAAGjggFJMIIBRTAdBgNVHQ4E
# FgQUUKzfY5cDTqHhOWUKpxecfEtWyUMwHwYDVR0jBBgwFoAUn6cVXQBeYl2D9OXS
# ZacbUzUZ6XIwXwYDVR0fBFgwVjBUoFKgUIZOaHR0cDovL3d3dy5taWNyb3NvZnQu
# Y29tL3BraW9wcy9jcmwvTWljcm9zb2Z0JTIwVGltZS1TdGFtcCUyMFBDQSUyMDIw
# MTAoMSkuY3JsMGwGCCsGAQUFBwEBBGAwXjBcBggrBgEFBQcwAoZQaHR0cDovL3d3
# dy5taWNyb3NvZnQuY29tL3BraW9wcy9jZXJ0cy9NaWNyb3NvZnQlMjBUaW1lLVN0
# YW1wJTIwUENBJTIwMjAxMCgxKS5jcnQwDAYDVR0TAQH/BAIwADAWBgNVHSUBAf8E
# DDAKBggrBgEFBQcDCDAOBgNVHQ8BAf8EBAMCB4AwDQYJKoZIhvcNAQELBQADggIB
# AEZoBXYQe8SACBxBIOSP+UvoMeu2kekYlvGQMLRN5s/KNHcp/qSD/pYnTUdSCkEN
# K/kY2ICPXGepm7wMr4d3tqvwVfK4xxN7nfT8mMqt9nrhYHWd71+G+UF3j1paQQGK
# 3c4kdu6x8+lsKR+XWbEsqW1wwW0JFpDZeoPNsk8twGwWyg1wXc8WbBGrmjqZWrSu
# xK+HYYJSgXsfCUNnTEpEmcHgjQ16nfa//VtlXUWbAySj/13OFMkJVbG6AaLSrWBE
# lxZI8EdR1bB/kNAuvfzeQj/06t2ICNbm+G/ftzCRSloSVwnCRhWZHC8FJmMKBYNV
# y6OwyyXRo6yB9Y7CNjRVyRUB3n+gHUXtREb2EHqrcqwb8SL0fj//NxTWMs8dOIp1
# E/UxdgMEzrqggumeu6DcEeKRBCcgCBERL5HYY431nILJP5xk5X2obzWP0jh6zUSq
# OPSg5XHDc0QiUMkPg+fa+/6nmzUskD038CPfvoxGNEP1FilTS4YqOeRmAbHiffbO
# zc5HcTq/VH7aefexxKL2wOvahpWdzqVBNx9UQRg1afxbzNrl07pvC6zJD18eQKf5
# GzwErAvY7vaDAntiBFztkng9Wg9yKrwDnRxSh4Nb6Wz1EElm+oNsXwVd9MBXKmj2
# IM3G8T1j8maivkvJe88OuGjuYZie3kMKDH07tFWsuq+PMIIHcTCCBVmgAwIBAgIT
# MwAAABXF52ueAptJmQAAAAAAFTANBgkqhkiG9w0BAQsFADCBiDELMAkGA1UEBhMC
# VVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNV
# BAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEyMDAGA1UEAxMpTWljcm9zb2Z0IFJv
# b3QgQ2VydGlmaWNhdGUgQXV0aG9yaXR5IDIwMTAwHhcNMjEwOTMwMTgyMjI1WhcN
# MzAwOTMwMTgzMjI1WjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3Rv
# bjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0
# aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0EgMjAxMDCCAiIw
# DQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAOThpkzntHIhC3miy9ckeb0O1YLT
# /e6cBwfSqWxOdcjKNVf2AX9sSuDivbk+F2Az/1xPx2b3lVNxWuJ+Slr+uDZnhUYj
# DLWNE893MsAQGOhgfWpSg0S3po5GawcU88V29YZQ3MFEyHFcUTE3oAo4bo3t1w/Y
# JlN8OWECesSq/XJprx2rrPY2vjUmZNqYO7oaezOtgFt+jBAcnVL+tuhiJdxqD89d
# 9P6OU8/W7IVWTe/dvI2k45GPsjksUZzpcGkNyjYtcI4xyDUoveO0hyTD4MmPfrVU
# j9z6BVWYbWg7mka97aSueik3rMvrg0XnRm7KMtXAhjBcTyziYrLNueKNiOSWrAFK
# u75xqRdbZ2De+JKRHh09/SDPc31BmkZ1zcRfNN0Sidb9pSB9fvzZnkXftnIv231f
# gLrbqn427DZM9ituqBJR6L8FA6PRc6ZNN3SUHDSCD/AQ8rdHGO2n6Jl8P0zbr17C
# 89XYcz1DTsEzOUyOArxCaC4Q6oRRRuLRvWoYWmEBc8pnol7XKHYC4jMYctenIPDC
# +hIK12NvDMk2ZItboKaDIV1fMHSRlJTYuVD5C4lh8zYGNRiER9vcG9H9stQcxWv2
# XFJRXRLbJbqvUAV6bMURHXLvjflSxIUXk8A8FdsaN8cIFRg/eKtFtvUeh17aj54W
# cmnGrnu3tz5q4i6tAgMBAAGjggHdMIIB2TASBgkrBgEEAYI3FQEEBQIDAQABMCMG
# CSsGAQQBgjcVAgQWBBQqp1L+ZMSavoKRPEY1Kc8Q/y8E7jAdBgNVHQ4EFgQUn6cV
# XQBeYl2D9OXSZacbUzUZ6XIwXAYDVR0gBFUwUzBRBgwrBgEEAYI3TIN9AQEwQTA/
# BggrBgEFBQcCARYzaHR0cDovL3d3dy5taWNyb3NvZnQuY29tL3BraW9wcy9Eb2Nz
# L1JlcG9zaXRvcnkuaHRtMBMGA1UdJQQMMAoGCCsGAQUFBwMIMBkGCSsGAQQBgjcU
# AgQMHgoAUwB1AGIAQwBBMAsGA1UdDwQEAwIBhjAPBgNVHRMBAf8EBTADAQH/MB8G
# A1UdIwQYMBaAFNX2VsuP6KJcYmjRPZSQW9fOmhjEMFYGA1UdHwRPME0wS6BJoEeG
# RWh0dHA6Ly9jcmwubWljcm9zb2Z0LmNvbS9wa2kvY3JsL3Byb2R1Y3RzL01pY1Jv
# b0NlckF1dF8yMDEwLTA2LTIzLmNybDBaBggrBgEFBQcBAQROMEwwSgYIKwYBBQUH
# MAKGPmh0dHA6Ly93d3cubWljcm9zb2Z0LmNvbS9wa2kvY2VydHMvTWljUm9vQ2Vy
# QXV0XzIwMTAtMDYtMjMuY3J0MA0GCSqGSIb3DQEBCwUAA4ICAQCdVX38Kq3hLB9n
# ATEkW+Geckv8qW/qXBS2Pk5HZHixBpOXPTEztTnXwnE2P9pkbHzQdTltuw8x5MKP
# +2zRoZQYIu7pZmc6U03dmLq2HnjYNi6cqYJWAAOwBb6J6Gngugnue99qb74py27Y
# P0h1AdkY3m2CDPVtI1TkeFN1JFe53Z/zjj3G82jfZfakVqr3lbYoVSfQJL1AoL8Z
# thISEV09J+BAljis9/kpicO8F7BUhUKz/AyeixmJ5/ALaoHCgRlCGVJ1ijbCHcNh
# cy4sa3tuPywJeBTpkbKpW99Jo3QMvOyRgNI95ko+ZjtPu4b6MhrZlvSP9pEB9s7G
# dP32THJvEKt1MMU0sHrYUP4KWN1APMdUbZ1jdEgssU5HLcEUBHG/ZPkkvnNtyo4J
# vbMBV0lUZNlz138eW0QBjloZkWsNn6Qo3GcZKCS6OEuabvshVGtqRRFHqfG3rsjo
# iV5PndLQTHa1V1QJsWkBRH58oWFsc/4Ku+xBZj1p/cvBQUl+fpO+y/g75LcVv7TO
# PqUxUYS8vwLBgqJ7Fx0ViY1w/ue10CgaiQuPNtq6TPmb/wrpNPgkNWcr4A245oyZ
# 1uEi6vAnQj0llOZ0dFtq0Z4+7X6gMTN9vMvpe784cETRkPHIqzqKOghif9lwY1NN
# je6CbaUFEMFxBmoQtB1VM1izoXBm8qGCA1YwggI+AgEBMIIBAaGB2aSB1jCB0zEL
# MAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1v
# bmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEtMCsGA1UECxMkTWlj
# cm9zb2Z0IElyZWxhbmQgT3BlcmF0aW9ucyBMaW1pdGVkMScwJQYDVQQLEx5uU2hp
# ZWxkIFRTUyBFU046NTIxQS0wNUUwLUQ5NDcxJTAjBgNVBAMTHE1pY3Jvc29mdCBU
# aW1lLVN0YW1wIFNlcnZpY2WiIwoBATAHBgUrDgMCGgMVAGmygBWirdoWlHapB3xW
# MwM34EjLoIGDMIGApH4wfDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjEmMCQGA1UEAxMdTWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwDQYJ
# KoZIhvcNAQELBQACBQDtnSNvMCIYDzIwMjYwNDMwMDA0MDE1WhgPMjAyNjA1MDEw
# MDQwMTVaMHQwOgYKKwYBBAGEWQoEATEsMCowCgIFAO2dI28CAQAwBwIBAAICIgkw
# BwIBAAICExswCgIFAO2edO8CAQAwNgYKKwYBBAGEWQoEAjEoMCYwDAYKKwYBBAGE
# WQoDAqAKMAgCAQACAwehIKEKMAgCAQACAwGGoDANBgkqhkiG9w0BAQsFAAOCAQEA
# VP6vJV250pLnaET9teb3mYUJVdLmMHlaVU3kOj3j/2oWUAgTgP5RENCEQh21SMSa
# pyGPKm45MGYhY8V7QJEsSicVhqETDCpFBZEC43KgQvOVSsF2zxhkeBB+vAhNCdNY
# yyQX/VM3r+F6jSBLFamyLwBUJmyulSuPp9RoymbI+GEwhnlzxUPHBdDE1Om0lAsq
# LToMnlh6iYGSwMKZprkIbAOE9J6UhT4YWHZiXmuq1P8EmRqfmj8QFNrbYVG4HATH
# RyR39IL92PdNY3vajA1Z1lvc0VbcsVM8WYBnAIpmS8orZqBd+1CTZC8xmkqBhYmp
# HFY7gRlZ9GHI7LnMEkD81DGCBA0wggQJAgEBMIGTMHwxCzAJBgNVBAYTAlVTMRMw
# EQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVN
# aWNyb3NvZnQgQ29ycG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0
# YW1wIFBDQSAyMDEwAhMzAAACF3H7LqWvAR3qAAEAAAIXMA0GCWCGSAFlAwQCAQUA
# oIIBSjAaBgkqhkiG9w0BCQMxDQYLKoZIhvcNAQkQAQQwLwYJKoZIhvcNAQkEMSIE
# IIqGCIrVNxtrHt/8ehjT03XIVIUzoyRL2oX9RYku22eXMIH6BgsqhkiG9w0BCRAC
# LzGB6jCB5zCB5DCBvQQg0PJQYD5dt8mdEs1EreaYTiHoBz8sK5DcHr8XtpPkWlsw
# gZgwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4G
# A1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSYw
# JAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0EgMjAxMAITMwAAAhdx+y6l
# rwEd6gABAAACFzAiBCBjqeuNwdxuTSkoV+3Z89xW0CdAC15qC7pmhcFXmN71RjAN
# BgkqhkiG9w0BAQsFAASCAgBJezvc2RaWpBFWWBlAobsTTtlt/p3sYup7KtOQLeI3
# EXC9MDPrGEzXPtj/iAywn+C47ctHOdtEXHgkc4WrN8Wofi0P4tEhlAlyv5iQ7OaL
# 4QriYWwUxCGKjSgRCxnBw2MLRdtJwQ2jzJH0HuG65ImA4gtflkOj733+40Bv7Hwy
# 8gpU8xcDqAtP8rS2yO/7qL+9ZTcMEXC9msAM+mmcA/XPt2yJLXFuVbbsvrxZw3D2
# dlznUasra25thWEZuW6mx4EUk9aFBeuRXlEYhStmNkEi9md+zWzErY/3IwNwNYA0
# k+6+GCjP9zuibUwcnYQgxPzkKMQMB7MrLRTN6IHNBGBGsn2CAb3qUpbeekjYtLnP
# dYnfySZQhrMPF3TfE8FnTmL2YktMf5hIuikGJz7NVBbMbdgBupuNHZH+gU8JHh3Q
# T7Y+JH/mkttEWS4IhSnRBbf5VV842FmBG0d8h2LvK/7j8l6Oanb+58QXPW9R+8Zc
# JYKrXTv98IOqUcha90a3UtvE3OHCcwA51oiQKTFng6/ctNwA3/GWjC2lf3BMQKF8
# VHJKo5v6amumxQRxUazrIoN7QvZu76IVV0jeyYd5xANo6Bg8lFNMdVy2K6DoPNp2
# 6sHQxv4ABVU0pCwWkilKo2H5/U2BKpYvCBlM+G3/5eh4Xv+KPqIKMktwX5p55l0c
# 3A==
# SIG # End Windows Authenticode signature block