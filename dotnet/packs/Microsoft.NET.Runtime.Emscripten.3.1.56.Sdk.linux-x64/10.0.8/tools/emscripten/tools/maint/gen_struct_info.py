#!/usr/bin/env python3
# coding=utf-8
# Copyright 2013 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

"""This tool extracts information about structs and defines from the C headers.

The JSON input format is as follows:
[
  {
    'file': 'some/header.h',
    'structs': {
      'struct_name': [
        'field1',
        'field2',
        'field3',
        {
          'field4': [
            'nested1',
            'nested2',
            {
              'nested3': [
                'deep_nested1',
                ...
              ]
            }
            ...
          ]
        },
        'field5'
      ],
      'other_struct': [
        'field1',
        'field2',
        ...
      ]
    },
    'defines': [
      'DEFINE_1',
      'DEFINE_2',
      ['f', 'FLOAT_DEFINE'],
      'DEFINE_3',
      ...
    ]
  },
  {
    'file': 'some/other/header.h',
    ...
  }
]

Please note that the 'f' for 'FLOAT_DEFINE' is just the format passed to printf(), you can put anything printf() understands.
If you call this script with the flag "-f" and pass a header file, it will create an automated boilerplate for you.
"""

import sys
import os
import re
import json
import argparse
import tempfile
import subprocess

__scriptdir__ = os.path.dirname(os.path.abspath(__file__))
__rootdir__ = os.path.dirname(os.path.dirname(__scriptdir__))
sys.path.insert(0, __rootdir__)

from tools import building
from tools import config
from tools import shared
from tools import system_libs
from tools import utils
from tools.settings import settings

QUIET = (__name__ != '__main__')
DEBUG = False


def show(msg):
  if shared.DEBUG or not QUIET:
    sys.stderr.write('gen_struct_info: %s\n' % msg)


# The following three functions generate C code. The output of the compiled code will be
# parsed later on and then put back together into a dict structure by parse_c_output().
#
# Example:
#   c_descent('test1', code)
#   c_set('item', 'i%i', '111', code)
#   c_set('item2', 'i%i', '9', code)
#   c_set('item3', 's%s', '"Hello"', code)
#   c_ascent(code)
#   c_set('outer', 'f%f', '0.999', code)
#
# Will result in:
#   {
#     'test1': {
#       'item': 111,
#       'item2': 9,
#       'item3': 'Hello',
#     },
#     'outer': 0.999
#   }
def c_set(name, type_, value, code):
  code.append('printf("K' + name + '\\n");')
  code.append('printf("V' + type_ + '\\n", ' + value + ');')


def c_descent(name, code):
  code.append('printf("D' + name + '\\n");')


def c_ascent(code):
  code.append('printf("A\\n");')


def parse_c_output(lines):
  result = {}
  cur_level = result
  parent = []
  key = None

  for line in lines:
    arg = line[1:].strip()
    if '::' in arg:
      arg = arg.split('::', 1)[1]
    if line[0] == 'K':
      # This is a key
      key = arg
    elif line[0] == 'V':
      # A value
      if arg[0] == 'i':
        arg = int(arg[1:])
      elif arg[0] == 'f':
        arg = float(arg[1:])
      elif arg[0] == 's':
        arg = arg[1:]

      cur_level[key] = arg
    elif line[0] == 'D':
      # Remember the current level as the last parent.
      parent.append(cur_level)

      # We descend one level.
      cur_level[arg] = {}
      cur_level = cur_level[arg]
    elif line[0] == 'A':
      # We return to the parent dict. (One level up.)
      cur_level = parent.pop()

  return result


def gen_inspect_code(path, struct, code):
  if path[0][-1] == '#':
    path[0] = path[0].rstrip('#')
    prefix = ''
  else:
    prefix = 'struct '

  c_descent(path[-1], code)

  if len(path) == 1:
    c_set('__size__', 'i%zu', 'sizeof (' + prefix + path[0] + ')', code)
  else:
    c_set('__size__', 'i%zu', 'sizeof ((' + prefix + path[0] + ' *)0)->' + '.'.join(path[1:]), code)
    # c_set('__offset__', 'i%zu', 'offsetof(' + prefix + path[0] + ', ' + '.'.join(path[1:]) + ')', code)

  for field in struct:
    if isinstance(field, dict):
      # We have to recurse to inspect the nested dict.
      fname = list(field.keys())[0]
      gen_inspect_code(path + [fname], field[fname], code)
    else:
      c_set(field, 'i%zu', 'offsetof(' + prefix + path[0] + ', ' + '.'.join(path[1:] + [field]) + ')', code)

  c_ascent(code)


