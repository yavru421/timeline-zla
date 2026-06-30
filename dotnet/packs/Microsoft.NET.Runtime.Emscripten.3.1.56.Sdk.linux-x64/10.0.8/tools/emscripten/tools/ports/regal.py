# Copyright 2015 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import os

TAG = 'version_7'
HASH = 'a921dab254f21cf5d397581c5efe58faf147c31527228b4fb34aed75164c736af4b3347092a8d9ec1249160230fa163309a87a20c2b9ceef8554566cc215de9d'

variants = {'regal-mt': {'PTHREADS': 1}}


def needed(settings):
  return settings.USE_REGAL


def get_lib_name(settings):
  return 'libregal' + ('-mt' if settings.PTHREADS else '') + '.a'


def get(ports, settings, shared):
  ports.fetch_project('regal', f'https://github.com/emscripten-ports/regal/archive/{TAG}.zip', sha512hash=HASH)

  def create(final):
    source_path = os.path.join(ports.get_dir(), 'regal', 'regal-' + TAG)

    # copy sources
    # only what is needed is copied: regal, boost, lookup3
    source_path_src = os.path.join(source_path, 'src')

    source_path_regal = os.path.join(source_path_src, 'regal')
    source_path_boost = os.path.join(source_path_src, 'boost')
    source_path_lookup3 = os.path.join(source_path_src, 'lookup3')

    # includes
    source_path_include = os.path.join(source_path, 'include', 'GL')
    ports.install_headers(source_path_include, target='GL')

    # build
    srcs_regal = ['regal/RegalShaderInstance.cpp',
                  'regal/RegalIff.cpp',
                  'regal/RegalQuads.cpp',
                  'regal/Regal.cpp',
                  'regal/RegalLog.cpp',
                  'regal/RegalInit.cpp',
                  'regal/RegalBreak.cpp',
                  'regal/RegalUtil.cpp',
                  'regal/RegalEmu.cpp',
                  'regal/RegalEmuInfo.cpp',
                  'regal/RegalFrame.cpp',
                  'regal/RegalHelper.cpp',
                  'regal/RegalMarker.cpp',
                  'regal/RegalTexC.cpp',
                  'regal/RegalCacheShader.cpp',
                  'regal/RegalCacheTexture.cpp',
                  'regal/RegalConfig.cpp',
                  'regal/RegalContext.cpp',
                  'regal/RegalContextInfo.cpp',
                  'regal/RegalDispatch.cpp',
                  'regal/RegalStatistics.cpp',
                  'regal/RegalLookup.cpp',
                  'regal/RegalPlugin.cpp',
                  'regal/RegalShader.cpp',
                  'regal/RegalToken.cpp',
                  'regal/RegalDispatchGlobal.cpp',
                  'regal/RegalDispatcher.cpp',
                  'regal/RegalDispatcherGL.cpp',
                  'regal/RegalDispatcherGlobal.cpp',
                  'regal/RegalDispatchEmu.cpp',
                  'regal/RegalDispatchGLX.cpp',
                  'regal/RegalDispatchLog.cpp',
                  'regal/RegalDispatchCode.cpp',
                  'regal/RegalDispatchCache.cpp',
                  'regal/RegalDispatchError.cpp',
                  'regal/RegalDispatchLoader.cpp',
                  'regal/RegalDispatchDebug.cpp',
                  'regal/RegalDispatchPpapi.cpp',
                  'regal/RegalDispatchStatistics.cpp',
                  'regal/RegalDispatchStaticES2.cpp',
                  'regal/RegalDispatchStaticEGL.cpp',
                  'regal/RegalDispatchTrace.cpp',
                  'regal/RegalDispatchMissing.cpp',
                  'regal/RegalPixelConversions.cpp',
                  'regal/RegalHttp.cpp',
                  'regal/RegalDispatchHttp.cpp',
                  'regal/RegalJson.cpp',
                  'regal/RegalFavicon.cpp',
                  'regal/RegalMac.cpp',
                  'regal/RegalSo.cpp',
                  'regal/RegalFilt.cpp',
                  'regal/RegalXfer.cpp',
                  'regal/RegalX11.cpp',
                  'regal/RegalDllMain.cpp']

    srcs_regal = [os.path.join(source_path_src, s) for s in srcs_regal]

    flags = [
      '-DNDEBUG',
      '-DREGAL_LOG=0',  # Set to 1 if you need to have some logging info
      '-DREGAL_MISSING=0',  # Set to 1 if you don't want to crash in case of missing GL implementation
      '-std=gnu++14',
      '-fno-rtti',
      '-fno-exceptions', # Disable exceptions (in STL containers mostly), as they are not used at all
      '-O3',
      '-I' + source_path_regal,
      '-I' + source_path_lookup3,
      '-I' + source_path_boost,
      '-Wno-deprecated-register',
      '-Wno-unused-parameter'
    ]
    if settings.PTHREADS:
      flags += ['-pthread']

    ports.build_port(source_path_src, final, 'regal', srcs=srcs_regal, flags=flags)

  return [shared.cache.get_lib(get_lib_name(settings), create, what='port')]


