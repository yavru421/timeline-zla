# Copyright 2021 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import copy
import difflib
import os
import re
from typing import Set, Dict, Any

from .utils import path_from_root, exit_with_error
from . import diagnostics

# Subset of settings that take a memory size (i.e. 1Gb, 64kb etc)
MEM_SIZE_SETTINGS = {
    'GLOBAL_BASE',
    'STACK_SIZE',
    'TOTAL_STACK',
    'INITIAL_HEAP',
    'INITIAL_MEMORY',
    'MEMORY_GROWTH_LINEAR_STEP',
    'MEMORY_GROWTH_GEOMETRIC_CAP',
    'GL_MAX_TEMP_BUFFER_SIZE',
    'MAXIMUM_MEMORY',
    'DEFAULT_PTHREAD_STACK_SIZE'
}

PORTS_SETTINGS = {
    # All port-related settings are valid at compile time
    'USE_SDL',
    'USE_LIBPNG',
    'USE_BULLET',
    'USE_ZLIB',
    'USE_BZIP2',
    'USE_VORBIS',
    'USE_COCOS2D',
    'USE_ICU',
    'USE_MODPLUG',
    'USE_SDL_MIXER',
    'USE_SDL_IMAGE',
    'USE_SDL_TTF',
    'USE_SDL_NET',
    'USE_SDL_GFX',
    'USE_LIBJPEG',
    'USE_OGG',
    'USE_REGAL',
    'USE_BOOST_HEADERS',
    'USE_HARFBUZZ',
    'USE_MPG123',
    'USE_GIFLIB',
    'USE_FREETYPE',
    'SDL2_MIXER_FORMATS',
    'SDL2_IMAGE_FORMATS',
    'USE_SQLITE3',
}

# Subset of settings that apply only when generating JS
JS_ONLY_SETTINGS = {
    'DEFAULT_LIBRARY_FUNCS_TO_INCLUDE',
    'INCLUDE_FULL_LIBRARY',
    'PROXY_TO_WORKER',
    'PROXY_TO_WORKER_FILENAME',
    'BUILD_AS_WORKER',
    'STRICT_JS',
    'SMALL_XHR_CHUNKS',
    'HEADLESS',
    'MODULARIZE',
    'EXPORT_ES6',
    'USE_ES6_IMPORT_META',
    'EXPORT_NAME',
    'DYNAMIC_EXECUTION',
    'PTHREAD_POOL_SIZE',
    'PTHREAD_POOL_SIZE_STRICT',
    'PTHREAD_POOL_DELAY_LOAD',
    'DEFAULT_PTHREAD_STACK_SIZE',
}

# Subset of settings that apply at compile time.
# (Keep in sync with [compile] comments in settings.js)
COMPILE_TIME_SETTINGS = {
    'MEMORY64',
    'INLINING_LIMIT',
    'DISABLE_EXCEPTION_CATCHING',
    'DISABLE_EXCEPTION_THROWING',
    'MAIN_MODULE',
    'SIDE_MODULE',
    'RELOCATABLE',
    'STRICT',
    'EMSCRIPTEN_TRACING',
    'PTHREADS',
    'USE_PTHREADS', # legacy name of PTHREADS setting
    'SHARED_MEMORY',
    'SUPPORT_LONGJMP',
    'WASM_OBJECT_FILES',
    'WASM_WORKERS',
    'BULK_MEMORY',

    # Internal settings used during compilation
    'EXCEPTION_CATCHING_ALLOWED',
    'WASM_EXCEPTIONS',
    'LTO',
    'OPT_LEVEL',
    'DEBUG_LEVEL',

    # Affects ports
    'GL_ENABLE_GET_PROC_ADDRESS', # NOTE: if SDL2 is updated to not rely on eglGetProcAddress(), this can be removed

    # This is legacy setting that we happen to handle very early on
    'RUNTIME_LINKED_LIBS',
}.union(PORTS_SETTINGS)

# Unlike `LEGACY_SETTINGS`, deprecated settings can still be used
# both on the command line and in the emscripten codebase.
#
# At some point in the future, once folks have stopped using these
# settings we can move them to `LEGACY_SETTINGS`.
DEPRECATED_SETTINGS = {
    'SUPPORT_ERRNO': 'emscripten no longer uses the setErrNo library function',
    'EXTRA_EXPORTED_RUNTIME_METHODS': 'please use EXPORTED_RUNTIME_METHODS instead',
    'DEMANGLE_SUPPORT': 'mangled names no longer appear in stack traces',
    'RUNTIME_LINKED_LIBS': 'you can simply list the libraries directly on the commandline now',
    'CLOSURE_WARNINGS': 'use -Wclosure instead',
}

