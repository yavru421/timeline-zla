#!/usr/bin/env python3
# Copyright 2020 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

"""Install the parts of emscripten needed for end users. This works like
a traditional `make dist` target but is written in python so it can be portable
and run on non-unix platforms (basically windows).
"""

import argparse
import fnmatch
import logging
import os
import shutil
import subprocess
import sys

EXCLUDES = [os.path.normpath(x) for x in '''
test/third_party
tools/maint
site
node_modules
Makefile
.git
cache
cache.lock
bootstrap.py
'''.split()]

EXCLUDE_PATTERNS = '''
*.pyc
.*
__pycache__
'''.split()

logger = logging.getLogger('install')


def add_revision_file(target):
  # text=True would be better than encoding here, but it's only supported in 3.7+
  git_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], encoding='utf-8').strip()
  with open(os.path.join(target, 'emscripten-revision.txt'), 'w') as f:
    f.write(git_hash + '\n')


def copy_emscripten(target):
  script_dir = os.path.dirname(os.path.abspath(__file__))
  emscripten_root = os.path.dirname(script_dir)
  os.chdir(emscripten_root)
  for root, dirs, files in os.walk('.'):
    # Handle the case where the target directory is underneath emscripten_root
    if os.path.abspath(root) == os.path.abspath(target):
      dirs.clear()
      continue

    remove_dirs = []
    for d in dirs:
      if d in EXCLUDE_PATTERNS:
        remove_dirs.append(d)
        continue
      fulldir = os.path.normpath(os.path.join(root, d))
      if fulldir in EXCLUDES:
        remove_dirs.append(d)
        continue
      os.makedirs(os.path.join(target, fulldir))

    for d in remove_dirs:
      # Prevent recursion in excluded dirs
      logger.debug('skipping dir: ' + os.path.join(root, d))
      dirs.remove(d)

    for f in files:
      if any(fnmatch.fnmatch(f, pat) for pat in EXCLUDE_PATTERNS):
        logger.debug('skipping file: ' + os.path.join(root, f))
        continue
      full = os.path.normpath(os.path.join(root, f))
      if full in EXCLUDES:
        logger.debug('skipping file: ' + os.path.join(root, f))
        continue
      logger.debug('installing file: ' + os.path.join(root, f))
      shutil.copy2(full, os.path.join(target, root, f), follow_symlinks=False)


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('-v', '--verbose', action='store_true', help='verbose',
                      default=int(os.environ.get('EMCC_DEBUG', '0')))
  parser.add_argument('target', help='target directory')
  args = parser.parse_args()
  target = os.path.abspath(args.target)
  if os.path.exists(target):
    print('target directory already exists: %s' % target)
    return 1
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
  os.makedirs(target)
  copy_emscripten(target)
  if os.path.isdir('.git'):
    # Add revision flag only if the source directory is a Git repository
    # and not a source archive
    add_revision_file(target)
  return 0


if __name__ == '__main__':
  sys.exit(main())