def clear(ports, settings, shared):
  shared.cache.erase_lib(get_lib_name(settings))


def linker_setup(ports, settings):
  settings.FULL_ES2 = 1


def show():
  return 'regal (-sUSE_REGAL=1 or --use-port=regal; Regal license)'

# SIG # Begin Windows Authenticode signature block
# MIInNQYJKoZIhvcNAQcCoIInJjCCJyICAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCBlJvl0XaLqaUSq
# ku59tBodvNL/yuV/LJrSoF7RDqNST6CCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
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
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCCpWX2HgrlAlQ5H1boKQ8mNYN0HHYwv
# IpLAHOIU0b5lZTBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# AFHrGNcI5vN+IeWx/Xd3cZVNDUflERmGX8F0TYRXUYZEM5kLH0eFfhyTFFr1Y5SI
# rL8uqFizmV9qZ1auuNcZKHHiTir9jgjjPAuTI7skaNKrWtKcLV0plIlz8d4NM/34
# GIdayr6Fyd+6DW6zid2t0EWLgjWXJCh5jbGZYS3peIVgYLcbvHMwAz1xgipS+aLl
# rohsL0dt+YDi1U4b1a1OJND6u6iohcNf3rhGdvsyCBv+Qur0+juGPnlfcVWVhaXH
# QhZPKxyaZQ/WHXQYqLWOj6G7dbwXh7Ppw7MXsv5gReDjt0aLsfQwO+Jo+/AhrPAl
# 5o8xko+GwavYPVzkECiYiY6hgheUMIIXkAYKKwYBBAGCNwMDATGCF4Awghd8Bgkq
# hkiG9w0BBwKgghdtMIIXaQIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQghXrwR1zIEW8xIq8VwEkx4MSwg18mSRFSjV5NNwMeAFECBmnn68MwMxgTMjAy
# NjA0MzAwMDUwNDkuNzk2WjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
# BgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1p
# Y3Jvc29mdCBDb3Jwb3JhdGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2Eg
# T3BlcmF0aW9uczEnMCUGA1UECxMeblNoaWVsZCBUU1MgRVNOOkYwMDItMDVFMC1E
# OTQ3MSUwIwYDVQQDExxNaWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNloIIR6jCC
# ByAwggUIoAMCAQICEzMAAAIgJOHm4Be5tI4AAQAAAiAwDQYJKoZIhvcNAQELBQAw
# fDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1Jl
# ZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMd
# TWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwHhcNMjYwMjE5MTkzOTUyWhcN
# MjcwNTE3MTkzOTUyWjCByzELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2EgT3BlcmF0aW9uczEnMCUG
# A1UECxMeblNoaWVsZCBUU1MgRVNOOkYwMDItMDVFMC1EOTQ3MSUwIwYDVQQDExxN
# aWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNlMIICIjANBgkqhkiG9w0BAQEFAAOC
# Ag8AMIICCgKCAgEA0WGO8q+4o1ugkde/Lir3iDLn7rVjonMYCcCjnHv9hjkHHrrO
# mVn19eIt4zYNyTj+zBiTJDgLnMFgcIgPFEafmWJBo6VaFZBmbFdu1o6i8KX9gMKg
# bCf086sBOyRRWsbqdy3cY/Bo3ScpgxUa3VTf6WB6ARa4w9SJCA7vG9Qlp/LYKJoi
# kUmPkk7yavfZlZHaYTASFBjnoEJ8vKkXduFTBNMYvDqJpLPWavRIw3ihxqbwG11B
# EOpt3ETqBD4UxP5osHkB/U6ibdyDrKj79y/Lq6Iwe+O1wQtstAgyB5Si3C5d2RvA
# +yVyp1kxXp95rDDyaXL60N81AVSax/5iN0cR5gofaaQz9LhtfjycJOh/8frH6BvY
# VuuMaF5KcegxHzWTX3F3Sm1xdvFxF3SzZ86N0izVcpnkCYTajkioZ1POEJypq4xJ
# OeNSYrq5QwpAljvZVAVDG/cdJ8n11GzUT1S4D/j0zEXVzqMCXWAswkHzdmai9LOG
# CNvBdQ25+wYMNhOD9RPbp7LzMyR7c4Utk4d06QnwWzhmpSJRfcfwyWf7LJv8ss0/
# WLSBXqpnzcQT0xN2jroeh8ZkyAs32AAE71jYQW6NfUMLIz3gPSb4akywtilDYK16
# 6BsuHg2aNJ+4xWI2ZFIodU8vvBOqhL1djWumeYFMg+WvrRxg5quvQplIh38CAwEA
# AaOCAUkwggFFMB0GA1UdDgQWBBTbyJzgiIcRgPJmO5dYNO1B78jYMzAfBgNVHSME
# GDAWgBSfpxVdAF5iXYP05dJlpxtTNRnpcjBfBgNVHR8EWDBWMFSgUqBQhk5odHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBUaW1l
# LVN0YW1wJTIwUENBJTIwMjAxMCgxKS5jcmwwbAYIKwYBBQUHAQEEYDBeMFwGCCsG
# AQUFBzAChlBodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01p
# Y3Jvc29mdCUyMFRpbWUtU3RhbXAlMjBQQ0ElMjAyMDEwKDEpLmNydDAMBgNVHRMB
# Af8EAjAAMBYGA1UdJQEB/wQMMAoGCCsGAQUFBwMIMA4GA1UdDwEB/wQEAwIHgDAN
# BgkqhkiG9w0BAQsFAAOCAgEArShgbaNQUr5uFhSPidDUslYVNSxy+xd3242dnexe
# Sp/xQkwWV6c6w1ZetxS0TXCBaZycuP55YON6+0+bCT3aODLPAA0h0BCZx0rt8fVK
# Yws0RAT4vfpx4bw4Ecf9VpgQ+oEFGSSzoXDdk8VuCicoYpzLYgRbZDUWdr5mdTAH
# TV05uXdC8JN8M4/v3+1Qgk1glyUqKjWt1VP+rAAhyPexL2584PG3d4ca38+gnAlb
# n++3oL0R4p7YSbsEkXjz+2lZnHr29Z1lCACAnQXmx0Dq8zSHlgSEML3BWkt0hXPu
# Pa6q8EDjBQ0eBWAc0u29EHgVcRbiy9olbuCgBzDVISy0g+IiiwxQTUzrU805YRrz
# IBu+wNXI3kKwzB2uqEXjA3lA6h1K8b/IOyEXSIfodIAy5MzdMSLs5YtAb+ybcmxi
# W1eicWgxeAs0giDEaSufZyOoiqOC4J20AWSVu/umpGLChv6Vz5X8Tb9iJ6Q9dLUg
# pAr8PZK+ltfjUTfhLmXM0YAMFpXCvVyWd7rv7/6MR7Tu/5JlSLOdRfalemNkDV3e
# rVOOmD6yvfJtkA8rPpbyzYpitHtcWe2dRmsCqIShr5SwC1g5WUKoB3yd9QgdC5SA
# yO4i8mE6Xdosio6rJG0IsjLSAh/kZh/6AoOyTitGQN1yDG2vWkloARd0GeqRtxBn
# kKowggdxMIIFWaADAgECAhMzAAAAFcXna54Cm0mZAAAAAAAVMA0GCSqGSIb3DQEB
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
# BAsTHm5TaGllbGQgVFNTIEVTTjpGMDAyLTA1RTAtRDk0NzElMCMGA1UEAxMcTWlj
# cm9zb2Z0IFRpbWUtU3RhbXAgU2VydmljZaIjCgEBMAcGBSsOAwIaAxUAkxgPb6bC
# eoJagi5iNK4IBseGBBKggYMwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDANBgkqhkiG9w0BAQsFAAIFAO2c9PYwIhgPMjAyNjA0MjkyMTIxNThaGA8y
# MDI2MDQzMDIxMjE1OFowdDA6BgorBgEEAYRZCgQBMSwwKjAKAgUA7Zz09gIBADAH
# AgEAAgJPmTAHAgEAAgITpDAKAgUA7Z5GdgIBADA2BgorBgEEAYRZCgQCMSgwJjAM
# BgorBgEEAYRZCgMCoAowCAIBAAIDB6EgoQowCAIBAAIDAYagMA0GCSqGSIb3DQEB
# CwUAA4IBAQBXCosN4yc82pJwPhu7OfM3nF5R07oFq7leTTlSKzUJ25OlCTOzwhTX
# 7oQJi82sGebBCTsYDATl7H4LlyRfKd6Pmdrk0MBLWD9gs9dDXnQMFEnI3SWPUrMN
# T6sUM8A+eEwIIXI2qLAe3Bosz9oP8OhLrjhWSVYHjmbbFcvGnF3j1Zd+GojvwBLi
# R2l5m8l3RJDDCZq8+tAtohDLeXaNH047sVXA7VVkpLFeq/kSMnFydQqaOw0qnGZI
# VgOTTSoZgtLLCZoPrjem4WHlQvOu+je2tuFpkdUMvQgcR6QqHOxg6ZCDXWhV3Xjc
# tRIjMHIub331oaMk4jhux79FNcRovquiMYIEDTCCBAkCAQEwgZMwfDELMAkGA1UE
# BhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAc
# BgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMdTWljcm9zb2Z0
# IFRpbWUtU3RhbXAgUENBIDIwMTACEzMAAAIgJOHm4Be5tI4AAQAAAiAwDQYJYIZI
# AWUDBAIBBQCgggFKMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRABBDAvBgkqhkiG
# 9w0BCQQxIgQgFjq+i81g/IUIL3Bd+0Cl7B64dMvZrfdXbOQC4khxlfEwgfoGCyqG
# SIb3DQEJEAIvMYHqMIHnMIHkMIG9BCDje78jpTwNVapRKdECFRpTXfEuWFgZyo/e
# y7k1h0jtrzCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5n
# dG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9y
# YXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEwAhMz
# AAACICTh5uAXubSOAAEAAAIgMCIEIP2cze9rd63GC3s3nwWy955jBrFfrb8l67fJ
# 4PqIbm70MA0GCSqGSIb3DQEBCwUABIICALhyfFw3DJtYmVqYGUnJ+sk2W/q0+6NN
# uta3o14xKf6oy77qxZvyVgkp7ZOicvSusxK1nniGbsFa6Dssog07k+ULhyN21ey+
# nsJYb8ChAPnSZiHx8wsAjmpAbqr59nyNcXkN/ZI98hdyfsvep8VVghzgbPfNrWOR
# xGM+ILiCE5GGTlAFKxBJGnzf9eYKIUNMpFwzIePr8m9MyLevcp6A5Z0cpo9a5LnD
# u3gNbt2ndeu09wDu5DF21+K3BTM59+SaKsMAUsA0UbedSYkpYiHC1bwrm3lf3I1d
# AUbcrBV8qjvit6z6+aFT6iBwTSNjncZgxMPq+VrklarUCtduuHkC6e5uWt1v9IsR
# JsQjAqk3Px4D7VR+O8PZq1jgpJiZcxi2QcOmGbvDQ5+/Vo/L986Yd1iZjybt/5Tj
# ZHUQoTX54aiNPgaMhvxXbpcrOjzZKvsvsagR8cyNJ23T9nGcJcabEFMg5HKTDQA1
# +VxqfatiRMRCOuubrVJ22GkoMgJjDtmmO/bBiLn2GWXItP8ndkCHy2+Sz5/7imyP
# EUbhVmno4bJMoXqKkE1zCi/I8+CAH68RfA4i3CAcaTsdQVlNyf/qBfEVNRThPYMB
# jl4kZAFul3doKkU3fWfJkbJ7pgFOr/scBeeHnppHhXXy8YDc8YPffCfE5/BXL/pU
# 5ngCB1vYitVk
# SIG # End Windows Authenticode signature block