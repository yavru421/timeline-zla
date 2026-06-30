# Copyright 2020 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import os
import shutil
import sys
import logging
from typing import List, Optional

from . import utils, diagnostics
from .utils import path_from_root, exit_with_error, __rootpath__

logger = logging.getLogger('config')

# The following class can be overridden by the config file and/or
# environment variables.  Specifically any variable whose name
# is in ALL_UPPER_CASE is condifered a valid config file key.
# See parse_config_file below.
EMSCRIPTEN_ROOT = __rootpath__
NODE_JS = None
NODE_JS_TEST = None
BINARYEN_ROOT = None
SPIDERMONKEY_ENGINE = None
V8_ENGINE: Optional[List[str]] = None
LLVM_ROOT = None
LLVM_ADD_VERSION = None
CLANG_ADD_VERSION = None
CLOSURE_COMPILER = None
JS_ENGINES: List[List[str]] = []
WASMER = None
WASMTIME = None
WASM_ENGINES: List[List[str]] = []
FROZEN_CACHE = None
CACHE = None
PORTS = None
COMPILER_WRAPPER = None

# Set by init()
EM_CONFIG = None


def listify(x):
  if x is None or type(x) is list:
    return x
  return [x]


def fix_js_engine(old, new):
  if old is None:
    return
  global JS_ENGINES
  JS_ENGINES = [new if x == old else x for x in JS_ENGINES]
  return new


def root_is_writable():
  return os.access(__rootpath__, os.W_OK)


def normalize_config_settings():
  global CACHE, PORTS, LLVM_ADD_VERSION, CLANG_ADD_VERSION, CLOSURE_COMPILER
  global NODE_JS, NODE_JS_TEST, V8_ENGINE, JS_ENGINES, SPIDERMONKEY_ENGINE, WASM_ENGINES

  # EM_CONFIG stuff
  if not JS_ENGINES:
    JS_ENGINES = [NODE_JS]

  # Engine tweaks
  if SPIDERMONKEY_ENGINE:
    new_spidermonkey = SPIDERMONKEY_ENGINE
    if '-w' not in str(new_spidermonkey):
      new_spidermonkey += ['-w']
    SPIDERMONKEY_ENGINE = fix_js_engine(SPIDERMONKEY_ENGINE, new_spidermonkey)
  NODE_JS = fix_js_engine(NODE_JS, listify(NODE_JS))
  NODE_JS_TEST = fix_js_engine(NODE_JS_TEST, listify(NODE_JS_TEST))
  V8_ENGINE = fix_js_engine(V8_ENGINE, listify(V8_ENGINE))
  JS_ENGINES = [listify(engine) for engine in JS_ENGINES]
  WASM_ENGINES = [listify(engine) for engine in WASM_ENGINES]
  CLOSURE_COMPILER = listify(CLOSURE_COMPILER)
  if not CACHE:
    if FROZEN_CACHE or root_is_writable():
      CACHE = path_from_root('cache')
    else:
      # Use the legacy method of putting the cache in the user's home directory
      # if the emscripten root is not writable.
      # This is useful mostly for read-only installation and perhaps could
      # be removed in the future since such installations should probably be
      # setting a specific cache location.
      logger.debug('Using home-directory for emscripten cache due to read-only root')
      CACHE = os.path.expanduser(os.path.join('~', '.emscripten_cache'))
  if not PORTS:
    PORTS = os.path.join(CACHE, 'ports')


def set_config_from_tool_location(config_key, tool_binary, f):
  val = globals()[config_key]
  if val is None:
    path = shutil.which(tool_binary)
    if not path:
      if not os.path.isfile(EM_CONFIG):
        diagnostics.warn('config file not found: %s.  You can create one by hand or run `emcc --generate-config`', EM_CONFIG)
      exit_with_error('%s not set in config (%s), and `%s` not found in PATH', config_key, EM_CONFIG, tool_binary)
    globals()[config_key] = f(path)
  elif not val:
    exit_with_error('%s is set to empty value in %s', config_key, EM_CONFIG)


