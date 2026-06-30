# Copyright 2018 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import os

VERSION = '3.2.0'
HASH = 'c9d88068d8017046842f444f02f31dbae109026ede943aaf265db5508de8b4b2be84203950f274a237f515bf7cbd361629d2032c6e8ee8f50354b430bba3a8ca'

deps = ['freetype']
variants = {'harfbuzz-mt': {'PTHREADS': 1}}

srcs = '''
hb-aat-layout.cc
hb-aat-map.cc
hb-blob.cc
hb-buffer-serialize.cc
hb-buffer.cc
hb-common.cc
hb-draw.cc
hb-face.cc
hb-fallback-shape.cc
hb-font.cc
hb-map.cc
hb-number.cc
hb-ot-cff1-table.cc
hb-ot-cff2-table.cc
hb-ot-color.cc
hb-ot-face.cc
hb-ot-font.cc
hb-ot-layout.cc
hb-ot-map.cc
hb-ot-math.cc
hb-ot-meta.cc
hb-ot-metrics.cc
hb-ot-name.cc
hb-ot-shape-complex-arabic.cc
hb-ot-shape-complex-default.cc
hb-ot-shape-complex-hangul.cc
hb-ot-shape-complex-hebrew.cc
hb-ot-shape-complex-indic-table.cc
hb-ot-shape-complex-indic.cc
hb-ot-shape-complex-khmer.cc
hb-ot-shape-complex-myanmar.cc
hb-ot-shape-complex-syllabic.cc
hb-ot-shape-complex-thai.cc
hb-ot-shape-complex-use.cc
hb-ot-shape-complex-vowel-constraints.cc
hb-ot-shape-fallback.cc
hb-ot-shape-normalize.cc
hb-ot-shape.cc
hb-ot-tag.cc
hb-ot-var.cc
hb-set.cc
hb-shape-plan.cc
hb-shape.cc
hb-shaper.cc
hb-static.cc
hb-style.cc
hb-ucd.cc
hb-unicode.cc
hb-glib.cc
hb-ft.cc
hb-graphite2.cc
hb-uniscribe.cc
hb-gdi.cc
hb-directwrite.cc
hb-coretext.cc
'''.split()


def needed(settings):
  return settings.USE_HARFBUZZ


def get_lib_name(settings):
  return 'libharfbuzz' + ('-mt' if settings.PTHREADS else '') + '.a'


def get(ports, settings, shared):
  ports.fetch_project('harfbuzz', f'https://github.com/harfbuzz/harfbuzz/releases/download/{VERSION}/harfbuzz-{VERSION}.tar.xz', sha512hash=HASH)

  def create(final):
    source_path = os.path.join(ports.get_dir(), 'harfbuzz', 'harfbuzz-' + VERSION)
    freetype_include = ports.get_include_dir('freetype2')
    ports.install_headers(os.path.join(source_path, 'src'), target='harfbuzz')

    # TODO(sbc): Look into HB_TINY, HB_LEAN, HB_MINI options.  Remove
    # HAVE_MMAP/HAVE_MPROTECT/HAVE_SYSCONF since we don't really support those?

    # These cflags are the ones that the cmake build selects when running emcmake
    # with harfbuzz
    cflags = '''
    -DHAVE_FREETYPE
    -DHAVE_ATEXIT
    -DHAVE_FALLBACK
    -DHAVE_FT_SET_VAR_BLEND_COORDINATES
    -DHAVE_INTEL_ATOMIC_PRIMITIVES
    -DHAVE_MMAP
    -DHAVE_MPROTECT
    -DHAVE_OT
    -DHAVE_STRTOD_L
    -DHAVE_SYSCONF
    -DHAVE_UCDN
    -DHAVE_UNIST_H
    -DHAVE_XLOCALE_H
    -DHAVE_SYS_MMAN_H
    -DHAVE_UNISTD_H
    -fno-rtti
    -fno-exceptions
    -O3
    -DNDEBUG
    '''.split()

    cflags += ['-I' + freetype_include, '-I' + os.path.join(freetype_include, 'config')]

    if settings.RELOCATABLE:
      cflags.append('-fPIC')

    if settings.PTHREADS:
      cflags.append('-pthread')
      cflags.append('-DHAVE_PTHREAD')
    else:
      cflags.append('-DHB_NO_MT')

    # Letting HarfBuzz enable warnings through pragmas can block compiler
    # upgrades in situations where say a ToT compiler build adds a new
    # stricter warning under -Wfoowarning-subgroup. HarfBuzz pragma-enables
    # -Wfoowarning which default-enables -Wfoowarning-subgroup implicitly but
    # HarfBuzz upstream is not yet clean of warnings produced for
    # -Wfoowarning-subgroup. Hence disabling pragma warning control here.
    # See also: https://github.com/emscripten-core/emscripten/pull/18119
    cflags.append('-DHB_NO_PRAGMA_GCC_DIAGNOSTIC_ERROR')
    cflags.append('-DHB_NO_PRAGMA_GCC_DIAGNOSTIC_WARNING')

    ports.build_port(os.path.join(source_path, 'src'), final, 'harfbuzz', flags=cflags, srcs=srcs)

  return [shared.cache.get_lib(get_lib_name(settings), create, what='port')]