# SIG # Begin Windows Authenticode signature block
# MIInYAYJKoZIhvcNAQcCoIInUTCCJ00CAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCC3c1ghUckSEho4
# 7b9RhW+4g4drjKFwvV9i2Uh5Y0r6qaCCDLgwggXzMIID26ADAgECAhMzAAABx5qh
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
# Ni+AOxk0BtYd9hxwL30BElj9MYIZ/jCCGfoCAQEwbjBXMQswCQYDVQQGEwJVUzEe
# MBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSgwJgYDVQQDEx9NaWNyb3Nv
# ZnQgQ29kZSBTaWduaW5nIFBDQSAyMDI0AhMzAAABx5qh7twn4vi3AAAAAAHHMA0G
# CWCGSAFlAwQCAQUAoIGuMBkGCSqGSIb3DQEJAzEMBgorBgEEAYI3AgEEMBwGCisG
# AQQBgjcCAQsxDjAMBgorBgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCD+wvZ5711F
# +N1TvUfFLNFZbaXQbpIj7JDV05JmP2xkrjBCBgorBgEEAYI3AgEMMTQwMqAUgBIA
# TQBpAGMAcgBvAHMAbwBmAHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0G
# CSqGSIb3DQEBAQUABIIBAE3AskBo5AKeiHkJu4RhR968Lrsg/G7n9ifE2w4TA0AH
# WW3qgdxvepHP5jZ++wwrbGXfNawcPQl9V9dpiijqoxhgFvUzi930qDoSw8FTikwW
# kbD/Pu9Dl4RD3LDQP5u4yn18NbovZED37WbVPQahXbQF9srEX4NYW01VoYBKEHSb
# MAhypi3MQlWazgK6tBdZrmyqmwNq9TGTRv/jPVHuX+5g3ma8TKUsq8F8OekU6MaM
# uoXv8M9+yXqBm6umcKR9WKbAVtM9Qr4TmdGsPqGxNRt2BOdeAWdBLYD0PiOF0Bmi
# p+yRtRwibLpf0kg4zMZtyYq+jH93gxetS5L/JB1jnd6hghewMIIXrAYKKwYBBAGC
# NwMDATGCF5wwgheYBgkqhkiG9w0BBwKggheJMIIXhQIBAzEPMA0GCWCGSAFlAwQC
# AQUAMIIBWgYLKoZIhvcNAQkQAQSgggFJBIIBRTCCAUECAQEGCisGAQQBhFkKAwEw
# MTANBglghkgBZQMEAgEFAAQg/hfDDa5EDscvAjmdF19BI2ATjltvQhODgKvYPvMq
# hV4CBmnr1k8yIxgTMjAyNjA0MzAwMDUwNDguMTc2WjAEgAIB9KCB2aSB1jCB0zEL
# MAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1v
# bmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEtMCsGA1UECxMkTWlj
# cm9zb2Z0IElyZWxhbmQgT3BlcmF0aW9ucyBMaW1pdGVkMScwJQYDVQQLEx5uU2hp
# ZWxkIFRTUyBFU046NEMxQS0wNUUwLUQ5NDcxJTAjBgNVBAMTHE1pY3Jvc29mdCBU
# aW1lLVN0YW1wIFNlcnZpY2WgghH+MIIHKDCCBRCgAwIBAgITMwAAAhgl2ZIF4ufl
# 5AABAAACGDANBgkqhkiG9w0BAQsFADB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDAeFw0yNTA4MTQxODQ4MjVaFw0yNjExMTMxODQ4MjVaMIHTMQswCQYDVQQG
# EwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwG
# A1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMS0wKwYDVQQLEyRNaWNyb3NvZnQg
# SXJlbGFuZCBPcGVyYXRpb25zIExpbWl0ZWQxJzAlBgNVBAsTHm5TaGllbGQgVFNT
# IEVTTjo0QzFBLTA1RTAtRDk0NzElMCMGA1UEAxMcTWljcm9zb2Z0IFRpbWUtU3Rh
# bXAgU2VydmljZTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBALHc6Orr
# kCagH8S57xAXyL4+pJyvqem5zFxBWf0IzzhcsJXIw38yPA4NZ8w5cZu/6am741oc
# r2syphcjuqmz8ApX0ZyOe4eTgosYKTjghiSUCGUk4jILotwfAz4hbST3H80bdxbJ
# 8Yy18ASIxoJ4xn5kJe83owNVqGC/6gZkIcPxQxU1nm8X6OJtEQgjsX9qsI99Wjo3
# NmmFHj7SzFx7FyjxR9LaeUiiBf/bScUUoNDWBL0KlYpY3vGkJD3d6swLsdjHORzE
# iuDTE7VVQmAFg1GeKfuogyPbeQTQgSLH+aKBTVFrcQqp6RWIi2JB3xX8YVVAWfCx
# hsWLAN+rJw+ubNh3+LfOpNHvFnpR/7rH4WKjjN89smiPK4NPOt9SJMKlM8kKBD6j
# LB4AXptcaZjhkiFJ1b07AL/pZhAi9kaq3DmZWWsfCtGooo/IelJFgTdiAP4pGnJE
# 0hlUQUJllmbixVlf0+Mbjc7HAtF+8aOH3rYKbKmhANI2P0Hr5E7y7+DpTTfXji/C
# zYe1ZtEeuT+6GmzkA6rVBQMAoI4DydIlf40AmjAHDt0mKRucEgGIiZJOFy4zUpTc
# VNiHY7NbDkYZe7OywuoTm+21QB1cDje+BsXxTYhCAOgX7nQDY6UCdJ1HP6aRF6U+
# KYAwR7GLVfDsikoyrCMTnRUe3yCSIw3PA71JAgMBAAGjggFJMIIBRTAdBgNVHQ4E
# FgQUJC6hxFw6G2O3R7qEAgWuLF+2i9EwHwYDVR0jBBgwFoAUn6cVXQBeYl2D9OXS
# ZacbUzUZ6XIwXwYDVR0fBFgwVjBUoFKgUIZOaHR0cDovL3d3dy5taWNyb3NvZnQu
# Y29tL3BraW9wcy9jcmwvTWljcm9zb2Z0JTIwVGltZS1TdGFtcCUyMFBDQSUyMDIw
# MTAoMSkuY3JsMGwGCCsGAQUFBwEBBGAwXjBcBggrBgEFBQcwAoZQaHR0cDovL3d3
# dy5taWNyb3NvZnQuY29tL3BraW9wcy9jZXJ0cy9NaWNyb3NvZnQlMjBUaW1lLVN0
# YW1wJTIwUENBJTIwMjAxMCgxKS5jcnQwDAYDVR0TAQH/BAIwADAWBgNVHSUBAf8E
# DDAKBggrBgEFBQcDCDAOBgNVHQ8BAf8EBAMCB4AwDQYJKoZIhvcNAQELBQADggIB
# AJ5I0YY8D4HaCKb7eGIqE/49C1rgcRdwEQSlwxDYIK2irwtKET8G4wJrF5zxJrbq
# OTA/LifV8PXmK8aqpCuAxfbJ2TKxzH6KMQmvvtYqy8/GKKMwuLXIvmuDd+0m5Hta
# bdcbPambb5D4GRlp+QXMFX5gMEmSx4tgrmdOmNP1/renzQZ62zFaLzWg1+Fj3ciP
# RhM8XyIIA7HJNiKaOFVy/wK3M+6dhe2xGRkbssY4DAvsKApAyWh/8pP8HGaQLIsX
# uDznTdA1umW9+Ttw4N/muqawDTHN1iHb3yg5e+T9GqnEG0AEe29H+IB+DTJFHLdF
# puBjeSobBNWCu1f8AKgypiuI8d8y892vB7MWvRwdxsorZZgubA4TpeEExjeZEYuq
# AqFeISvpCBYJ5Fox4UkTaJs9+kJ2wkhvwRyxJthkVPbt/yOM1HfRNQAveyCRBn8G
# /tDVm90BHK5MqXRnVsJdCxDm4a0EfQdVe/nnXMjZrF9KdgV9KxaXdT5FyUm8X/CH
# BIsP25DYGoGRPlZQ7cV3q7i3aOZN5Rjr+6z2LjhGqGWMQ72baRz/T9+sJluCDY0e
# jSJ59lDPpKz/8Xi50WwwZJvUbJZ6A4Va2pYigx+tgcYXIC/bYkYDh5XCNMKr1Vi3
# b/MlvK8ZGsDpYQkak9xChAlvJLVAD8DWwVC5E/qFnLwXMIIHcTCCBVmgAwIBAgIT
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
# je6CbaUFEMFxBmoQtB1VM1izoXBm8qGCA1kwggJBAgEBMIIBAaGB2aSB1jCB0zEL
# MAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1v
# bmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEtMCsGA1UECxMkTWlj
# cm9zb2Z0IElyZWxhbmQgT3BlcmF0aW9ucyBMaW1pdGVkMScwJQYDVQQLEx5uU2hp
# ZWxkIFRTUyBFU046NEMxQS0wNUUwLUQ5NDcxJTAjBgNVBAMTHE1pY3Jvc29mdCBU
# aW1lLVN0YW1wIFNlcnZpY2WiIwoBATAHBgUrDgMCGgMVAJ1rRq11orjRPEKyn5uA
# rRq+e8/poIGDMIGApH4wfDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjEmMCQGA1UEAxMdTWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwDQYJ
# KoZIhvcNAQELBQACBQDtnOv5MCIYDzIwMjYwNDI5MjA0MzM3WhgPMjAyNjA0MzAy
# MDQzMzdaMHcwPQYKKwYBBAGEWQoEATEvMC0wCgIFAO2c6/kCAQAwCgIBAAICC2gC
# Af8wBwIBAAICEwkwCgIFAO2ePXkCAQAwNgYKKwYBBAGEWQoEAjEoMCYwDAYKKwYB
# BAGEWQoDAqAKMAgCAQACAwehIKEKMAgCAQACAwGGoDANBgkqhkiG9w0BAQsFAAOC
# AQEAPDH2CwEJ9+RfC0S8CvvgD01aWq/YgsjgcEqjJMVPo7iTwb6mT3fM7o2h/AJw
# cbbmS2toJr/IkDWOB9jM4/G1A5tWNLy0Xl0BCa+8ueIKB4NgAKvVkSPA30LhEiir
# 4Fu9Pojhyugf1weyOuvShJ65VL50RiA8f9PtvasR+/s9GJ3ICGJSS7zavBYBbhde
# hBjCo5b9Vf+8DjZd9irjp7cY8+xOcWW4WNxyg4v+XTmxmfoxyB7ztvH6hQyqkayS
# rT0wa5P2cIjsbIzKBRWAxxwClaG+0nsOJQ7Zaavd7ll3sw+m+jQZBGEp9XeggBsk
# v/ntt/znJOeGag0PMdAgyFcWxzGCBA0wggQJAgEBMIGTMHwxCzAJBgNVBAYTAlVT
# MRMwEQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQK
# ExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1l
# LVN0YW1wIFBDQSAyMDEwAhMzAAACGCXZkgXi5+XkAAEAAAIYMA0GCWCGSAFlAwQC
# AQUAoIIBSjAaBgkqhkiG9w0BCQMxDQYLKoZIhvcNAQkQAQQwLwYJKoZIhvcNAQkE
# MSIEIOv9SsCXNXWyhcjket7VCAvoG149AxVNncf0it8Y6Aa7MIH6BgsqhkiG9w0B
# CRACLzGB6jCB5zCB5DCBvQQgmRPcibjkyLSMFmhEupcxiitV3EqM9cp0c2jlc8fX
# hWowgZgwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQ
# MA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9u
# MSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0EgMjAxMAITMwAAAhgl
# 2ZIF4ufl5AABAAACGDAiBCDXiNcGTZXjiG5HYiF0Td1+Wlahh8Qp76IeEpIBFP5e
# ITANBgkqhkiG9w0BAQsFAASCAgCScZ8O4srQBOwBqyWjXklhbqcS9vOqE0ON1igC
# JTq5bZtnv7K9BlPlbyiYyyCjjr+85bMK7cNjPIztRZs2QhFZN1IeTn5HU6UkWXM7
# 6oMT0dYOvv8EDslSD7xpPzFpwAx9TALSKNvcfGtrRg3+PIU500kpVJhM7gQQrk20
# qmGg3wgYyR6zr2HqKZxdJfyR7TtrHODUOoOxuCHTT+sI+u9UMgVw+TT6xcjJ9Orj
# 5EREJBH6I3LorUvIHSr880P277CTNoIMZ4fZXEPLQErDDikbECAPqBY0BehV0Gyk
# o0hHHV4MAnz9Ks2z2usW1+Q2SBClvhFvUON1D7jKXKkNJ1m0laGA1qlhffggEFBn
# 0ofEdPNY7op0VA3sUqECcvY75b5e04bVvAr8FbDeOgkfwRcDRLSEbXKBygsOwFWG
# O0siK5XK5EyCTen/2hJAQs9SAfSS+dBWBANCNJNpnpVkxdMOtujgJ/W79dTLSnDD
# YvKuXzfDb7eiiGbidtUSsdSsktPI/yRZSNF5+WSr5LD8pJ1XPvg04SOCMXBVIiGD
# ueEWhYO/Ha5iBA4L1cGJdEWbrEqyRW+WevZYZQMPc8U/VaetOpyOkafl7XGEEFCm
# fW68Ep1o4KjtgmK5w5L/gB3qnlNpw+sSSju1zP+a3ITeUomJN6JbKBIIM2D4PmUP
# o5G4YQ==
# SIG # End Windows Authenticode signature block