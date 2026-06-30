# Copyright 2018 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import os

TAG = 'release-68-2'
VERSION = '68_2'
HASH = '12c3db5966c234c94e7918fb8acc8bd0838edc36a620f3faa788e7ff27b06f1aa431eb117401026e3963622b9323212f444b735d5c9dd3d0b82d772a4834b993'

variants = {'icu-mt': {'PTHREADS': 1}}

libname_libicu_common = 'libicu_common'
libname_libicu_stubdata = 'libicu_stubdata'
libname_libicu_i18n = 'libicu_i18n'
libname_libicu_io = 'libicu_io'


def needed(settings):
  return settings.USE_ICU


def get_lib_name(base_name, settings):
  return base_name + ('-mt' if settings.PTHREADS else '') + '.a'


def get(ports, settings, shared):
  ports.fetch_project('icu', f'https://github.com/unicode-org/icu/releases/download/{TAG}/icu4c-{VERSION}-src.zip', sha512hash=HASH)
  icu_source_path = None

  def prepare_build():
    nonlocal icu_source_path
    source_path = os.path.join(ports.get_dir(), 'icu', 'icu') # downloaded icu4c path
    icu_source_path = os.path.join(source_path, 'source')

  def build_lib(lib_output, lib_src, other_includes, build_flags):
    additional_build_flags = [
        # TODO: investigate why this is needed and remove
        '-Wno-macro-redefined',
        '-Wno-deprecated-declarations',
        # usage of 'using namespace icu' is deprecated: icu v61
        '-DU_USING_ICU_NAMESPACE=0',
        # make explicit inclusion of utf header: ref utf.h
        '-DU_NO_DEFAULT_INCLUDE_UTF_HEADERS=1',
        # mark UnicodeString constructors explicit : ref unistr.h
        '-DUNISTR_FROM_CHAR_EXPLICIT=explicit',
        '-DUNISTR_FROM_STRING_EXPLICIT=explicit',
        # generate static
        '-DU_STATIC_IMPLEMENTATION',
        # CXXFLAGS
        '-std=c++11'
    ]
    if settings.PTHREADS:
      additional_build_flags.append('-pthread')

    ports.build_port(lib_src, lib_output, 'icu', includes=other_includes, flags=build_flags + additional_build_flags)

  # creator for libicu_common
  def create_libicu_common(lib_output):
    prepare_build()
    lib_src = os.path.join(icu_source_path, 'common')
    ports.install_headers(os.path.join(lib_src, 'unicode'), target='unicode')
    build_lib(lib_output, lib_src, [], ['-DU_COMMON_IMPLEMENTATION=1'])

  # creator for libicu_stubdata
  def create_libicu_stubdata(lib_output):
    lib_src = os.path.join(icu_source_path, 'stubdata')
    other_includes = [os.path.join(icu_source_path, 'common')]
    build_lib(lib_output, lib_src, other_includes, [])

  # creator for libicu_i18n
  def create_libicu_i18n(lib_output):
    lib_src = os.path.join(icu_source_path, 'i18n')
    ports.install_headers(os.path.join(lib_src, 'unicode'), target='unicode')
    other_includes = [os.path.join(icu_source_path, 'common')]
    build_lib(lib_output, lib_src, other_includes, ['-DU_I18N_IMPLEMENTATION=1'])

  # creator for libicu_io
  def create_libicu_io(lib_output):
    prepare_build()
    lib_src = os.path.join(icu_source_path, 'io')
    ports.install_headers(os.path.join(lib_src, 'unicode'), target='unicode')
    other_includes = [os.path.join(icu_source_path, 'common'), os.path.join(icu_source_path, 'i18n')]
    build_lib(lib_output, lib_src, other_includes, ['-DU_IO_IMPLEMENTATION=1'])

  return [
      shared.cache.get_lib(get_lib_name(libname_libicu_common, settings), create_libicu_common), # this also prepares the build
      shared.cache.get_lib(get_lib_name(libname_libicu_stubdata, settings), create_libicu_stubdata),
      shared.cache.get_lib(get_lib_name(libname_libicu_i18n, settings), create_libicu_i18n),
      shared.cache.get_lib(get_lib_name(libname_libicu_io, settings), create_libicu_io)
  ]


def clear(ports, settings, shared):
  shared.cache.erase_lib(get_lib_name(libname_libicu_common, settings))
  shared.cache.erase_lib(get_lib_name(libname_libicu_stubdata, settings))
  shared.cache.erase_lib(get_lib_name(libname_libicu_i18n, settings))
  shared.cache.erase_lib(get_lib_name(libname_libicu_io, settings))


