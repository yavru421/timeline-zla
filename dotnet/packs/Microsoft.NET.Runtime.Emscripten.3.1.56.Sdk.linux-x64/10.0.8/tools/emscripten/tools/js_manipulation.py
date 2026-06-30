# Copyright 2020 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import re

from .settings import settings
from . import utils, shared

emscripten_license = '''\
/**
 * @license
 * Copyright 2010 The Emscripten Authors
 * SPDX-License-Identifier: MIT
 */
'''

# handle the above form, and also what closure can emit which is stuff like
#  /*
#
#   Copyright 2019 The Emscripten Authors
#   SPDX-License-Identifier: MIT
#
#   Copyright 2017 The Emscripten Authors
#   SPDX-License-Identifier: MIT
#  */
# CodeQL [SM03905] This regex is safe for our use case since it only runs on source code in the repo
emscripten_license_regex = r'/\*\*?(?:\s*\*?\s*@license)?(?:\s*\*?\s*Copyright \d+ The Emscripten Authors\s*\*?\s*SPDX-License-Identifier: MIT){1,}\s*\*\/\s*'


def add_files_pre_js(pre_js_list, files_pre_js):
  # the normal thing is to just combine the pre-js content
  filename = shared.get_temp_files().get('.js').name
  utils.write_file(filename, files_pre_js)
  pre_js_list.insert(0, filename)
  if not settings.ASSERTIONS:
    return

  # if a user pre-js tramples the file code's changes to Module.preRun
  # that could be confusing. show a clear error at runtime if assertions are
  # enabled
  pre = shared.get_temp_files().get('.js').name
  post = shared.get_temp_files().get('.js').name
  utils.write_file(pre, '''
    // All the pre-js content up to here must remain later on, we need to run
    // it.
    if (Module['ENVIRONMENT_IS_PTHREAD'] || Module['$ww']) Module['preRun'] = [];
    var necessaryPreJSTasks = Module['preRun'].slice();
  ''')
  utils.write_file(post, '''
    if (!Module['preRun']) throw 'Module.preRun should exist because file support used it; did a pre-js delete it?';
    necessaryPreJSTasks.forEach(function(task) {
      if (Module['preRun'].indexOf(task) < 0) throw 'All preRun tasks that exist before user pre-js code should remain after; did you replace Module or modify Module.preRun?';
    });
  ''')

  pre_js_list.insert(1, pre)
  pre_js_list.append(post)


def handle_license(js_target):
  # ensure we emit the license if and only if we need to, and exactly once
  js = utils.read_file(js_target)
  # first, remove the license as there may be more than once
  processed_js = re.sub(emscripten_license_regex, '', js)
  if settings.EMIT_EMSCRIPTEN_LICENSE:
    processed_js = emscripten_license + processed_js
  if processed_js != js:
    utils.write_file(js_target, processed_js)


# Returns the given string with escapes added so that it can safely be placed inside a string in JS code.
def escape_for_js_string(s):
  s = s.replace('\\', '/').replace("'", "\\'").replace('"', '\\"')
  return s


def legalize_sig(sig):
  # with BigInt support all sigs are legal since we can use i64s.
  if settings.WASM_BIGINT:
    return sig
  legal = [sig[0]]
  # a return of i64 is legalized into an i32 (and the high bits are
  # accessible on the side through getTempRet0).
  if legal[0] == 'j':
    legal[0] = 'i'
  # a parameter of i64 is legalized into i32, i32
  for s in sig[1:]:
    if s != 'j':
      legal.append(s)
    else:
      legal.append('i')
      legal.append('i')
  return ''.join(legal)


def is_legal_sig(sig):
  # with BigInt support all sigs are legal since we can use i64s.
  if settings.WASM_BIGINT:
    return True
  return sig == legalize_sig(sig)


def isidentifier(name):
  # https://stackoverflow.com/questions/43244604/check-that-a-string-is-a-valid-javascript-identifier-name-using-python-3
  return name.replace('$', '_').isidentifier()


def make_dynCall(sig, args):
  # wasm2c and asyncify are not yet compatible with direct wasm table calls
  if settings.MEMORY64:
    args = list(args)
    args[0] = f'Number({args[0]})'
  if settings.DYNCALLS or not is_legal_sig(sig):
    args = ','.join(args)
    if not settings.MAIN_MODULE and not settings.SIDE_MODULE:
      # Optimize dynCall accesses in the case when not building with dynamic
      # linking enabled.
      return 'dynCall_%s(%s)' % (sig, args)
    else:
      return 'Module["dynCall_%s"](%s)' % (sig, args)
  else:
    call_args = ",".join(args[1:])
    return f'getWasmTableEntry({args[0]})({call_args})'