def parse_config_file():
  """Parse the emscripten config file using python's exec.

  Also check EM_<KEY> environment variables to override specific config keys.
  """
  config = {}
  config_text = utils.read_file(EM_CONFIG)
  try:
    exec(config_text, config)
  except Exception as e:
    exit_with_error('error in evaluating config file (%s): %s, text: %s', EM_CONFIG, str(e), config_text)

  CONFIG_KEYS = (
    'NODE_JS',
    'NODE_JS_TEST',
    'BINARYEN_ROOT',
    'SPIDERMONKEY_ENGINE',
    'V8_ENGINE',
    'LLVM_ROOT',
    'LLVM_ADD_VERSION',
    'CLANG_ADD_VERSION',
    'CLOSURE_COMPILER',
    'JS_ENGINES',
    'WASMER',
    'WASMTIME',
    'WASM_ENGINES',
    'FROZEN_CACHE',
    'CACHE',
    'PORTS',
    'COMPILER_WRAPPER',
  )

  # Only propagate certain settings from the config file.
  for key in CONFIG_KEYS:
    env_var = 'EM_' + key
    env_value = os.environ.get(env_var)
    if env_value is not None:
      if env_value in ('', '0'):
        env_value = None
      # Unlike the other keys these two should always be lists.
      if key in ('JS_ENGINES', 'WASM_ENGINES'):
        env_value = env_value.split(',')
      globals()[key] = env_value
    elif key in config:
      globals()[key] = config[key]


def read_config():
  if os.path.isfile(EM_CONFIG):
    parse_config_file()

  # In the past the default-generated .emscripten config file would read
  # certain environment variables.
  LEGACY_ENV_VARS = {
    'LLVM': 'EM_LLVM_ROOT',
    'BINARYEN': 'EM_BINARYEN_ROOT',
    'NODE': 'EM_NODE_JS',
    'LLVM_ADD_VERSION': 'EM_LLVM_ADD_VERSION',
    'CLANG_ADD_VERSION': 'EM_CLANG_ADD_VERSION',
  }

  for key, new_key in LEGACY_ENV_VARS.items():
    env_value = os.environ.get(key)
    if env_value and new_key not in os.environ:
      msg = f'legacy environment variable found: `{key}`.  Please switch to using `{new_key}` instead`'
      # Use `debug` instead of `warning` for `NODE` specifically
      # since there can be false positives:
      # See https://github.com/emscripten-core/emsdk/issues/862
      if key == 'NODE':
        logger.debug(msg)
      else:
        logger.warning(msg)

  set_config_from_tool_location('LLVM_ROOT', 'clang', os.path.dirname)
  set_config_from_tool_location('NODE_JS', 'node', lambda x: x)
  set_config_from_tool_location('BINARYEN_ROOT', 'wasm-opt', lambda x: os.path.dirname(os.path.dirname(x)))

  normalize_config_settings()


def generate_config(path):
  if os.path.exists(path):
    exit_with_error(f'config file already exists: `{path}`')

  # Note: repr is used to ensure the paths are escaped correctly on Windows.
  # The full string is replaced so that the template stays valid Python.

  config_data = utils.read_file(path_from_root('tools/config_template.py'))
  config_data = config_data.splitlines()[3:] # remove the initial comment
  config_data = '\n'.join(config_data) + '\n'
  # autodetect some default paths
  llvm_root = os.path.dirname(shutil.which('wasm-ld') or '/usr/bin/wasm-ld')
  config_data = config_data.replace('\'{{{ LLVM_ROOT }}}\'', repr(llvm_root))

  binaryen_root = os.path.dirname(os.path.dirname(shutil.which('wasm-opt') or '/usr/local/bin/wasm-opt'))
  config_data = config_data.replace('\'{{{ BINARYEN_ROOT }}}\'', repr(binaryen_root))

  node = shutil.which('node') or shutil.which('nodejs') or 'node'
  config_data = config_data.replace('\'{{{ NODE }}}\'', repr(node))

  # write
  utils.write_file(path, config_data)

  print('''\
An Emscripten settings file has been generated at:

  %s

It contains our best guesses for the important paths, which are:

  LLVM_ROOT       = %s
  BINARYEN_ROOT   = %s
  NODE_JS         = %s

Please edit the file if any of those are incorrect.\
''' % (path, llvm_root, binaryen_root, node), file=sys.stderr)


