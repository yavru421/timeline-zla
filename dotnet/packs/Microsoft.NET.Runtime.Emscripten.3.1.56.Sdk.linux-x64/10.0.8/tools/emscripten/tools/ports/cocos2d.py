# Copyright 2017 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import os
import re
from tools import diagnostics

TAG = 'version_3_3'
HASH = 'd7b22660036c684f09754fcbbc7562984f02aa955eef2b76555270c63a717e6672c4fe695afb16280822e8b7c75d4b99ae21975a01a4ed51cad957f7783722cd'

deps = ['libpng', 'zlib']


def needed(settings):
  return settings.USE_COCOS2D == 3


def get(ports, settings, shared):
  ports.fetch_project('cocos2d', f'https://github.com/emscripten-ports/Cocos2d/archive/{TAG}.zip', sha512hash=HASH)

  def create(final):
    diagnostics.warning('experimental', 'cocos2d: library is experimental, do not expect that it will work out of the box')

    cocos2d_src = os.path.join(ports.get_dir(), 'cocos2d')
    cocos2d_root = os.path.join(cocos2d_src, 'Cocos2d-' + TAG)
    cocos2dx_root = os.path.join(cocos2d_root, 'cocos2dx')

    srcs = make_source_list(cocos2d_root, cocos2dx_root)
    includes = make_includes(cocos2d_root)
    flags = [
      '-w',
      '-D__CC_PLATFORM_FILEUTILS_CPP__',
      '-DCC_ENABLE_CHIPMUNK_INTEGRATION',
      '-DCC_KEYBOARD_SUPPORT',
      '-DGL_ES=1',
      '-DNDEBUG', # '-DCOCOS2D_DEBUG=1' 1 - error/warn, 2 - verbose
      # Cocos2d source code hasn't switched to __EMSCRIPTEN__.
      # See https://github.com/emscripten-ports/Cocos2d/pull/3
      '-DEMSCRIPTEN',
      '-DCP_USE_DOUBLES=0',
      '-sUSE_ZLIB',
      '-sUSE_LIBPNG',
    ]

    for dirname in includes:
      target = os.path.join('cocos2d', os.path.relpath(dirname, cocos2d_root))
      ports.install_header_dir(dirname, target=target)

    ports.build_port(cocos2d_src, final, 'cocos2d',
                     flags=flags,
                     cxxflags=['-std=c++14'],
                     includes=includes,
                     srcs=srcs)

  return [shared.cache.get_lib('libcocos2d.a', create, what='port')]


def clear(ports, settings, shared):
  shared.cache.erase_lib('libcocos2d.a')


def process_dependencies(settings):
  settings.USE_LIBPNG = 1
  settings.USE_ZLIB = 1


def process_args(ports):
  args = []
  for include in make_includes(ports.get_include_dir('cocos2d')):
    args += ['-isystem', include]
  return args


def show():
  return 'cocos2d (-sUSE_COCOS2D=3 or --use-port=cocos2d)'


def make_source_list(cocos2d_root, cocos2dx_root):
  sources = []

  def add_makefile(makefile):
    with open(makefile) as infile:
      add_next = False
      for line in infile:
        if line.startswith('SOURCES'):
          file = re.search(r'=\s*(.*?)(\s*\\$|\s*$)', line, re.IGNORECASE).group(1)
          absfile = os.path.abspath(os.path.join(os.path.dirname(makefile), file))
          sources.append(absfile)
          add_next = line.endswith('\\\n')
          continue
        if add_next:
          file = re.search(r'\s*(.*?)(\s*\\$|\s*$)', line, re.IGNORECASE).group(1)
          absfile = os.path.abspath(os.path.join(os.path.dirname(makefile), file))
          sources.append(absfile)
          add_next = line.endswith('\\\n')

  # core
  add_makefile(os.path.join(cocos2dx_root, 'proj.emscripten', 'Makefile'))
  # extensions
  add_makefile(os.path.join(cocos2d_root, 'extensions', 'proj.emscripten', 'Makefile'))
  # external
  add_makefile(os.path.join(cocos2d_root, 'external', 'Box2D', 'proj.emscripten', 'Makefile'))
  add_makefile(os.path.join(cocos2d_root, 'external', 'chipmunk', 'proj.emscripten', 'Makefile'))
  add_makefile(os.path.join(cocos2dx_root, 'platform', 'third_party', 'Makefile'))
  # misc
  sources.append(os.path.join(cocos2d_root, 'CocosDenshion', 'emscripten', 'SimpleAudioEngine.cpp'))
  sources.append(os.path.join(cocos2dx_root, 'CCDeprecated.cpp')) # subset of cocos2d v2
  return sources