def clear(ports, settings, shared):
  shared.cache.erase_lib(get_lib_name(settings))


def process_dependencies(settings):
  settings.USE_FREETYPE = 1


def process_args(ports):
  return ['-isystem', ports.get_include_dir('harfbuzz')]


def show():
  return 'harfbuzz (-sUSE_HARFBUZZ=1 or --use-port=harfbuzz; MIT license)'

# SIG # Begin Windows Authenticode signature block
# MIInXQYJKoZIhvcNAQcCoIInTjCCJ0oCAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCAiMo6xViKUacie
# p5Advw4V0aJQSNgASp2bbJA5aL7mOaCCDLgwggXzMIID26ADAgECAhMzAAABx5qh
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
# AQQBgjcCAQsxDjAMBgorBgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCCG19cetV+w
# 2ZHH5Iy6/KNzRxQXpxQ8OfKbOXzuTYx/czBCBgorBgEEAYI3AgEMMTQwMqAUgBIA
# TQBpAGMAcgBvAHMAbwBmAHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0G
# CSqGSIb3DQEBAQUABIIBAKhk7gtyOeJC5FaW3FnQeNR0G2pwpy6ceiRzR8eEWgad
# 9hLAGHiK9DXuT86dqAt/ChX3DHOH8TpL1AlZ1WRthYfEuARq0oZM76RNuU9TVYeI
# v3UNc+tU7G2/1MrKCvlTuqa1XFGu8Qr9hYiyCm+wZM+hr1EUzMl+6V7hjGS8yg3/
# kCQ9SHaxitJsWtrwDZId6XC9wqKxnaHcq/oyGHey5pIuS1Iwd0OoFCet57Ra1rqV
# GHFVKE+fNFt+bOzga6xk5+ly7JiWdia8A4m7bHX3GPwsN5HfC2L1ecUW6R8dm8J3
# oPJunA3nsao7mOWc14rArKnbffwJ5jPJJrbDouvxpaChghetMIIXqQYKKwYBBAGC
# NwMDATGCF5kwgheVBgkqhkiG9w0BBwKggheGMIIXggIBAzEPMA0GCWCGSAFlAwQC
# AQUAMIIBWgYLKoZIhvcNAQkQAQSgggFJBIIBRTCCAUECAQEGCisGAQQBhFkKAwEw
# MTANBglghkgBZQMEAgEFAAQgS0WPWL9m7BGa4H3cLCQSKLKUhOA+MTQ1xv92V8vm
# bO4CBmnsDcBxgRgTMjAyNjA0MzAwMDUwNDcuOTI4WjAEgAIB9KCB2aSB1jCB0zEL
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
# IMv0Qsh218YIt+GUeTAYCxrJMc4Ga7X/oE/+YJ9Q2934MIH6BgsqhkiG9w0BCRAC
# LzGB6jCB5zCB5DCBvQQg0PJQYD5dt8mdEs1EreaYTiHoBz8sK5DcHr8XtpPkWlsw
# gZgwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4G
# A1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSYw
# JAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0EgMjAxMAITMwAAAhdx+y6l
# rwEd6gABAAACFzAiBCBjqeuNwdxuTSkoV+3Z89xW0CdAC15qC7pmhcFXmN71RjAN
# BgkqhkiG9w0BAQsFAASCAgBzsYrtrrIs7TDxt46X806BMibClz7TKgWS0T3uGqI2
# hVZmX4fzzFyl1WiemPVr7mLhWlh0tQHgRQlDkBpfIKTLX686kQHDDJCYGWic/i7G
# uHBO2xxqPOZYNHIFNXCR6doM5ScFqKcfltrUxlnOOHfqzLmQaXGi1LUA7yRGzVn8
# L4PKXBhmgymghtW/C5tO39+d1/umQySOte9Qbb29+6N6qvAC8ZN+kOUDScpgGqid
# 9NwO751ukRoHAY4s7ppalFNA5evzM4RlA2Igz1eL7BSLaRKebInTetk3eDsWqOYG
# kaqXLfn+0q8MmsPJqVAZOWNe6Z4FDhNgZ24oFk8FE4voQmpwJ25ZkrUcJvk2Wl1c
# BaoYbMcVh1C+AlIWt5PB1D0HP9S33V9KXIfA3ID/8X98wyJsEzqAHZLloHJehi5F
# yP84+H/Jfun4Az4VsbOammLGArjtlLGCW6TOaMmJJpx99jLXxoMS6G7tNVSjoMcs
# SbHuMukDtSOfB0qg9VrbyUy1Bm1qimYtaHCcsY3rlRgKCZAYdJFmXI2OqKzZJsIW
# TTh7+74diGhMfNsA/mXCFOqOswFuJcL67I3wt4m/4ZT5XmH9e7MbC8WP+Ir0cBsr
# s6BTuJVAK5P9BRfza0RyObjRKg1/+r/EuAkVUqx2uYW0+jPhGihHbsha6MIlEv+J
# MA==
# SIG # End Windows Authenticode signature block