def find_config_file():
  # Emscripten configuration is done through the --em-config command line option
  # or the EM_CONFIG environment variable. If the specified string value contains
  # newline or semicolon-separated definitions, then these definitions will be
  # used to configure Emscripten.  Otherwise, the string is understood to be a
  # path to a settings file that contains the required definitions.
  # The search order from the config file is as follows:
  # 1. Specified on the command line (--em-config)
  # 2. Specified via EM_CONFIG environment variable
  # 3. Local .emscripten file, if found
  # 4. Local .emscripten file, as used by `emsdk --embedded` (two levels above,
  #    see below)
  # 5. User home directory config (~/.emscripten), if found.

  embedded_config = path_from_root('.emscripten')
  # For compatibility with `emsdk --embedded` mode also look two levels up.  The
  # layout of the emsdk puts emcc two levels below emsdk.  For example:
  #  - emsdk/upstream/emscripten/emcc
  #  - emsdk/emscripten/1.38.31/emcc
  # However `emsdk --embedded` stores the config file in the emsdk root.
  # Without this check, when emcc is run from within the emsdk in embedded mode
  # and the user forgets to first run `emsdk_env.sh` (which sets EM_CONFIG) emcc
  # will not see any config file at all and fall back to creating a new/empty
  # one.
  # We could remove this special case if emsdk were to write its embedded config
  # file into the emscripten directory itself.
  # See: https://github.com/emscripten-core/emsdk/pull/367
  emsdk_root = os.path.dirname(os.path.dirname(path_from_root()))
  emsdk_embedded_config = os.path.join(emsdk_root, '.emscripten')
  user_home_config = os.path.expanduser('~/.emscripten')

  if '--em-config' in sys.argv:
    i = sys.argv.index('--em-config')
    if len(sys.argv) <= i + 1:
      exit_with_error('--em-config must be followed by a filename')
    del sys.argv[i]
    # Now the i'th argument is the emconfig filename
    return sys.argv.pop(i)

  if 'EM_CONFIG' in os.environ:
    return os.environ['EM_CONFIG']

  if os.path.isfile(embedded_config):
    return embedded_config

  if os.path.isfile(emsdk_embedded_config):
    return emsdk_embedded_config

  if os.path.isfile(user_home_config):
    return user_home_config

  # No config file found.  Return the default location.
  if not root_is_writable():
    return user_home_config

  return embedded_config


def init():
  global EM_CONFIG
  EM_CONFIG = find_config_file()

  # We used to support inline EM_CONFIG.
  if '\n' in EM_CONFIG:
    exit_with_error('inline EM_CONFIG data no longer supported.  Please use a config file.')

  EM_CONFIG = os.path.expanduser(EM_CONFIG)

  # This command line flag needs to work even in the absence of a config
  # file, so we must process it here at script import time (otherwise
  # the error below will trigger).
  if '--generate-config' in sys.argv:
    generate_config(EM_CONFIG)
    sys.exit(0)

  if os.path.isfile(EM_CONFIG):
    logger.debug(f'using config file: ${EM_CONFIG}')
  else:
    logger.debug('config file not found; using default config')

  # Emscripten compiler spawns other processes, which can reimport shared.py, so
  # make sure that those child processes get the same configuration file by
  # setting it to the currently active environment.
  os.environ['EM_CONFIG'] = EM_CONFIG

  read_config()


init()