def make_includes(root):
  return [os.path.join(root, 'CocosDenshion', 'include'),
          os.path.join(root, 'extensions'),
          os.path.join(root, 'extensions', 'AssetsManager'),
          os.path.join(root, 'extensions', 'CCArmature'),
          os.path.join(root, 'extensions', 'CCBReader'),
          os.path.join(root, 'extensions', 'GUI', 'CCControlExtension'),
          os.path.join(root, 'extensions', 'GUI', 'CCEditBox'),
          os.path.join(root, 'extensions', 'GUI', 'CCScrollView'),
          os.path.join(root, 'extensions', 'network'),
          os.path.join(root, 'extensions', 'Components'),
          os.path.join(root, 'extensions', 'LocalStorage'),
          os.path.join(root, 'extensions', 'physics_nodes'),
          os.path.join(root, 'extensions', 'spine'),
          os.path.join(root, 'external'),
          os.path.join(root, 'external', 'chipmunk', 'include', 'chipmunk'),
          os.path.join(root, 'cocos2dx'),
          os.path.join(root, 'cocos2dx', 'cocoa'),
          os.path.join(root, 'cocos2dx', 'include'),
          os.path.join(root, 'cocos2dx', 'kazmath', 'include'),
          os.path.join(root, 'cocos2dx', 'platform'),
          os.path.join(root, 'cocos2dx', 'platform', 'emscripten'),
          os.path.join(root, 'cocos2dx', 'platform', 'third_party', 'linux', 'libfreetype2'),
          os.path.join(root, 'cocos2dx', 'platform', 'third_party', 'common', 'etc'),
          os.path.join(root, 'cocos2dx', 'platform', 'third_party', 'emscripten', 'libtiff', 'include'),
          os.path.join(root, 'cocos2dx', 'platform', 'third_party', 'emscripten', 'libjpeg'),
          os.path.join(root, 'cocos2dx', 'platform', 'third_party', 'emscripten', 'libwebp')]