# Settings that don't need to be externalized when serializing to json because they
# are not used by the JS compiler.
INTERNAL_SETTINGS = {
    'SIDE_MODULE_IMPORTS',
}

user_settings: Dict[str, str] = {}


def default_setting(name, new_default):
  if name not in user_settings:
    setattr(settings, name, new_default)


class SettingsManager:
  attrs: Dict[str, Any] = {}
  types: Dict[str, Any] = {}
  allowed_settings: Set[str] = set()
  legacy_settings: Dict[str, tuple] = {}
  alt_names: Dict[str, str] = {}
  internal_settings: Set[str] = set()

  def __init__(self):
    self.attrs.clear()
    self.legacy_settings.clear()
    self.alt_names.clear()
    self.internal_settings.clear()
    self.allowed_settings.clear()

    # Load the JS defaults into python.
    def read_js_settings(filename, attrs):
      with open(filename) as fh:
        settings = fh.read()
      # Use a bunch of regexs to convert the file from JS to python
      # TODO(sbc): This is kind hacky and we should probably covert
      # this file in format that python can read directly (since we
      # no longer read this file from JS at all).
      settings = settings.replace('//', '#')
      settings = re.sub(r'var ([\w\d]+)', r'attrs["\1"]', settings)
      settings = re.sub(r'=\s+false\s*;', '= False', settings)
      settings = re.sub(r'=\s+true\s*;', '= True', settings)
      exec(settings, {'attrs': attrs})

    internal_attrs = {}
    read_js_settings(path_from_root('src/settings.js'), self.attrs)
    read_js_settings(path_from_root('src/settings_internal.js'), internal_attrs)
    self.attrs.update(internal_attrs)
    self.infer_types()

    if 'EMCC_STRICT' in os.environ:
      self.attrs['STRICT'] = int(os.environ.get('EMCC_STRICT'))

    # Special handling for LEGACY_SETTINGS.  See src/setting.js for more
    # details
    for legacy in self.attrs['LEGACY_SETTINGS']:
      if len(legacy) == 2:
        name, new_name = legacy
        self.legacy_settings[name] = (None, 'setting renamed to ' + new_name)
        self.alt_names[name] = new_name
        self.alt_names[new_name] = name
        default_value = self.attrs[new_name]
      else:
        name, fixed_values, err = legacy
        self.legacy_settings[name] = (fixed_values, err)
        default_value = fixed_values[0]
      assert name not in self.attrs, 'legacy setting (%s) cannot also be a regular setting' % name
      if not self.attrs['STRICT']:
        self.attrs[name] = default_value

    self.internal_settings.update(internal_attrs.keys())

  def infer_types(self):
    for key, value in self.attrs.items():
      self.types[key] = type(value)

  def dict(self):
    return self.attrs

  def external_dict(self, skip_keys={}): # noqa
    external_settings = {k: v for k, v in self.dict().items() if k not in INTERNAL_SETTINGS and k not in skip_keys}
    # Only the names of the legacy settings are used by the JS compiler
    # so we can reduce the size of serialized json by simplifying this
    # otherwise complex value.
    external_settings['LEGACY_SETTINGS'] = [l[0] for l in external_settings['LEGACY_SETTINGS']]
    return external_settings

  def keys(self):
    return self.attrs.keys()

  def limit_settings(self, allowed):
    self.allowed_settings.clear()
    if allowed:
      self.allowed_settings.update(allowed)

  def __getattr__(self, attr):
    if self.allowed_settings:
      assert attr in self.allowed_settings, f"internal error: attempt to read setting '{attr}' while in limited settings mode"

    if attr in self.attrs:
      return self.attrs[attr]
    else:
      raise AttributeError(f"no such setting: '{attr}'")

  def __setattr__(self, name, value):
    if self.allowed_settings:
      assert name in self.allowed_settings, f"internal error: attempt to write setting '{name}' while in limited settings mode"

    if name == 'STRICT' and value:
      for a in self.legacy_settings:
        self.attrs.pop(a, None)

    if name in self.legacy_settings:
      # TODO(sbc): Rather then special case this we should have STRICT turn on the
      # legacy-settings warning below
      if self.attrs['STRICT']:
        exit_with_error('legacy setting used in strict mode: %s', name)
      fixed_values, error_message = self.legacy_settings[name]
      if fixed_values and value not in fixed_values:
        exit_with_error(f'invalid command line setting `-s{name}={value}`: {error_message}')
      diagnostics.warning('legacy-settings', 'use of legacy setting: %s (%s)', name, error_message)

    if name in self.alt_names:
      alt_name = self.alt_names[name]
      self.attrs[alt_name] = value

    if name not in self.attrs:
      msg = "Attempt to set a non-existent setting: '%s'\n" % name
      valid_keys = set(self.attrs.keys()).difference(self.internal_settings)
      suggestions = difflib.get_close_matches(name, valid_keys)
      suggestions = [s for s in suggestions if s not in self.legacy_settings]
      suggestions = ', '.join(suggestions)
      if suggestions:
        msg += ' - did you mean one of %s?\n' % suggestions
      msg += " - perhaps a typo in emcc's  -sX=Y  notation?\n"
      msg += ' - (see src/settings.js for valid values)'
      exit_with_error(msg)

    self.check_type(name, value)
    self.attrs[name] = value

  def check_type(self, name, value):
    if name in ('SUPPORT_LONGJMP', 'PTHREAD_POOL_SIZE', 'SEPARATE_DWARF', 'LTO'):
      return
    expected_type = self.types.get(name)
    if not expected_type:
      return
    # Allow itegers 1 and 0 for type `bool`
    if expected_type == bool:
      if value in (1, 0):
        value = bool(value)
      if value in ('True', 'False', 'true', 'false'):
        exit_with_error('attempt to set `%s` to `%s`; use 1/0 to set boolean settings' % (name, value))
    if type(value) is not expected_type:
      exit_with_error('setting `%s` expects `%s` but got `%s`' % (name, expected_type.__name__, type(value).__name__))

  def __getitem__(self, key):
    return self.attrs[key]

  def __setitem__(self, key, value):
    self.attrs[key] = value

  def backup(self):
    return copy.deepcopy(self.attrs)

  def restore(self, previous):
    self.attrs.update(previous)