def make_invoke(sig):
  legal_sig = legalize_sig(sig) # TODO: do this in extcall, jscall?
  args = ['index'] + ['a' + str(i) for i in range(1, len(legal_sig))]
  ret = 'return ' if sig[0] != 'v' else ''
  # For function that needs to return a genuine i64 (i.e. if legal_sig[0] is 'j')
  # we need to return an actual BigInt, even in the exceptional case because
  # wasm won't implicitly convert undefined to 0 in this case.
  exceptional_ret = '\n    return 0n;' if legal_sig[0] == 'j' else ''
  body = '%s%s;' % (ret, make_dynCall(sig, args))
  # Create a try-catch guard that rethrows the Emscripten EH exception.
  if settings.EXCEPTION_STACK_TRACES:
    # Exceptions thrown from C++ and longjmps will be an instance of
    # EmscriptenEH.
    maybe_rethrow = 'if (!(e instanceof EmscriptenEH)) throw e;'
  else:
    # Exceptions thrown from C++ will be a pointer (number) and longjmp will
    # throw the number Infinity. Use the compact and fast "e !== e+0" test to
    # check if e was not a Number.
    maybe_rethrow = 'if (e !== e+0) throw e;'

  ret = '''\
function invoke_%s(%s) {
  var sp = stackSave();
  try {
    %s
  } catch(e) {
    stackRestore(sp);
    %s
    _setThrew(1, 0);%s
  }
}''' % (sig, ','.join(args), body, maybe_rethrow, exceptional_ret)

  return ret


def make_wasm64_wrapper(sig):
  assert 'p' in sig.lower()
  n_args = len(sig) - 1
  args = ['a%d' % i for i in range(n_args)]
  args_converted = args.copy()
  for i, arg_type in enumerate(sig[1:]):
    if arg_type == 'p':
      args_converted[i] = f'BigInt({args_converted[i]})'
    elif arg_type == 'P':
      args_converted[i] = f'BigInt({args_converted[i]} ? {args_converted[i]} : 0)'
    else:
      assert arg_type == '_'

  args_in = ', '.join(args)
  args_out = ', '.join(args_converted)
  result = f'f({args_out})'
  if sig[0] == 'p':
    result = f'Number({result})'

  # We can't use an arrow function for the inner wrapper here since there
  # are certain places we need to avoid strict mode still.
  # e.g. emscripten_get_callstack (getCallstack) which uses the `arguments`
  # global.
  return f'  var makeWrapper_{sig} = (f) => function ({args_in}) {{ return {result} }};\n'


def make_unsign_pointer_wrapper(sig):
  assert sig[0] == 'p'
  n_args = len(sig) - 1
  args = ','.join('a%d' % i for i in range(n_args))
  return f'  var makeWrapper_{sig} = (f) => ({args}) => f({args}) >>> 0;\n'