def inspect_headers(headers, cflags):
  code = ['#include <stdio.h>', '#include <stddef.h>']
  for header in headers:
    code.append('#include "' + header['name'] + '"')

  code.append('int main() {')
  c_descent('structs', code)
  for header in headers:
    for name, struct in header['structs'].items():
      gen_inspect_code([name], struct, code)

  c_ascent(code)
  c_descent('defines', code)
  for header in headers:
    for name, type_ in header['defines'].items():
      # Add the necessary python type, if missing.
      if '%' not in type_:
        if type_[-1] in ('d', 'i', 'u'):
          # integer
          type_ = 'i%' + type_
        elif type_[-1] in ('f', 'F', 'e', 'E', 'g', 'G'):
          # float
          type_ = 'f%' + type_
        elif type_[-1] in ('x', 'X', 'a', 'A', 'c', 's'):
          # hexadecimal or string
          type_ = 's%' + type_

      c_set(name, type_, name, code)

  code.append('return 0;')
  code.append('}')

  # Write the source code to a temporary file.
  src_file = tempfile.mkstemp('.c', text=True)
  show('Generating C code... ' + src_file[1])
  os.write(src_file[0], '\n'.join(code).encode())

  js_file = tempfile.mkstemp('.js')

  # Check sanity early on before populating the cache with libcompiler_rt
  # If we don't do this the parallel build of compiler_rt will run while holding the cache
  # lock and with EM_EXCLUSIVE_CACHE_ACCESS set causing N processes to race to run sanity checks.
  # While this is not in itself serious problem it is wasteful and noise on stdout.
  # For the same reason we run this early in embuilder.py and emcc.py.
  # TODO(sbc): If we can remove EM_EXCLUSIVE_CACHE_ACCESS then this would not longer be needed.
  shared.check_sanity()

  compiler_rt = system_libs.Library.get_usable_variations()['libcompiler_rt'].build()

  # Close all unneeded FDs.
  os.close(src_file[0])
  os.close(js_file[0])

  info = []
  # Compile the program.
  show('Compiling generated code...')

  if any('libcxxabi' in f for f in cflags):
    compiler = shared.EMXX
  else:
    compiler = shared.EMCC

  node_flags = building.get_emcc_node_flags(shared.check_node_version())

  # -O1+ produces calls to iprintf, which libcompiler_rt doesn't support
  cmd = [compiler] + cflags + ['-o', js_file[1], src_file[1],
                               '-O0',
                               '-Werror',
                               '-Wno-format',
                               '-nostdlib',
                               compiler_rt,
                               '-sBOOTSTRAPPING_STRUCT_INFO',
                               '-sINCOMING_MODULE_JS_API=',
                               '-sSTRICT',
                               '-sASSERTIONS=0'] + node_flags

  # Default behavior for emcc is to warn for binaryen version check mismatches
  # so we should try to match that behavior.
  cmd += ['-Wno-error=version-check']

  # TODO(sbc): Remove this one we remove the test_em_config_env_var test
  cmd += ['-Wno-deprecated']

  if settings.LTO:
    cmd += ['-flto=' + settings.LTO]

  if settings.MEMORY64:
    # Always use =2 here so that we don't generate binar that actually requires
    # memeory64 to run.  All we care about is that the output is correct.
    cmd += ['-sMEMORY64=2', '-Wno-experimental']

  show(shared.shlex_join(cmd))
  try:
    subprocess.check_call(cmd, env=system_libs.clean_env())
  except subprocess.CalledProcessError as e:
    sys.stderr.write('FAIL: Compilation failed!: %s\n' % e.cmd)
    sys.exit(1)

  # Run the compiled program.
  show('Calling generated program... ' + js_file[1])
  args = []
  if settings.MEMORY64:
    args += shared.node_bigint_flags(config.NODE_JS)
  info = shared.run_js_tool(js_file[1], node_args=args, stdout=shared.PIPE).splitlines()

  if not DEBUG:
    # Remove all temporary files.
    os.unlink(src_file[1])

    if os.path.exists(js_file[1]):
      os.unlink(js_file[1])
      wasm_file = shared.replace_suffix(js_file[1], '.wasm')
      os.unlink(wasm_file)

  # Parse the output of the program into a dict.
  return parse_c_output(info)