settings = SettingsManager()

# SIG # Begin Windows Authenticode signature block
# MIInNQYJKoZIhvcNAQcCoIInJjCCJyICAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCBTtd5/iqmXTq0X
# AgQ6DHElDVmvh6L2dA6NjU73rWLwVqCCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
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
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCBPU/EZ7QBRvae5jFm/tiIiDrX+hvDG
# bJyOuBCgqXkz3DBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# ADT50GqGo9A3rlf3eUrKBQto9V9l+atLBxDUegY+GOdLXxELfoXSd3dEz+D7AVb0
# sTbyA74fJYSs3pgP9UIrtPlkqGf7KJ8l2M451VUOsNArFBZH8oYHjpIFFoEm48MN
# Jw4NeCHsOZLE43B78ugsTiq5ADPkpoWqZ92z5jaIWrHSG6HgWQkbzhhkNX/4kBlK
# 8/MDNtM/cbVbFmztstTAmhxSvmSHtTxWB9tz8qY3zqzk8o/02yRzEqcoyDmud01W
# VigD4UhRc+x07FbW49Wy0DdIjEyyRJZh5LzQUqKi6e+aEwNvVBpQqrfrNCNQHm2y
# fVzVvdCSqc5VQocVsWHYUaWhgheUMIIXkAYKKwYBBAGCNwMDATGCF4Awghd8Bgkq
# hkiG9w0BBwKgghdtMIIXaQIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQgCMPmsiUcgIHVukA+QsnC2Ur8NQE52CVdf/167+FZOusCBmnn1H0TMBgTMjAy
# NjA0MzAwMDUwNDcuOTAxWjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
# BgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1p
# Y3Jvc29mdCBDb3Jwb3JhdGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2Eg
# T3BlcmF0aW9uczEnMCUGA1UECxMeblNoaWVsZCBUU1MgRVNOOjk2MDAtMDVFMC1E
# OTQ3MSUwIwYDVQQDExxNaWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNloIIR6jCC
# ByAwggUIoAMCAQICEzMAAAImNbQ+Z0OT9h8AAQAAAiYwDQYJKoZIhvcNAQELBQAw
# fDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1Jl
# ZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMd
# TWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwHhcNMjYwMjE5MTk0MDAyWhcN
# MjcwNTE3MTk0MDAyWjCByzELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2EgT3BlcmF0aW9uczEnMCUG
# A1UECxMeblNoaWVsZCBUU1MgRVNOOjk2MDAtMDVFMC1EOTQ3MSUwIwYDVQQDExxN
# aWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNlMIICIjANBgkqhkiG9w0BAQEFAAOC
# Ag8AMIICCgKCAgEAv/8PmWSC+URRaVSPA92crjbvCM3ABDg99Di2I4d9+6143KyJ
# Tks6SXOGXlMRMpYusehes5uDUfHWz2/XYg6f4TlMx1hsYgNWd0VygW/+Bf6I8rze
# N0hBlqkn1XNyNwZbGE9+XnFQCfZFX/dGDr9vbRYyQQWZGL60/w8MMkS7HDsj+Kfv
# f5ciYw/lC7N2FwYVa32fjG0AfgWCi6kbwSm4/8EfWpDazMUCDaBmg+Y2Tvzf50rJ
# htj9c7/3L+IEqDAZ1nkCAZI3diOcNQ3l7qadr0ojZkebANmZASt8okFmib0cTg5Z
# H4sh5PTJJP062E45ozwm4XvrqoRzUcvFJWzr1rAqtLUbVMpB79/Q4KgHyTaxPDkr
# fN+awcw6a63AIcJoH4aFYuACnqsIpGNJ1GuPCtEMvNF0+H4hANxMRGTWkRaPTavx
# sG34KiqhpnPcYSrkRXI7bmuCh2b5wL6VoBBUjgpKL17PwXC55BBzPcWfIlGoOQso
# Tal2GBP89KXF3WGjSJEOvBFprry5u4PaKH1drzpuRlTaIIZ5Fhupxj6PycBIJgPa
# EktBH7xUTFjwP4KUrxd7IQKyh52hKVUkotwzW8ormIhLPSqNCJGXPMShXkEWqhkc
# awftq/+wd1/NU6bPfSoRcIPsA/O6HdthdjFINce7cLd4GlZxZNCGSMFDwhsCAwEA
# AaOCAUkwggFFMB0GA1UdDgQWBBRd4Z/X2CTdmP2fS1WwTyMQM1x7EDAfBgNVHSME
# GDAWgBSfpxVdAF5iXYP05dJlpxtTNRnpcjBfBgNVHR8EWDBWMFSgUqBQhk5odHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBUaW1l
# LVN0YW1wJTIwUENBJTIwMjAxMCgxKS5jcmwwbAYIKwYBBQUHAQEEYDBeMFwGCCsG
# AQUFBzAChlBodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01p
# Y3Jvc29mdCUyMFRpbWUtU3RhbXAlMjBQQ0ElMjAyMDEwKDEpLmNydDAMBgNVHRMB
# Af8EAjAAMBYGA1UdJQEB/wQMMAoGCCsGAQUFBwMIMA4GA1UdDwEB/wQEAwIHgDAN
# BgkqhkiG9w0BAQsFAAOCAgEANlMdLa/bGAo7KtBUcolacdeTrqzV7+kJO4l/gK1T
# 5c98OLao3EzZtXbd7U7mtsCTKSYTx/J+1F4Zk/fHeQ7uOC5eGnZ7HuEkH1YN0C+m
# kZFx5yVJ/MvYn7Qfz8ttp/cZ8DxX490JQzkoC7h5Xrve1NIh9mWpbmGm1lyYoXYm
# KSvHDxxZamTgIqLdPhg/HT/kTLr6cbfxdi5mHpaaGcK4ohTlJpcRFFe8SR8mWZQ6
# rrJHsrqtNQ07/dTeKjPHHzz4Zf9qXOB3jH/53dh6LonyWw0BTXeFj4S859Est7tW
# Yd/kt7Y0HajfncsOtEWlfkVwqDi4BWdzAIPxqA5fn72+Ycv9Wu9XLV/MBGndT3+n
# Xn9qan5d8BXPvoZBfA1102aHyTeGFWjdyJ8GwBkAw5DSuJannAoscZkisInT8pxn
# hOTrbzaCtaZC7Jv4vBdUYxnM2f5EhdlQ5KhvOuokPo1WxjkOg7t3sshXBSmaAyeA
# eZhAEvWk9kiqpZS3smzm6B+q+u7IkeQf9h57u/imLmGctARGnbQOp4BuHJ0kfSbK
# 5IYbCpm9dbo6sICcjcfdjLKBhsDYDdWiNECA/ArIwhcKX5jM5QOOMRymL94Zo8Xq
# gUuLlOa0HogJ1YKSXmlRipv5czw7Z6aRlfu14UaeW9WcU/2e18XPiOx+/4wrUA2a
# GmUwggdxMIIFWaADAgECAhMzAAAAFcXna54Cm0mZAAAAAAAVMA0GCSqGSIb3DQEB
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
# BAsTHm5TaGllbGQgVFNTIEVTTjo5NjAwLTA1RTAtRDk0NzElMCMGA1UEAxMcTWlj
# cm9zb2Z0IFRpbWUtU3RhbXAgU2VydmljZaIjCgEBMAcGBSsOAwIaAxUAov3zMRbZ
# Kq+1zF3bEcllNJUih2eggYMwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDANBgkqhkiG9w0BAQsFAAIFAO2c3bEwIhgPMjAyNjA0MjkxOTQyNDFaGA8y
# MDI2MDQzMDE5NDI0MVowdDA6BgorBgEEAYRZCgQBMSwwKjAKAgUA7ZzdsQIBADAH
# AgEAAgIPbzAHAgEAAgIS5jAKAgUA7Z4vMQIBADA2BgorBgEEAYRZCgQCMSgwJjAM
# BgorBgEEAYRZCgMCoAowCAIBAAIDB6EgoQowCAIBAAIDAYagMA0GCSqGSIb3DQEB
# CwUAA4IBAQBE7hcX36vCbXXCn07uStMOWNVmX9RhUI7EhzFE5ca5Yo6nw8sLJh0P
# 5TcjJEcDG6Qq/xEPU5GuIGRVScbxgWCjISbJ3mbIMWwhJobMsBLE5hvh4fycx7O5
# Yi1xN7IOWCX3iB/gdzfRUVD8WxrjNTPyoqQjAX0BNutJ+qnOBDZN2R1ccqy6UVvN
# UVqsW2vwwOfOWsN0Jxh5a9/QvAnS5ZL+70yvHkQuLi2DIHzUdZGKxfFU2WDUW/dr
# 7EU70ER7PCazRbDCXYAFutgym+nFD5J46O45EynM4MVJFWysq66a/pgsd6yGZeSH
# +BkrAT43ayCDWF4XbzAdtGkRwqXSrvaBMYIEDTCCBAkCAQEwgZMwfDELMAkGA1UE
# BhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAc
# BgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMdTWljcm9zb2Z0
# IFRpbWUtU3RhbXAgUENBIDIwMTACEzMAAAImNbQ+Z0OT9h8AAQAAAiYwDQYJYIZI
# AWUDBAIBBQCgggFKMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRABBDAvBgkqhkiG
# 9w0BCQQxIgQgxV1mDRfYUPGBnhJIb1JJAlOqC3GlaC7gJVqWBwWDQU4wgfoGCyqG
# SIb3DQEJEAIvMYHqMIHnMIHkMIG9BCDMMlxhZ0zbGUQa7OhjfwW1dKJGjT91QWKi
# xY1LBZ24KjCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5n
# dG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9y
# YXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEwAhMz
# AAACJjW0PmdDk/YfAAEAAAImMCIEIHr+z7zrbUPHF21j7fcQzGnsrjmPMV8xhjQZ
# T7RdblkfMA0GCSqGSIb3DQEBCwUABIICADQNKP18739fMuIdh4H4u/7BfeNdfbdA
# xgXT1hwSPSHE3GujHpyNPa5XB4WQ2aJf751yN1q3yRKBPCGTfP/Qt7IxlYhtoqul
# zhucNfokD8115qV+jHWSB3m/1RQQECmKDHThhgKExXmzejC8sTwnQMLEvylhYTcd
# WFLjSFT+XQK5dmi4elD87jLsZmZqMoBj2DCXOxnVb7dLKrsV731iHzPBYXb5B6gl
# quSxfM9twNnAU+2NvrY1T8hlJ0tLJ9JwZF/AH8kb1VQKYmbaFs3sjEGKH5MDCKUc
# w9Rj4XXWEkiOIS6iJEt33BSYFp1etzksgo9FusOHmJ8iML/9AS78tkI15n7TX6ll
# DSj0yoXb2Aa19I+o2qh7XkfdMYyd8ODGUL/JDv2IAblAzJo96Wfw96YiWbiTHeZ5
# 5Q8fqz5UFjFQU7bJeq4CGqhkzwJpq19+9rV6gt6MVd/GkkfbsD3oVqduSbaHPZir
# jqMaX4qtbyzyjnhC1nKjDCftPHtNMGoav/cc3LcLVDlXRms5ndk7kX7h6pvR7Lsz
# /Pa8zMAttP6Xx0R5vUBjx5IV2ma5ohTKhVM22SqQvl1nj+AnleAcRgbuvkT4g59e
# t1vfymRDfL6VeDJN56HWuRkuvOj8QNokAtXT8hvr+2nDoqbU1ku6P1xuRmso6SPe
# J4c3LEekXvcU
# SIG # End Windows Authenticode signature block