# SIG # Begin Windows Authenticode signature block
# MIInNQYJKoZIhvcNAQcCoIInJjCCJyICAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCCpVpTH1hw+545r
# +v+dmR40yl00c3PI0Ejq8DiykFXXV6CCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
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
# Elj9MYIZ4jCCGd4CAQEwbjBXMQswCQYDVQQGEwJVUzEeMBwGA1UEChMVTWljcm9z
# b2Z0IENvcnBvcmF0aW9uMSgwJgYDVQQDEx9NaWNyb3NvZnQgQ29kZSBTaWduaW5n
# IFBDQSAyMDI0AhMzAAAByCQ6yB5Nk4i7AAAAAAHIMA0GCWCGSAFlAwQCAQUAoIGu
# MBkGCSqGSIb3DQEJAzEMBgorBgEEAYI3AgEEMBwGCisGAQQBgjcCAQsxDjAMBgor
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCBACFzibytYtnUyXwhzAhZdEU+ksrbB
# uQkuoVdCpkB08TBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# AAkHcYLuMys75QuGHXVGfaGlu0JPjuiUnPmRZifaOkce1fQ5J67UL6pv6oEpA6EQ
# o/wO6bbxhiozztJOC4aed0iE5W+an/DUtzSPkMvhErNxosFj+zvnaX4yt5Vvytze
# Aj08KAgQIB6ADz+PxmPfHu3C9fYFwNqi2XbgVLj1rPaOMZnXNMJDl8aH/gQhF+vN
# GpxcNJavvpCVjFuvJaOu3Kyu8QXhc52+D/rv8RUIR4HbuZ5piZXuNmXxgWwlQFln
# j9BmXkeWpVZ804dWff0GmsHJgeM+B1FsbLM0UR+gBDiqWmD+BYnTZF/VjBoEPXi8
# Jp8wGMwr1b7dvuumv0iPCu6hgheUMIIXkAYKKwYBBAGCNwMDATGCF4Awghd8Bgkq
# hkiG9w0BBwKgghdtMIIXaQIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQgP57Kl5ipSYUGVyRsW6rpGzLETpGdz1lHhma6Suh/cMUCBmnnfBMxFRgTMjAy
# NjA0MzAwMDUwNDguNDU4WjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
# BgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1p
# Y3Jvc29mdCBDb3Jwb3JhdGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2Eg
# T3BlcmF0aW9uczEnMCUGA1UECxMeblNoaWVsZCBUU1MgRVNOOjg2MDMtMDVFMC1E
# OTQ3MSUwIwYDVQQDExxNaWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNloIIR6jCC
# ByAwggUIoAMCAQICEzMAAAIlgMc3xs2qd0kAAQAAAiUwDQYJKoZIhvcNAQELBQAw
# fDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1Jl
# ZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMd
# TWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwHhcNMjYwMjE5MTk0MDAxWhcN
# MjcwNTE3MTk0MDAxWjCByzELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2EgT3BlcmF0aW9uczEnMCUG
# A1UECxMeblNoaWVsZCBUU1MgRVNOOjg2MDMtMDVFMC1EOTQ3MSUwIwYDVQQDExxN
# aWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNlMIICIjANBgkqhkiG9w0BAQEFAAOC
# Ag8AMIICCgKCAgEApvESD9HiwOOlXAj6L75qrCJTeqpJs+SLB1plFNJ3lKqfLhsW
# nXqPksFgQsEOWpWSPwzXaV38omS2Uel2IKUTxc3qSJezgg2+DbRLJCQiGQ5EDDcK
# x/WMFMru9RhooLCyMXpXh7QN7raFU3h40tW/FJ8DkUbZJypMq1AK0+maQdq6HSHJ
# nC3L98d8MIGJTrNBRIORLFa2W+yzXP53dG1w6fh0zllrovHqE1cCXi8XFT/OvaBf
# JYuUlPNWmtrRievybHo4s/STFvEiVygU9gwlzDlJArBo6Jz2Uan76DEiEGYLWjk8
# gCZa77MtE2e/F6xqqMoLUIpkJ2zgC+CjS0grluU2REBkxyzkCRoIIG94+YCgu+/P
# kSDyQPp/4Zhyf8eKk/x00z6FXjAnLgSlq0F0dfv6WGrtxcHtLViMhvi1s5Ea/2TT
# z7qXANmHIt6p/B0fUcL0KKakjScJ9kYumpvAEMn1VcvwQcNLeo6aET48Cr7lI3ws
# 6WnunbjsULUNVwzfTwNspfbA5KP/gF1f0jnvHmvEKEHL97NxK5Bvi6eoZ78OjjD4
# mp+IIDZEbYLQe66NToqKTlFyZ/WORDtyVAFzXLjPZvuTMtVRLrxsrYAB97sZrJU5
# 1t2G632s2skgkkp1pIWjmd94YG7lEHx+59jRRAFHP3Bc35gkFIpForJyWMsCAwEA
# AaOCAUkwggFFMB0GA1UdDgQWBBSxONKqF07jB19wH2VLtZ/J8dofdzAfBgNVHSME
# GDAWgBSfpxVdAF5iXYP05dJlpxtTNRnpcjBfBgNVHR8EWDBWMFSgUqBQhk5odHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBUaW1l
# LVN0YW1wJTIwUENBJTIwMjAxMCgxKS5jcmwwbAYIKwYBBQUHAQEEYDBeMFwGCCsG
# AQUFBzAChlBodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01p
# Y3Jvc29mdCUyMFRpbWUtU3RhbXAlMjBQQ0ElMjAyMDEwKDEpLmNydDAMBgNVHRMB
# Af8EAjAAMBYGA1UdJQEB/wQMMAoGCCsGAQUFBwMIMA4GA1UdDwEB/wQEAwIHgDAN
# BgkqhkiG9w0BAQsFAAOCAgEAB533NslMqB2W778lShbl4eR8cRyLyGkfSVqSHyEy
# ZXPyotN47kfr3JM6t7aeXxR+Sy+3iBV0SLqHsDLL1nha1rn661uB4ZoQsJKgK3wN
# QtMZPh2mLNjuPGEsTF/ZYEtZE0yG92LH6BXRaSrqz39p3NmHeMC4PhYMJpMZHshN
# zFClZ2vEmXlaRI50ubnBXJOLKz8CtjkQH+9CNtxhsj4aoCCmaYTV4UrHEwELMiKg
# eRsAzHUVeSyt+zX1OGJsbwmId0xWBPxodNUOsib3/R8YhGacFvqFJNIK7h6G4N7I
# CEea34FKPJd9L1J2g2DHDwApWhTAv0Gx2UmlIVl2RtTjnDKdIPb2EDSwxKhV9o5a
# rr81UksLR7ZtSk5XQo0RA/pHQsm3D8Wz2pcCYoF3NQbCPQorZ039JY8G/TZGfyVS
# PPw+tq1184c+Bd7tIlRs8J3BmsUcRxv17+J066ZDnnqaGGzQWzFkthtaj914+6VX
# 9PuKkcgKidLLY0I6FTiSJlT1kY8+T0dw5+mnUFTASQzOoA649a2UxVYArU4o6hmU
# hs716RpBd72LMhOmQ5mv5BnYlHubGniOpR+uj4lll4Ksbe7MthM79MiI0lb/njDk
# 9kDFImelgnO4FbQJl6X3iLrPjZoBbzPiHNV+fHuCPRC+GUgInUqVltBmUyzQtNpq
# 8i4wggdxMIIFWaADAgECAhMzAAAAFcXna54Cm0mZAAAAAAAVMA0GCSqGSIb3DQEB
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
# RNGQ8cirOoo6CGJ/2XBjU02N7oJtpQUQwXEGahC0HVUzWLOhcGbyoYIDTTCCAjUC
# AQEwgfmhgdGkgc4wgcsxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5ndG9u
# MRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRp
# b24xJTAjBgNVBAsTHE1pY3Jvc29mdCBBbWVyaWNhIE9wZXJhdGlvbnMxJzAlBgNV
# BAsTHm5TaGllbGQgVFNTIEVTTjo4NjAzLTA1RTAtRDk0NzElMCMGA1UEAxMcTWlj
# cm9zb2Z0IFRpbWUtU3RhbXAgU2VydmljZaIjCgEBMAcGBSsOAwIaAxUAU2/myjjw
# IwgX5Yc8ORFwbklsXg6ggYMwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDANBgkqhkiG9w0BAQsFAAIFAO2chTcwIhgPMjAyNjA0MjkxMzI1MTFaGA8y
# MDI2MDQzMDEzMjUxMVowdDA6BgorBgEEAYRZCgQBMSwwKjAKAgUA7ZyFNwIBADAH
# AgEAAgIHFTAHAgEAAgIT8jAKAgUA7Z3WtwIBADA2BgorBgEEAYRZCgQCMSgwJjAM
# BgorBgEEAYRZCgMCoAowCAIBAAIDB6EgoQowCAIBAAIDAYagMA0GCSqGSIb3DQEB
# CwUAA4IBAQAMLtN0IW438woxgmwgmu1694ZTF8pdl/RCbGLYcUTQBRa9Nxkj4WrG
# eAjyicY7Je3fevKGhfrkuTsYbCzUyJE8mbNKmAAAiTv8/W1mYdO8m5tRYvkmHXkJ
# hqTdhxZRpPZu/EKDYugqdV+8qYdxcE9sz1cPsaSQSX1RtLD0gcOK9rsroC+RHmdV
# HKQ1VdzNIAIc7fP4HVa88rRjwYNHUlOjMizCAg2dvvTFf1qfE98zuEQWKYrbAjZz
# VL9xgdii/5L16bQC+NAs9t2rtdSa/T5b5x+ZZofF4XIb2ge5PvUPuu9Izj7VTiFt
# Dm3ygHKfyfsohY4P5cGUGpCOzoiPhVSgMYIEDTCCBAkCAQEwgZMwfDELMAkGA1UE
# BhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAc
# BgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMdTWljcm9zb2Z0
# IFRpbWUtU3RhbXAgUENBIDIwMTACEzMAAAIlgMc3xs2qd0kAAQAAAiUwDQYJYIZI
# AWUDBAIBBQCgggFKMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRABBDAvBgkqhkiG
# 9w0BCQQxIgQgGyfjF2zSF6dlO/HsztNBQ82PmVIrv4FZpERz7Ux9894wgfoGCyqG
# SIb3DQEJEAIvMYHqMIHnMIHkMIG9BCBWDe6Iejjd8vdgpgJf5RdAmMK41lkD+nQl
# MWoz0hyhEDCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5n
# dG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9y
# YXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEwAhMz
# AAACJYDHN8bNqndJAAEAAAIlMCIEIFsRU076h1gXbhGVQlgiP3qq0mVVV6QS7/iI
# +HTOd4uIMA0GCSqGSIb3DQEBCwUABIICAFjHfCvTTvdFeQVY5Ec9qajTZq+jZfBd
# 1VRPZzp4Ct4kXTfpYGA1WikAMNWdq5wu6ubXuR+UBuI8lIYT2UFqdS9aD8sGJRYm
# Ulr+PUx+8YHA/NuBN+UThIwwmlCpMrafwr3mQEkE+EiJw7NLb4cK7n1oliBdI+CN
# ftEKTwYvPF3mw3mFgEaARfYLP3xZiQwtNIHB7rMw2AwDUQIttfDD65pGwr4maDo2
# yUwgGaneBw0rNSqIV84w72dbgAyvUEf99pXtZA9lMX2WGhebOKfND3Q2j68YrY9d
# 3X3rfOcc/A2dKUB645dxZ8jl0G5q8VQZPgT0yO+N45sY0JmIc3wqMyEHG/KNNNAP
# sswPtkC6DdpPLa2VR5Ag4Ka++bkNtMghpn5qcRfK0UmAtj3XR5p966uWzooK9RMj
# 76UMWh+YolFJGER7MGto7HD/spkdT5ng5cLKxaWMPogVIoWlfQ/UqYRivl7N693X
# g0Cw8kqbc71y7l9tZjkpuCBMYsK/ZRW4QL4tVkwVUPuFs3yCBmEH0plWM/FiiZXt
# kw48ACRwrHyISys3yxLMrvA+k2Forjm/flcZYfrEWqFbkH3fpwQYeDuC9b3a2sdE
# dyBlt51HQx7hA6TzEd5flgGdwbu/lL/BFVjK8PdsB6hpMFkYU3QSpp1dTojC6kf0
# 3XmMjnVsoyWW
# SIG # End Windows Authenticode signature block