# SIG # Begin Windows Authenticode signature block
# MIInOAYJKoZIhvcNAQcCoIInKTCCJyUCAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCAma50C6CgAX+aE
# XQI/GDlyay790viqMXJ8fO80JcH396CCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
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
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCDGGc8NdEEGbJ+HQ3BZ10I7mFUNY1su
# d7tfn4LwzAkCxjBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# AJfubC6FpzvogwUiSQwVsf2rQX43v5qA6riWy4TpIy+o1+Em+YvQUWd0vXFH3Ddc
# 5FBKj/R2AO3H5D/rJe3VPZTm2jzJOORKkyK7X1/yqW/eG7YZW9KjmXZiuk9zL+KW
# 57HMVTX4PpPU2Y9KjSNACjMpfWxbymsn9j/kZVcuiDLnPXo5GG2f3nlJV7CNqSR1
# 5cpR+LlS4U5H01fWtHun3l+HPSaBh1GEmn5yFwAf3LTfI3ARZ4Lmob9h7KadNW7E
# bb37dTGD1drDkx7uN9idxkq4IrlHAwah2VkVTkK3seSCB5z0lS821WXMyiF/aOXg
# Hu4HK0oZGooXcnIx4hUQx4GhgheXMIIXkwYKKwYBBAGCNwMDATGCF4Mwghd/Bgkq
# hkiG9w0BBwKgghdwMIIXbAIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQgTB6OizGiG2B0W1bHQapAFz8NJmop3PWAWQ+Tp070tYECBmnnoCJoMxgTMjAy
# NjA0MzAwMDUwNDcuNjk4WjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
# BgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1p
# Y3Jvc29mdCBDb3Jwb3JhdGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2Eg
# T3BlcmF0aW9uczEnMCUGA1UECxMeblNoaWVsZCBUU1MgRVNOOjdGMDAtMDVFMC1E
# OTQ3MSUwIwYDVQQDExxNaWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNloIIR7TCC
# ByAwggUIoAMCAQICEzMAAAIeo6ykbjlvfEkAAQAAAh4wDQYJKoZIhvcNAQELBQAw
# fDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1Jl
# ZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMd
# TWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwHhcNMjYwMjE5MTkzOTQ5WhcN
# MjcwNTE3MTkzOTQ5WjCByzELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2EgT3BlcmF0aW9uczEnMCUG
# A1UECxMeblNoaWVsZCBUU1MgRVNOOjdGMDAtMDVFMC1EOTQ3MSUwIwYDVQQDExxN
# aWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNlMIICIjANBgkqhkiG9w0BAQEFAAOC
# Ag8AMIICCgKCAgEApdE47Ww8LEexXvGnOqJebNc4bU6ndgFqXIUIS6fRuZpkjNtz
# eX8kBgkNQ9OqzgNz4Fyhfu+r17zgrNlbC79aMI+JhxMhKoqvBiecgvv0DWEaWTwP
# HuzoHpMwzukv+L8v40zGG6d64bhYiigs01jkLXRXBfg9JN+vSO6ZvxNO0sjTBpLj
# XeZY+UifdVKhbmX4zAenENsIe+5rYkVFXY+d8o3Tao/hkJfmGs9vQY685+1NZZ/i
# aS5Z29MXRpmaCDymW8AVXFrci+LsoTC+0kk5ojn1l1PoPsjZdAnaCxi/C7VhxIvB
# bLkz3knUqpnjK7y2hJom01U0uL0EGPDT52+riOcuojVfbwRXJvC1P5Q04xk6j2u1
# AU+IHX+SZt8GK3whWeD/4+TKKk9CTjXGudI7eExiPdEooV2gxGKpNt0tCCWd1JFK
# bpA0U4yu9dwSMpH38cgajHkKnztM71n1Mewa5lKboEHMPffg8S5doH/rkBKUZp5W
# 61SfXb1vXbOH6hDzdoxtEMBdTwUoJTXFdUqamSorUIARksLv/NgCs7aAh8GER0Tc
# M8E1Xv9SjU75qgHeFIHrOMsDh9NoWmoE/MGGPDnVnYyp95NOdsPpJnNFAtBfolV0
# xmSDMb6PYgWUKF3oc0bVif1TrSrwskt3LCsze60rVicI0ls+nbTn9JfsrS0CAwEA
# AaOCAUkwggFFMB0GA1UdDgQWBBTmChaa6gQdCWZiXBQuHDz5nheCZDAfBgNVHSME
# GDAWgBSfpxVdAF5iXYP05dJlpxtTNRnpcjBfBgNVHR8EWDBWMFSgUqBQhk5odHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBUaW1l
# LVN0YW1wJTIwUENBJTIwMjAxMCgxKS5jcmwwbAYIKwYBBQUHAQEEYDBeMFwGCCsG
# AQUFBzAChlBodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01p
# Y3Jvc29mdCUyMFRpbWUtU3RhbXAlMjBQQ0ElMjAyMDEwKDEpLmNydDAMBgNVHRMB
# Af8EAjAAMBYGA1UdJQEB/wQMMAoGCCsGAQUFBwMIMA4GA1UdDwEB/wQEAwIHgDAN
# BgkqhkiG9w0BAQsFAAOCAgEApKGQeTZyVRW+cCno0aJ5OdfGtkwTWKSnATLXy+gU
# tAEWgATjBmC5TzboSNR8JnpT/YV96Kt02hJv3A5JMzUAMw3nT4KESNke/vKaDUlr
# x1xALO0mTg5vceyqpQZDWTPXseF2NcjZlTgJlg40a+4yo2okG57X+xAuBjYpMRhm
# lVjo32Ld0PV9K/yrPCgZW8w0fc4wP0wnLUeHKNVqVNWUSxawfW5fHUcbG58k9qkO
# NRO3U9dkd9HiBlM4hLORjftulf6L1zottHSYjNd4WFr8tTTSQIZCjpSwdTjbp3en
# 34T3VHB1rLvFfpUdGmpDFeuB6g2y7pmawjcFKH1cd8TJPBeLQmCbUMS08sHN9LGQ
# A9UtrAtfefceiosQPqeNRS1JfIOuKB8t232Jx+cXeCTgYEKGqp3Ro3HLca/vBJJ4
# 4Ssq4AM603CiyW1Hs4KMnvG6wiyfsujwKBI6V0ZEmAFPMH0N2FkXJOgC8KFe1Ip/
# Pq6RkEm14RenNXUxWpF5goQpbneCAA2P7eiUZCftOhcy/ow3fCi1fEI++yX4rk4j
# yBuRv8ZZxqGRXF/ssgbQ782ROPHfmPh2FHf3L4R9RSpewB/uQMqLaiUhZrzPwbmE
# cdgdtGrFV4pVdpNiWzTtyxgs90PnaRJc8LHya5GtTf4HrZmu31qaMLDb6CGhEL42
# nfEwggdxMIIFWaADAgECAhMzAAAAFcXna54Cm0mZAAAAAAAVMA0GCSqGSIb3DQEB
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
# BAsTHm5TaGllbGQgVFNTIEVTTjo3RjAwLTA1RTAtRDk0NzElMCMGA1UEAxMcTWlj
# cm9zb2Z0IFRpbWUtU3RhbXAgU2VydmljZaIjCgEBMAcGBSsOAwIaAxUAg/0DZCgy
# FuFSBe496Itqm60dGv+ggYMwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDANBgkqhkiG9w0BAQsFAAIFAO2cqUwwIhgPMjAyNjA0MjkxNTU5MDhaGA8y
# MDI2MDQzMDE1NTkwOFowdzA9BgorBgEEAYRZCgQBMS8wLTAKAgUA7ZypTAIBADAK
# AgEAAgIZqAIB/zAHAgEAAgIT3TAKAgUA7Z36zAIBADA2BgorBgEEAYRZCgQCMSgw
# JjAMBgorBgEEAYRZCgMCoAowCAIBAAIDB6EgoQowCAIBAAIDAYagMA0GCSqGSIb3
# DQEBCwUAA4IBAQBMR7VLNzDFMYRj5UT+AntH4lJmAAArK5MjiGQjm4q1WNxQn29L
# +bBSeC+/8Zb+4qte4D7tSmf1+uJN3D5tQLuS7eGKdWKdX/7lXhSqf2m2cu7ehT7L
# Z30awHzwCIcBBOEOV486XqiaKwvXhoEw03P2Avrfivk+3zPX7+ThbEFSeiqQAIvB
# pIiCOnKSYvqgeipM+f666lSNVSNgoc8Ln9fLyQGq2RETbvDd6i1xs02bCKikNisZ
# gijloxuYxLynrmK28WX3R6QaohMi3bLqa3Ix7gth9cwKqK70FYZDaC62h8bm0W4R
# uknO6MCtRMe+IcfnFagOYOMXidF/H/KvuL9WMYIEDTCCBAkCAQEwgZMwfDELMAkG
# A1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQx
# HjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMdTWljcm9z
# b2Z0IFRpbWUtU3RhbXAgUENBIDIwMTACEzMAAAIeo6ykbjlvfEkAAQAAAh4wDQYJ
# YIZIAWUDBAIBBQCgggFKMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRABBDAvBgkq
# hkiG9w0BCQQxIgQgLK4Zxx9JCHwG9NmTv1z/GUYwlzw5y9+GDIjq333vGu4wgfoG
# CyqGSIb3DQEJEAIvMYHqMIHnMIHkMIG9BCAvgV1q8/YHjIDPAb5/G6sR44R1ydvR
# AYsyEyMNAfbzgjCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNo
# aW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29y
# cG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEw
# AhMzAAACHqOspG45b3xJAAEAAAIeMCIEIAvbBsilYGWKwkmwfrGOvuMwCg+VuwfI
# qsOQOU0nAhHrMA0GCSqGSIb3DQEBCwUABIICAEjThvvOHy/O3ehW5I5/ixx2g+Wq
# r7jytp1JZkqKgq3tehLW/n2Lh139QmtxVHfux2iNuMHi6Wy69Y5iDv1ZAhsA3R96
# qO0Dzbd9qke0k+cdYAnZjn6f7Wt2SC+O0V7zn9b+0qTt4BL33QBk55Bb54275jCa
# 5MWqWfGDYUDBiL41pFJEz6Q+LCG0MMWZmveOqUXp+CXK//DD3udcGCuMmF7Y/3lr
# cvb0L3W4F1kRAV4LrRF2vHjOMbTBGRzkimICv7TYPA8CYnyWg3ilvQWL/XEiZAcR
# RfVS5OlWS/o8IQJ7hmfxfWtZ0Qau80YkS3hJ6rfKNjYIF9nwQGivmUjeq52kBILE
# 0o2dky8ww6xgVQk1eksHsUhq0nsJbyw3qBXYcSHvR8HK5Ze9o9fKE+37lEfTxBH3
# /94SdDjh6bCkY+Yg3lLJwj79zWbL+FEej8p3Aqsg4gATf/UVO5AtRegxaaB6po6t
# xc4gE0cUxW+twx3rV3rL1cyDmrtI+TqUMMiMQGg5skKnSaU1Ow0bPZoYxLGvjs9h
# 2fIWYZ2ZrzOkgovsiWxsvi/Ync8hCLknFLHEx05Qx8aUnyXxk66h73AF3lI77RVu
# kwdJtjdOYYBOleGk426h6nWPq5pSHL4Iq5v+qyX/012NLshYcW0RFKK5ZTwUVvId
# 6LQ+PGYxcYkNCto4
# SIG # End Windows Authenticode signature block