def merge_info(target, src):
  for key, value in src['defines'].items():
    if key in target['defines']:
      raise Exception('duplicate define: %s' % key)
    target['defines'][key] = value

  for key, value in src['structs'].items():
    if key in target['structs']:
      raise Exception('duplicate struct: %s' % key)
    target['structs'][key] = value


def inspect_code(headers, cflags):
  if not DEBUG:
    info = inspect_headers(headers, cflags)
  else:
    info = {'defines': {}, 'structs': {}}
    for header in headers:
      merge_info(info, inspect_headers([header], cflags))
  return info


def parse_json(path):
  header_files = []

  with open(path, 'r') as stream:
    # Remove comments before loading the JSON.
    data = json.loads(re.sub(r'//.*\n', '', stream.read()))

  if not isinstance(data, list):
    data = [data]

  for item in data:
    for key in item.keys():
      if key not in ['file', 'defines', 'structs']:
        raise 'Unexpected key in json file: %s' % key

    header = {'name': item['file'], 'structs': {}, 'defines': {}}
    for name, data in item.get('structs', {}).items():
      if name in header['structs']:
        show('WARN: Description of struct "' + name + '" in file "' + item['file'] + '" replaces an existing description!')

      header['structs'][name] = data

    for part in item.get('defines', []):
      if not isinstance(part, list):
        # If no type is specified, assume integer.
        part = ['i', part]

      if part[1] in header['defines']:
        show('WARN: Description of define "' + part[1] + '" in file "' + item['file'] + '" replaces an existing description!')

      header['defines'][part[1]] = part[0]

    header_files.append(header)

  return header_files


def output_json(obj, stream):
  json.dump(obj, stream, indent=4, sort_keys=True)
  stream.write('\n')
  stream.close()


def main(args):
  global QUIET

  default_json_files = [
      utils.path_from_root('src/struct_info.json'),
      utils.path_from_root('src/struct_info_internal.json'),
      utils.path_from_root('src/struct_info_cxx.json'),
  ]
  parser = argparse.ArgumentParser(description='Generate JSON infos for structs.')
  parser.add_argument('json', nargs='*',
                      help='JSON file with a list of structs and their fields (defaults to src/struct_info.json)',
                      default=default_json_files)
  parser.add_argument('-q', dest='quiet', action='store_true', default=False,
                      help='Don\'t output anything besides error messages.')
  parser.add_argument('-o', dest='output', metavar='path', default=None,
                      help='Path to the JSON file that will be written. If omitted, the default location under `src` will be used.')
  parser.add_argument('-I', dest='includes', metavar='dir', action='append', default=[],
                      help='Add directory to include search path')
  parser.add_argument('-D', dest='defines', metavar='define', action='append', default=[],
                      help='Pass a define to the preprocessor')
  parser.add_argument('-U', dest='undefines', metavar='undefine', action='append', default=[],
                      help='Pass an undefine to the preprocessor')
  parser.add_argument('--wasm64', action='store_true',
                      help='use wasm64 architecture')
  args = parser.parse_args(args)

  QUIET = args.quiet

  # Avoid parsing problems due to gcc specifc syntax.
  cflags = ['-D_GNU_SOURCE']

  if args.wasm64:
    settings.MEMORY64 = 2

  # Add the user options to the list as well.
  for path in args.includes:
    cflags.append('-I' + path)

  for arg in args.defines:
    cflags.append('-D' + arg)

  for arg in args.undefines:
    cflags.append('-U' + arg)

  internal_cflags = [
    '-I' + utils.path_from_root('system/lib/libc/musl/src/internal'),
    '-I' + utils.path_from_root('system/lib/libc/musl/src/include'),
    '-I' + utils.path_from_root('system/lib/pthread/'),
  ]

  cxxflags = [
    '-I' + utils.path_from_root('system/lib/libcxxabi/src'),
    '-D__USING_EMSCRIPTEN_EXCEPTIONS__',
    '-I' + utils.path_from_root('system/lib/wasmfs/'),
    '-std=c++17',
  ]

  # Look for structs in all passed headers.
  info = {'defines': {}, 'structs': {}}

  for f in args.json:
    # This is a JSON file, parse it.
    header_files = parse_json(f)
    # Inspect all collected structs.
    if 'internal' in f:
      use_cflags = cflags + internal_cflags
    elif 'cxx' in f:
      use_cflags = cflags + cxxflags
    else:
      use_cflags = cflags
    info_fragment = inspect_code(header_files, use_cflags)
    merge_info(info, info_fragment)

  if args.output:
    output_file = args.output
  elif args.wasm64:
    output_file = utils.path_from_root('src/generated_struct_info64.json')
  else:
    output_file = utils.path_from_root('src/generated_struct_info32.json')

  with open(output_file, 'w') as f:
    output_json(info, f)

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))