# SIG # Begin Windows Authenticode signature block
# MIInXwYJKoZIhvcNAQcCoIInUDCCJ0wCAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCA1Mt7ELr8b0AKH
# ANSBNNBlHHOZYyGS3QD9zoRc+f3m4aCCDLgwggXzMIID26ADAgECAhMzAAABx5qh
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
# Ni+AOxk0BtYd9hxwL30BElj9MYIZ/TCCGfkCAQEwbjBXMQswCQYDVQQGEwJVUzEe
# MBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSgwJgYDVQQDEx9NaWNyb3Nv
# ZnQgQ29kZSBTaWduaW5nIFBDQSAyMDI0AhMzAAABx5qh7twn4vi3AAAAAAHHMA0G
# CWCGSAFlAwQCAQUAoIGuMBkGCSqGSIb3DQEJAzEMBgorBgEEAYI3AgEEMBwGCisG
# AQQBgjcCAQsxDjAMBgorBgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCAH4meiIGao
# NU4H1IcYT0YlSTPdcEdNlHot0hKm86CngjBCBgorBgEEAYI3AgEMMTQwMqAUgBIA
# TQBpAGMAcgBvAHMAbwBmAHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0G
# CSqGSIb3DQEBAQUABIIBAEM3LuyUSVvB0DuBN1Yh6HuvAjmT25+nbtm/3jo8H4A9
# wm4r8t33SXkgJGbX17ollOPjoYMftwAPqW9G8f+XmUSLc9xAyzzUmjVcbrtrbeIN
# bms5uUQssI7Mifpzpge5imlmxg8TD39Cqb5SNPnvlB3xqLpy8zTKqTeBFPqs3bNi
# V74MxyhIhku4UEkGAwGq8eF1cwHetdnI+o5fjt9sXFY7vD5gQtf+hs0nu+G17fub
# g5lkmttKnesUzMvqT+GO2r6o7Q8FKItsTSHtdBiKL5gzb1f1uUArWqv20v7jiUd4
# QLwGPR8AEoEM2GKtFCa2xKYjexAeNnvX8NUf4oO2YGahghevMIIXqwYKKwYBBAGC
# NwMDATGCF5swgheXBgkqhkiG9w0BBwKggheIMIIXhAIBAzEPMA0GCWCGSAFlAwQC
# AQUAMIIBWgYLKoZIhvcNAQkQAQSgggFJBIIBRTCCAUECAQEGCisGAQQBhFkKAwEw
# MTANBglghkgBZQMEAgEFAAQgH1Z1+oXf/bWb8qAopUWwKcn+Jd4IAzVl9aMS9rv1
# 3uoCBmnsW6YZmBgTMjAyNjA0MzAwMDUwNDguMTI5WjAEgAIB9KCB2aSB1jCB0zEL
# MAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1v
# bmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEtMCsGA1UECxMkTWlj
# cm9zb2Z0IElyZWxhbmQgT3BlcmF0aW9ucyBMaW1pdGVkMScwJQYDVQQLEx5uU2hp
# ZWxkIFRTUyBFU046NTUxQS0wNUUwLUQ5NDcxJTAjBgNVBAMTHE1pY3Jvc29mdCBU
# aW1lLVN0YW1wIFNlcnZpY2WgghH9MIIHKDCCBRCgAwIBAgITMwAAAhvQsrgCZ/dy
# zwABAAACGzANBgkqhkiG9w0BAQsFADB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDAeFw0yNTA4MTQxODQ4MzBaFw0yNjExMTMxODQ4MzBaMIHTMQswCQYDVQQG
# EwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwG
# A1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMS0wKwYDVQQLEyRNaWNyb3NvZnQg
# SXJlbGFuZCBPcGVyYXRpb25zIExpbWl0ZWQxJzAlBgNVBAsTHm5TaGllbGQgVFNT
# IEVTTjo1NTFBLTA1RTAtRDk0NzElMCMGA1UEAxMcTWljcm9zb2Z0IFRpbWUtU3Rh
# bXAgU2VydmljZTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAI7Fnedm
# WZMweV3uYP5dhrDowM99LIOo1cXxSVfsOMSA1cmiNyzvGyKZs2LpdwGR4OdFCEPD
# 60kWRqUKhZETbvqN2CieINrhmAUZLB5x2EdLlUgkIOfE4ZGMnqZRl96ALxkVbjyK
# ULQIk7Ee+gP4HaFOxw8BG2+92ycE8q2yh4UflmjMvQ0ByOJOUKOPm2Q7NJI++m74
# Sb3RlPkvM8UAae1AIYyZxaisSLrEiExO8wgkeNthC4ZIVVThaitsOodTALyC3u+o
# cUSHD49EgS9q/DvbceZ41OPrYNqwHVNed6Zsoams3aVHHGARPcA0RVHf3vQqFse0
# 3Z1InAfjGou0U+qrHu3uWhql9Qe254/2R7663xfgSRCJUvYg1wFIHpL12fhWZo7y
# 8D/nTftP3K4fvq+HvBZJxexF+iCX55jXgzf+vGefZG2idX/j+ZpymH8nQnmZsaxq
# UtLWlpA5N+g94z1WX5b8a3Pta4QiJTOb/WoCxBSNdkIgU36TgTga9wBgj5Pnh9Pp
# WrY0Go7oPtvwQ9dqm/NudNC0MrVFk9qLWvx2J0YEr9Y72dP3ZpdRbMVmMzpwq433
# Qf+zeqTckreL5/jxjenRS4pu5MaLPgfVn0D3syYt37issgwAfc0hz49WbvJ2X3nG
# SfbpuM4+wxYLyV0w05xuapRuGXWxUWv66385AgMBAAGjggFJMIIBRTAdBgNVHQ4E
# FgQUtr6fd/5cS6aTSvDpGridgLzZiFAwHwYDVR0jBBgwFoAUn6cVXQBeYl2D9OXS
# ZacbUzUZ6XIwXwYDVR0fBFgwVjBUoFKgUIZOaHR0cDovL3d3dy5taWNyb3NvZnQu
# Y29tL3BraW9wcy9jcmwvTWljcm9zb2Z0JTIwVGltZS1TdGFtcCUyMFBDQSUyMDIw
# MTAoMSkuY3JsMGwGCCsGAQUFBwEBBGAwXjBcBggrBgEFBQcwAoZQaHR0cDovL3d3
# dy5taWNyb3NvZnQuY29tL3BraW9wcy9jZXJ0cy9NaWNyb3NvZnQlMjBUaW1lLVN0
# YW1wJTIwUENBJTIwMjAxMCgxKS5jcnQwDAYDVR0TAQH/BAIwADAWBgNVHSUBAf8E
# DDAKBggrBgEFBQcDCDAOBgNVHQ8BAf8EBAMCB4AwDQYJKoZIhvcNAQELBQADggIB
# AGZFNV8UA+DkzNxk4bd9k10oSHzwaDH0rBbAUKhTmaiyTsciTpZSARaZqbzrRjT5
# AuWfJXRvGgqb4BTaP4w1nk+RYlud3QI/Sp2cabENz3+X0c0hh0XMRDDnVyFcwycH
# GVF9HI38Z2u8nTb/Hlwf15Ohuksq0djh+ktSxzFtdZt1Lyhfni4yD5eOa8Yprgwq
# BHfmndJTgFwOf72TijeZ/3j2Hj9C0XIWV9EOh/J/2ZkjzJW5YtzDvOdUNPUZk/2R
# h2vvxXcvliw68HGMpFfZlMv+E28CsOhbXUemTx8THSItaZPGNpgvxswqtCwrB9Lk
# xXkOkOzXNzEZhEf95i1lIW2lh4F9RW2HIb0dtm/gbqfmD0eUP9AYWmgDegCAX3Br
# Prv5yaCAcsmSgPHE8gpp1CP+L1ug+L8sIN1wRX+H9g8BR8v3r7AvufCjJfpNsGtO
# V9pCtE/2wjy4WqL/WV8qG2sHzTi2Bomrik9hVr28GcxyBQk8YwcMOj7ebkbwhP45
# 1HH/8YZThjJ+oijvV7ePb2UxNknyAZP9+Ii00QSeh+2hj000J82tzn1rtf3UcnAu
# lpeaJ7Nz45xl00iksV5ZST5oOkf7pRqJz/1AmKCepjfhF438gyz1y6rK/dflUxta
# 2M0Qoz8ARQB7+BCMGhNGowq3++XlBiN/qF1NFD+q5aGfMIIHcTCCBVmgAwIBAgIT
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
# je6CbaUFEMFxBmoQtB1VM1izoXBm8qGCA1gwggJAAgEBMIIBAaGB2aSB1jCB0zEL
# MAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1v
# bmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEtMCsGA1UECxMkTWlj
# cm9zb2Z0IElyZWxhbmQgT3BlcmF0aW9ucyBMaW1pdGVkMScwJQYDVQQLEx5uU2hp
# ZWxkIFRTUyBFU046NTUxQS0wNUUwLUQ5NDcxJTAjBgNVBAMTHE1pY3Jvc29mdCBU
# aW1lLVN0YW1wIFNlcnZpY2WiIwoBATAHBgUrDgMCGgMVAIaFeq+PTOBgXeNStUWA
# dWdH+M7goIGDMIGApH4wfDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjEmMCQGA1UEAxMdTWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwDQYJ
# KoZIhvcNAQELBQACBQDtnMiWMCIYDzIwMjYwNDI5MTgxMjM4WhgPMjAyNjA0MzAx
# ODEyMzhaMHYwPAYKKwYBBAGEWQoEATEuMCwwCgIFAO2cyJYCAQAwCQIBAAIBIgIB
# /zAHAgEAAgITszAKAgUA7Z4aFgIBADA2BgorBgEEAYRZCgQCMSgwJjAMBgorBgEE
# AYRZCgMCoAowCAIBAAIDB6EgoQowCAIBAAIDAYagMA0GCSqGSIb3DQEBCwUAA4IB
# AQBeu5vaAJiws1Cggdf3K2P+Whxkh/tfE8QZEikxgLi7B9o08VspEDC/2FZsDcTz
# 52qNzvzNQykQZ8lsMGE/xSo9wnSXcRvc++UbdJpbVBJPFk5l3GKLlF6z5NAUgkOK
# d5wN47V06/hWjQgno4sfsW4DcDUwH64YCEnahsfQmvMTRHcrwWfDe06UqVyd19Mz
# cXffV8wAjpkP8f6vWtwDfkkstwPlQ6OzFIP9wyOkeJUpE5IejVYMbr8ouTj0UH6K
# zUaXy/7tezzWoyrgQQ7BiNjHw0mGnpIpXx2fcQ4iunirisLg4yLsnlTTzdjqKlJg
# 9T4uW/IRnIGZFnxUXatuISaGMYIEDTCCBAkCAQEwgZMwfDELMAkGA1UEBhMCVVMx
# EzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoT
# FU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMdTWljcm9zb2Z0IFRpbWUt
# U3RhbXAgUENBIDIwMTACEzMAAAIb0LK4Amf3cs8AAQAAAhswDQYJYIZIAWUDBAIB
# BQCgggFKMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRABBDAvBgkqhkiG9w0BCQQx
# IgQgH186NmIr70MizZj8LhuiY8WlWj5uH8AAwxEy4/3NLnswgfoGCyqGSIb3DQEJ
# EAIvMYHqMIHnMIHkMIG9BCAwJRSVuD2jmMcQCFXdLuJAwDpUVNZ6bc6dfJU83Q2L
# gDCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5ndG9uMRAw
# DgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24x
# JjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEwAhMzAAACG9Cy
# uAJn93LPAAEAAAIbMCIEIOL2akxnHv2Qhc+SrvtstlxEk7JMwaIRkJS5FUdNktNK
# MA0GCSqGSIb3DQEBCwUABIICADhNNx4nLYM7dIp07PHCG1L+GfSF4VOlPinYYZPU
# ckQWXA1uSOZIhZZvnJDcobL1CWM/geOJHP2VaX5AY7pKSVZlwVz2OqWoGPtlwryD
# 2yLXq6OzGyrCpX1W9jb2iKkzU4vsnUbdS1Olpk6m9yMRoCOBG+r3/YM0st4eFUat
# gOCkUsvawDv0D4JFfcJOICbjj8Z/GPqYXeHvzCbwPSa34uwl50UFPq7iZNdzriqN
# RtFk81iZ3Q+8dPhXbcbU+RPuZsi8j1ebMX7ukZot/nMi1frezxQ82K7A42qNMyhY
# uANjWuIS3gqEGptPcwmjlt40rotuFzotZAzWcSlIhXPOONSJuEFFU0gqfhngJXez
# hiRDS8SKja2e2lO0nXDW/cLMKG0IuzPFHsSTUw6FYar51SKQH3GH4XistZDlUBuk
# kt0IvDOtyyw9TFtnCV+81ixR8oaHdtI92ITrSUKOtATSniomwVa5BxOLGh4zANuM
# zPwgZyXG7fpBp60EOVIR4LGfo9KPZPIL42SO+CXkTsbEOHIsKP1lpjsQfMjyuSl5
# +hQIAMGorP23cyBiY65B4TjfqcmnO9Uh3tDd+U9kf3T8eRx8H14mGVGwgtF3RqLM
# MAIk/nDlP+pEY/5tsZkTrosXIl47la/qCTT1qARxuhUyawmjW3X2babwhKpa/82c
# j7Eq
# SIG # End Windows Authenticode signature block