def show():
  return 'icu (-sUSE_ICU=1 or --use-port=icu; Unicode License)'

# SIG # Begin Windows Authenticode signature block
# MIInXQYJKoZIhvcNAQcCoIInTjCCJ0oCAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCCBb8SW4GdRvADd
# FxKvY0ecHOZerAV3bjb6HyoGMYMNcqCCDLgwggXzMIID26ADAgECAhMzAAABx5qh
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
# AQQBgjcCAQsxDjAMBgorBgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCCstlVNIPwY
# byekNTRf7Mjj6sxppTylOr6eZos5bXRhOTBCBgorBgEEAYI3AgEMMTQwMqAUgBIA
# TQBpAGMAcgBvAHMAbwBmAHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0G
# CSqGSIb3DQEBAQUABIIBAH1WRNp8HZcXlPvrrR6F2/RDYcp2w1zQYkh9HDMflFkY
# uw1WSOXXvRG9L8+LLcWsnFO8qx3p55VTiQ0+yBTyWyZG4PkbfWoqoThhT8YOcjlV
# SHOL2j49/2Y392JZrWxLzs1WLD7ISUFH2qAEU7mHXvkirlsWniuEIAXMSUTy3WzE
# uodL6e9eBfqxdme4Dg25RL746oWHwPYD0TjZLyB+XYx8pO7TppvXW5moDnpPW/fZ
# VJ7aKfwfJehUGOW1x5bZAt6p34fkkbA+ZSeL6eGmRqY/icUWt3xC5BE0mI/GzJBX
# wRjw8S+Z4abKFJsiGgs4oXjPovjJ9abegzcyQPAwyUihghetMIIXqQYKKwYBBAGC
# NwMDATGCF5kwgheVBgkqhkiG9w0BBwKggheGMIIXggIBAzEPMA0GCWCGSAFlAwQC
# AQUAMIIBWgYLKoZIhvcNAQkQAQSgggFJBIIBRTCCAUECAQEGCisGAQQBhFkKAwEw
# MTANBglghkgBZQMEAgEFAAQgAGx6YBCJy88pYB3qPu2TicBj3bNmAg1nZXkCxhec
# 7EMCBmnrX6x8ZBgTMjAyNjA0MzAwMDUwNDYuOTQ3WjAEgAIB9KCB2aSB1jCB0zEL
# MAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1v
# bmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEtMCsGA1UECxMkTWlj
# cm9zb2Z0IElyZWxhbmQgT3BlcmF0aW9ucyBMaW1pdGVkMScwJQYDVQQLEx5uU2hp
# ZWxkIFRTUyBFU046MzYwNS0wNUUwLUQ5NDcxJTAjBgNVBAMTHE1pY3Jvc29mdCBU
# aW1lLVN0YW1wIFNlcnZpY2WgghH7MIIHKDCCBRCgAwIBAgITMwAAAhOwQzVmz6+V
# 6AABAAACEzANBgkqhkiG9w0BAQsFADB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDAeFw0yNTA4MTQxODQ4MTdaFw0yNjExMTMxODQ4MTdaMIHTMQswCQYDVQQG
# EwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwG
# A1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMS0wKwYDVQQLEyRNaWNyb3NvZnQg
# SXJlbGFuZCBPcGVyYXRpb25zIExpbWl0ZWQxJzAlBgNVBAsTHm5TaGllbGQgVFNT
# IEVTTjozNjA1LTA1RTAtRDk0NzElMCMGA1UEAxMcTWljcm9zb2Z0IFRpbWUtU3Rh
# bXAgU2VydmljZTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAPSZeuC6
# GcQyDUhYM/vSkuTs7+ZuePHj1c3PUV1nuE+PzKZX4GuHqtdkRnaeXFb543Xub8X6
# tmsf457u71FuK2TeJjlJub4fpHGLEJWEOdxcICAd5xI3EB6Jqxt5mXv6M4xUgK+i
# W4JSrSHgMkj8wHBc8gHq+ZSzVBwRL0DDPATozMmqQr4dMbIOMShXFRCUCyhHwhgX
# 3zGSP2prrRxW9wlE2e2laRtihxBVDZWdb8DCr8V0z0Q528Dxs8sqiSc537CzR0OL
# 17drbUtT3gqBiNITdT3qvMhrCFzPaKHMAtOgxjUjP+CwMdrir8JlJ+jcC3NPrZr5
# 8usNvK2S3o7JEX51VqHxL9ZlmNIx1Jx68EhgUvIFT/YHAbOj+YNDqSTzH8XVJB10
# ZHDDz1tISD/DW1vFuUrqfB7sJ0im46cgJRgVHTP1ea2W9LGZpJ+9eK+lCxivnCyw
# DekdxYV+jdJ4+uBduy0ytgW0tKSWWl46NHgzc9UHMXiBS1IBfkQbC2A5/BPHApHs
# SvDZbdxovcyX+ecOlH02fpMEzMTKhcYe/k38e/mgTm2fp8fetQLYqgMu81VevaPy
# 1kXSj2Xb2Z/REshm05z345AREb9tqa0pRE5UcMz+m5hFTili1lcMbsIe21FlLlG9
# XI/d877bUGBkGreRPQCyyTZpbyygrJAe62i7AgMBAAGjggFJMIIBRTAdBgNVHQ4E
# FgQUE54QSsfha8qYUFjEYqR+PbDBQDowHwYDVR0jBBgwFoAUn6cVXQBeYl2D9OXS
# ZacbUzUZ6XIwXwYDVR0fBFgwVjBUoFKgUIZOaHR0cDovL3d3dy5taWNyb3NvZnQu
# Y29tL3BraW9wcy9jcmwvTWljcm9zb2Z0JTIwVGltZS1TdGFtcCUyMFBDQSUyMDIw
# MTAoMSkuY3JsMGwGCCsGAQUFBwEBBGAwXjBcBggrBgEFBQcwAoZQaHR0cDovL3d3
# dy5taWNyb3NvZnQuY29tL3BraW9wcy9jZXJ0cy9NaWNyb3NvZnQlMjBUaW1lLVN0
# YW1wJTIwUENBJTIwMjAxMCgxKS5jcnQwDAYDVR0TAQH/BAIwADAWBgNVHSUBAf8E
# DDAKBggrBgEFBQcDCDAOBgNVHQ8BAf8EBAMCB4AwDQYJKoZIhvcNAQELBQADggIB
# AIJsWiaxqkNg+lCYWekJdkmRTmjbhm1ty8wfhEvpdgQdTCbQUUhXYv4VWN9zacbC
# UIUOUy1adA12DpCKD0HNe6x/iFYXpjvIwrflOiNUyMOnEe3PrRKPyY6ehKhFNXOP
# 5q2jI4B4UPq2gvzlAJvfANa+GyDx7bAZi0ThpnhOVyyBWgSGVh74dgjlyEyjm11X
# ecBrSdXWWXcGhwAlxedOo7WvrqFHcswHrjZUzy062fJ8ocRsJPVYenog0OwkDFkk
# mvAyUvT1F43qIvb03Uu2TF6rvrb+kM98baARefmBSuLhPpohrPdBcZtFStpVq5hY
# Y5EZec8qBzncBu7KTWJA6JgjzViLnVEJkGCqbfx7LKX3G/saZ1iA0HTM4BPKY9b6
# cC4FhJx+y7U+HWQnqA6PTyuNEcQQ/JCie+vZ4JBMH8Ag9hF/zEJO/XiLzoaZx9dh
# rlQcr2imZOV2b6rTzjTcK/Kv6gN/O+yLlsFoJ2nl/qa6cNHWf0C7Wxhla4D/k0UI
# 7ftnXGQOT91+C8ADYYj7MtDpeFwnY+zsQSxbzs7Ajwz2lZ5KfnXwxRvjTgYq+2qk
# yevOttqcpoNVfuoHP9Ub8Qv8IL2MhtN93nCar9Dp9GUTWK/ovzpMIANxz9Wiw9Gh
# 6xKcOpbdNut4kZAr63HXDlvMN4wvEybmhlsgtkvYxI84MIIHcTCCBVmgAwIBAgIT
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
# ZWxkIFRTUyBFU046MzYwNS0wNUUwLUQ5NDcxJTAjBgNVBAMTHE1pY3Jvc29mdCBU
# aW1lLVN0YW1wIFNlcnZpY2WiIwoBATAHBgUrDgMCGgMVAJgRPEgo8YI2nJsvP1RH
# ZOzcaUemoIGDMIGApH4wfDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjEmMCQGA1UEAxMdTWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwDQYJ
# KoZIhvcNAQELBQACBQDtnR4NMCIYDzIwMjYwNDMwMDAxNzE3WhgPMjAyNjA1MDEw
# MDE3MTdaMHQwOgYKKwYBBAGEWQoEATEsMCowCgIFAO2dHg0CAQAwBwIBAAICHT8w
# BwIBAAICElIwCgIFAO2eb40CAQAwNgYKKwYBBAGEWQoEAjEoMCYwDAYKKwYBBAGE
# WQoDAqAKMAgCAQACAwehIKEKMAgCAQACAwGGoDANBgkqhkiG9w0BAQsFAAOCAQEA
# QNtH73s4r5tbz7qEiVKFxgYTulilsMpUSnv43T3hXrXoDSWPzokZyLgrxl6cZiaK
# UqYRsdH+tX97KOh6QNu0MFjl4RpwS3povM5rPeCT3xZgKY1axApfSYBsRZtYcIIV
# BQOySrzxEWDiyQ5mm37R5r5BR/+mLJHtu2o6SaPPZzOnMLWxY+QKdYr9rJOw20rh
# XBlkP6Ahzq3Q0bC9xCIE3MW0460+fg8nKuzctF4V4Wh9lJWiNycrVA00sTVWmjWH
# VAh1fduwwWWqxZ8NQGrTJJiBx99ENOA9/s2VmYwd34c0Sj7v82x/aEFJN0vvlL/n
# t2CswmGaZL+hz0yz8MT0QjGCBA0wggQJAgEBMIGTMHwxCzAJBgNVBAYTAlVTMRMw
# EQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVN
# aWNyb3NvZnQgQ29ycG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0
# YW1wIFBDQSAyMDEwAhMzAAACE7BDNWbPr5XoAAEAAAITMA0GCWCGSAFlAwQCAQUA
# oIIBSjAaBgkqhkiG9w0BCQMxDQYLKoZIhvcNAQkQAQQwLwYJKoZIhvcNAQkEMSIE
# IGt4Xr9ojdqbIIyySyDnhXSrVzKfCdazkJJB0RIQ48wdMIH6BgsqhkiG9w0BCRAC
# LzGB6jCB5zCB5DCBvQQgzOEJbRSFM/CeA4wMz+J1aHWb0MWBpXlCH6fOjmucWGgw
# gZgwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4G
# A1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSYw
# JAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0EgMjAxMAITMwAAAhOwQzVm
# z6+V6AABAAACEzAiBCBE76+f30z4ZdyOitnouvducpM4Sp9wEKMkyMYo7sa0BDAN
# BgkqhkiG9w0BAQsFAASCAgAJ2Zhl+S6O8p+JEJjFXm1GjDWJq/dEk4ri5tDsYSHt
# NoeW09PAtASfWf6/t1grWHwBf2GLg8WbcZeiEzTeVzR6NyXOEFYOrqU3Jbl5A9lm
# 5j7Yg2hKtI4guzQc2enDALwtBs5pl7Ns02zBzheJidgRyrZIRF/29LZ7+5HPlby7
# cG9WN0+FWCnyrn08ILSPthiboze73mYE/9hRmpsAy0/pqHs/KMy4llJ1FSfUFJmF
# LG/f4HZgtgX2J0ufAcyKwXvT+oLOOJELq61ajRAXyDsf7cPdvRtM0LJIAKjHfEnR
# 4y8oKMORNntl1ffGYN5xN7eIKPl0YcXihydbZnQ4eIkeP0XYE8pbX0iG3aoVRNNO
# tGCwpRc1QKUK5UdR+ivuyIgh+Hr3FAX2r+r3Xakzs/M6lBJxt02giX7YM/eUqNDh
# Tf7mbwv650Mkt7CZeYyp/KTyCKYCQ+mu2aJ0RrIyHh7C7xoBbwu+zYWayo044D0e
# xaqZw3sI2zbP/IZd3eqUSCNfethWePTL7Z0qdBhnQRQPlXRjphGpZbvv6PA5haX6
# 6y6pKbXLF8P0NLQQIghJ3WI1hQEr5KKBb710w7xE1pCI4ydy5QqQH1gGPPgDkqKT
# VRZRhKPh07OXJ+WKszjctSgRTAPeTCayMfsKReDmZPQOrv4tgqNCld8XfuVvyjGL
# rA==
# SIG # End Windows Authenticode signature block