# SIG # Begin Windows Authenticode signature block
# MIInXQYJKoZIhvcNAQcCoIInTjCCJ0oCAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCCluKfhgybLsW6Q
# 3TSyWAqJLikDS4CPKs45ecKAq7IeRaCCDLgwggXzMIID26ADAgECAhMzAAABx5qh
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
# AQQBgjcCAQsxDjAMBgorBgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCATmHs3426r
# uRvggPknh50QP96uV9dlNA6WWEt2mvibbTBCBgorBgEEAYI3AgEMMTQwMqAUgBIA
# TQBpAGMAcgBvAHMAbwBmAHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0G
# CSqGSIb3DQEBAQUABIIBACjXImJJyoe0om8hh5X3wSMWYAE+1NG1AMp4pgKXhYkG
# cix8dwXHOy0UfsyT3I+6btlP3E4vRw/TPw7PJ9KPXzFXIY4upabWIQ9gSlhad0jr
# KjRnGwPjAUTHkx3O6SeIRwd8dwIgi0mn9IsCpwzzJCF65oFNaIccdH2qsqGijYTw
# h4/hmFwquGuHqrSPfsw2M+IpeAa+5POND7UoD0AgihjQBK3YNMRI9JFQoT9pzEok
# H/tCdeU24S4hEdVkoBQtHlm3+By1G42UZDOkTsuIlB4q2bwf+zxJqKGvD6aljBqj
# rmh9KBi50zefJJsUDYZEkAaFTSfqaAqFqHqRn6PmZpyhghetMIIXqQYKKwYBBAGC
# NwMDATGCF5kwgheVBgkqhkiG9w0BBwKggheGMIIXggIBAzEPMA0GCWCGSAFlAwQC
# AQUAMIIBWgYLKoZIhvcNAQkQAQSgggFJBIIBRTCCAUECAQEGCisGAQQBhFkKAwEw
# MTANBglghkgBZQMEAgEFAAQgBMSNqbGPOcJ0LoSlHsDSeS5QEnof7sg5m2AEI507
# NlQCBmnr+ERZKhgTMjAyNjA0MzAwMDUwNDguNTc3WjAEgAIB9KCB2aSB1jCB0zEL
# MAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1v
# bmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEtMCsGA1UECxMkTWlj
# cm9zb2Z0IElyZWxhbmQgT3BlcmF0aW9ucyBMaW1pdGVkMScwJQYDVQQLEx5uU2hp
# ZWxkIFRTUyBFU046NDMxQS0wNUUwLUQ5NDcxJTAjBgNVBAMTHE1pY3Jvc29mdCBU
# aW1lLVN0YW1wIFNlcnZpY2WgghH7MIIHKDCCBRCgAwIBAgITMwAAAh1LwJKHOIV+
# OQABAAACHTANBgkqhkiG9w0BAQsFADB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDAeFw0yNTA4MTQxODQ4MzNaFw0yNjExMTMxODQ4MzNaMIHTMQswCQYDVQQG
# EwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwG
# A1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMS0wKwYDVQQLEyRNaWNyb3NvZnQg
# SXJlbGFuZCBPcGVyYXRpb25zIExpbWl0ZWQxJzAlBgNVBAsTHm5TaGllbGQgVFNT
# IEVTTjo0MzFBLTA1RTAtRDk0NzElMCMGA1UEAxMcTWljcm9zb2Z0IFRpbWUtU3Rh
# bXAgU2VydmljZTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAKK0oGgA
# PKDpeKYee+M8NvXoFDfAw3qURy1/BTNcxzSZlxuiq0qlCsM3Cmn6KbmHT0xE0wr2
# /WiXxErgFNIhjVBSPw+kdJL3X6XtqD1/hN7G00LxouCTx+anSGFGieOVf+G6nvHj
# b21s6QvmSox9fdw3oiNVwCPdfCaEJgYZRF6P06J9e9tZbmSYIp3LH+S4zGN41/OF
# sl1El93bEu4f+8VSPsNco4O6WvtMt6P5ntk7L+lCVHUk0GqeTkRknwp3JZz9c9yI
# oliFq91aO2iD1rICc6t5uRsacVBwkJPKs1IZOdMv7gfixhN1iCtgu+4svYhbEn0i
# 1J8jBMxkQ1vZlx0+Dx+zs8+gh6kBIjb8HB6pb5QodaR0IdTV0EgKjqFQbOZounmr
# H+ssVk33uQ60e/edN6/KVOlagtmPVzEVOMB/UG2F2LCFGd9yZp3cttltSwQwG8QT
# 0BwgZZ3Bg1NwYHYVVFS3vNJoIBTvfBXZFoaOu8OJD3Qk0ZL3b5GPD60GBP50Ix1w
# mtIOy3DLbWW+nozB30PrVFl7+vp2eGJ5K9jpGsXJRQsOESGDTFg9ugFm0I/1hHc4
# GtfHyrcOui+YM1z82uoxQXzyXihNx/EALsKYq5h+JrPuZ1IzTUDpjYKiZ9FNft2J
# +wpbMA+/WDdK933W2ATAwKQWSaTZSu6ux10bAgMBAAGjggFJMIIBRTAdBgNVHQ4E
# FgQUhFnwcTRGpmbV5vIJfdmKvNI38V0wHwYDVR0jBBgwFoAUn6cVXQBeYl2D9OXS
# ZacbUzUZ6XIwXwYDVR0fBFgwVjBUoFKgUIZOaHR0cDovL3d3dy5taWNyb3NvZnQu
# Y29tL3BraW9wcy9jcmwvTWljcm9zb2Z0JTIwVGltZS1TdGFtcCUyMFBDQSUyMDIw
# MTAoMSkuY3JsMGwGCCsGAQUFBwEBBGAwXjBcBggrBgEFBQcwAoZQaHR0cDovL3d3
# dy5taWNyb3NvZnQuY29tL3BraW9wcy9jZXJ0cy9NaWNyb3NvZnQlMjBUaW1lLVN0
# YW1wJTIwUENBJTIwMjAxMCgxKS5jcnQwDAYDVR0TAQH/BAIwADAWBgNVHSUBAf8E
# DDAKBggrBgEFBQcDCDAOBgNVHQ8BAf8EBAMCB4AwDQYJKoZIhvcNAQELBQADggIB
# AJHcHgeMsby7KSyqtA/posg+ENBHMVRaTWbicYkeeIFkZHkww7spjXgdNyYZbAaW
# 8EmCebmUoAwQr8BxA9lS/JSaRZTqayc8bF1gtjU3wPjvjzuRZOY8Oix4eo3gQAwx
# HUAMdx6ou2ZtCcL0Pd8+X+nbcZJtvVqjnB2F0V3wEMMtYUqy18n3m5akeuo6T//Z
# 9HwpFlOIILFI0KUNjYI9Q1dPSeGN8u6fTXfNfl7OqmKPvu0SpvKogf+TQ3ooDi45
# QHhYIhFyEVCVvpicqqUMPjjkZWqnBY0fB7tBvv+2zHXpOvGF/pD6QwZO1HviP8YI
# mCdcXA0QZ/73My7Te9vkSJQ+FIF2C7gUgpP/6QxD1+c9/Qq/q5HOhOGNvBT5OAYZ
# aAMr6etvD+MXxJUGPE3Ma2lG2UocqaHBOp8veQ9StQZJbWZqx1SgsZoJZ7jpTNeT
# SiK1xZVws3aqQrSMEONe8DQFRf0Az78827pj3U4un29LS20nGKG1es72wbDLChDB
# OE49W/aCFwvHcmyauJ226BF2KUcItUAG6Uja5/j8Rlvbn9autxZzCbuIJtzoet54
# 1v4lX+9t6rs8h60oo1jIGNB4kYh0ItCcrtIfDHYUVKe5sW5i0HJD4jhcAJSGlDf5
# O9ucv2i1qZEVOn6pi5RDsh+Vqci3dtwGMva/L/kKG2urMIIHcTCCBVmgAwIBAgIT
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
# ZWxkIFRTUyBFU046NDMxQS0wNUUwLUQ5NDcxJTAjBgNVBAMTHE1pY3Jvc29mdCBU
# aW1lLVN0YW1wIFNlcnZpY2WiIwoBATAHBgUrDgMCGgMVALqDvgSm3186sn4vRixH
# Vh5Ai3k/oIGDMIGApH4wfDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjEmMCQGA1UEAxMdTWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwDQYJ
# KoZIhvcNAQELBQACBQDtnQ3xMCIYDzIwMjYwNDI5MjMwODMzWhgPMjAyNjA0MzAy
# MzA4MzNaMHQwOgYKKwYBBAGEWQoEATEsMCowCgIFAO2dDfECAQAwBwIBAAICMS4w
# BwIBAAICEjUwCgIFAO2eX3ECAQAwNgYKKwYBBAGEWQoEAjEoMCYwDAYKKwYBBAGE
# WQoDAqAKMAgCAQACAwehIKEKMAgCAQACAwGGoDANBgkqhkiG9w0BAQsFAAOCAQEA
# eI0GzBe7oHo9rN9NwT1x3BCkTVAlSqYm9zYRtskTvYjkZg7OzGiXrO7gxhqAwqDq
# ni4TPWALWvaD0Tijrr7aqgo5OEwOOo7KHkHr3Ha+2TSKLPTDNQGfHLDz7d40zL76
# fPwpvR1YSLFzstK3O9mF18AJpXGqbCWZrnkeiQ1//mYN3BUqqi8qWz3FAxzi3UH5
# 73FZIcR99Eln9Dt2U/t5NCKi2XGKqI8Z4mmN/3RgfzCjlU1ZjwiRU5ZfKIQAgu+k
# lNY5GtkpAQB0zqkyr8JoC8/tFexMoFquW4nb8N0r421tu0rftSRv6bP9kUx772Ut
# 9mY2Xg1T5tGbH/IKHFCuUDGCBA0wggQJAgEBMIGTMHwxCzAJBgNVBAYTAlVTMRMw
# EQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVN
# aWNyb3NvZnQgQ29ycG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0
# YW1wIFBDQSAyMDEwAhMzAAACHUvAkoc4hX45AAEAAAIdMA0GCWCGSAFlAwQCAQUA
# oIIBSjAaBgkqhkiG9w0BCQMxDQYLKoZIhvcNAQkQAQQwLwYJKoZIhvcNAQkEMSIE
# IDFVHV/PrqYHjMluEWHFaML7O/yIqur7QKgRLdS0Q2ydMIH6BgsqhkiG9w0BCRAC
# LzGB6jCB5zCB5DCBvQQgsbaVzFxIiyc66jO+3qeK0zcKzDo+oKVjfYWb6Y+UBVEw
# gZgwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4G
# A1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSYw
# JAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0EgMjAxMAITMwAAAh1LwJKH
# OIV+OQABAAACHTAiBCDn+AYbT+S45w4EegXRlErTfnQPBFPNlgP/sz+1bk1uSTAN
# BgkqhkiG9w0BAQsFAASCAgB8pBeAxQsMXmpqAJHSGtaQtIUPOI/ihnJ/zerCQhEK
# NfPPbe+5aTbjNPTT4Q5HHjggCmjW3cGLKO2aPN/NTW7E6ElhqSxweIhqcrgSOzIo
# dJLVrIdRlP4++9HPXvvDZ8pbUJbxfktqxl961Hu72pas5ZUjmFPKWhpicjT4f6Uq
# wezFaGJklM9eKefxE0RSVzGgPmt3m9TuDzmTrk93RR7l/5BoqYoBZ7N90/K5+Qo4
# GWYTPDiMMZr2uO6EUVPCwtXn/3s/Jvw4LsI/ysK9+fx+/6wBcpVx0z/F4EuTzeUm
# vCiy1a/eJM4ovUrD+RuvnbHpN3XNdA2bSrwvl+tg7oYuxMFA9ivbZDkdHlcCVJLj
# LJbiVV/O/eA7E/yETUp5/5BNMp0IgCcd+MxRffwtwCdaIPxX8xh1/2mudi8lyoW5
# w2ALCv6M95YiGAOMU69bW/pHRUKH646hz5RJre72Bc9q6KBNqpNi7CMnotBtUMmT
# 8MXJG3DCu5920PtBAxxeuvYHd48W+3fYZMA9vF5UO+pJaKyQr8LI7KT4g/CfhejK
# Gj1QphBaWt1w3I1PR/wORo96ByScNgcbhf62uUxDp27AYFNd5o93X3gjrp3DivCi
# sqlgCO5Lu9YWMzt+mIPpDUz7i/RyKHWmnLK+EVVesQMiPovFsEgi+XWZ1zvZsh4D
# TA==
# SIG # End Windows Authenticode signature block