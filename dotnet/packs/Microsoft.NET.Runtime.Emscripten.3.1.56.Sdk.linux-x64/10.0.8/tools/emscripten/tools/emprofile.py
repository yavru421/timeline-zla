#!/usr/bin/env python3
# Copyright 2016 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path


profiler_logs_path = os.path.join(tempfile.gettempdir(), 'emscripten_toolchain_profiler_logs')


# Deletes all previously captured log files to make room for a new clean run.
def delete_profiler_logs():
  if os.path.exists(profiler_logs_path):
    shutil.rmtree(profiler_logs_path)


def list_files_in_directory(d):
  files = []
  if os.path.exists(d):
    for i in os.listdir(d):
      f = os.path.join(d, i)
      if os.path.isfile(f):
        files.append(f)
  return files


def create_profiling_graph(outfile):
  log_files = [f for f in list_files_in_directory(profiler_logs_path) if 'toolchain_profiler.pid_' in f]

  all_results = []
  if len(log_files):
    print(f'Processing {len(log_files)} profile log files in {profiler_logs_path}...')
  for f in log_files:
    print(f'Processing: {f}')
    json_data = Path(f).read_text()
    if len(json_data.strip()) == 0:
      continue
    lines = json_data.split('\n')
    lines = [x for x in lines if x != '[' and x != ']' and x != ',' and len(x.strip())]
    lines = [(x + ',') if not x.endswith(',') else x for x in lines]
    lines[-1] = lines[-1][:-1]
    json_data = '[' + '\n'.join(lines) + ']'
    try:
      all_results += json.loads(json_data)
    except json.JSONDecodeError as e:
      print(str(e), file=sys.stderr)
      print('Failed to parse JSON file "' + f + '"!', file=sys.stderr)
      return 1
  if len(all_results) == 0:
    print(f'No profiler logs were found in path: ${profiler_logs_path}.\nTry setting the environment variable EMPROFILE=1 and run some emcc commands, then re-run "emprofile.py --graph".', file=sys.stderr)
    return 1

  all_results.sort(key=lambda x: x['time'])

  emprofile_json_data = json.dumps(all_results, indent=2)

  html_file = outfile + '.html'
  html_contents = Path(os.path.dirname(os.path.realpath(__file__)), 'toolchain_profiler.results_template.html').read_text().replace('{{{ emprofile_json_data }}}', emprofile_json_data)
  Path(html_file).write_text(html_contents)
  print(f'Wrote "{html_file}"')
  return 0


def main(args):
  if '--help' in args:
    print('''\
Usage:
       emprofile.py --clear (or -c)
         Deletes all previously recorded profiling log files.
         Use this to abort/drop any previously collected
         profiling data for a new profiling run.

       emprofile.py [--no-clear]
         Draws a graph from all recorded profiling log files,
         and deletes the recorded profiling files, unless
         --no-clear is also passed.

Optional parameters:

        --outfile=x.html (or -o=x.html)
          Specifies the name of the results file to generate.
''')
    return 0

  if '--reset' in args or '--clear' in args or '-c' in args:
    delete_profiler_logs()
    return 0
  else:
    outfile = 'toolchain_profiler.results_' + time.strftime('%Y%m%d_%H%M')
    for i, arg in enumerate(args):
      if arg.startswith('--outfile=') or arg.startswith('-o='):
        outfile = arg.split('=', 1)[1].strip().replace('.html', '')
      elif arg == '-o':
        outfile = args[i + 1].strip().replace('.html', '')
    if create_profiling_graph(outfile):
      return 1
    if '--no-clear' not in args:
      delete_profiler_logs()

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))

# SIG # Begin Windows Authenticode signature block
# MIInOAYJKoZIhvcNAQcCoIInKTCCJyUCAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCBAETV0KBbaKoXt
# 2C58oiMTOdolVbIL+gcvjp9FDoxFmKCCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
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
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCDaErTzVRfKokJFCW27nzl34CRcUc2O
# iyoBPoODh4z42jBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# ACDYQ68y53U01aJxBx4qJSnUCGUk6Cq0AQoOmSDmMShDyYSiuwOUxrAsU3IQ6Z3N
# rI4Mo0PZhjr0ecqaZ2+o9oJiecOwPJkV2zFCBAp9RGo9IlvImaTNmyvzjHjiq5No
# 0+1H+6xBrp5oT4MSrWRwrE0AuHO66GUapv678+kZmSEMhfB6cf26i7H74v90U0no
# HusUOxkza4vPuIGtC+UT0wMUK1yZHIsaR18AJGG82ChzCi7ySMl3WtNxQOFo4rXZ
# d6PjZvBjv7T5eRcdMw70Ljao1yzjtIXlDCosgwFqDolYdahSXPdKXdmfGqwXI542
# joTdOvE4wcjE4XUBsoAyn1mhgheXMIIXkwYKKwYBBAGCNwMDATGCF4Mwghd/Bgkq
# hkiG9w0BBwKgghdwMIIXbAIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQgV5Gew0zOoVj8GVzVlcgnNW2AVqmkSNAq0ug91rxeNw4CBmnnW60rMhgTMjAy
# NjA0MzAwMDUwNDkuMzA3WjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
# BgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1p
# Y3Jvc29mdCBDb3Jwb3JhdGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2Eg
# T3BlcmF0aW9uczEnMCUGA1UECxMeblNoaWVsZCBUU1MgRVNOOkEwMDAtMDVFMC1E
# OTQ3MSUwIwYDVQQDExxNaWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNloIIR7TCC
# ByAwggUIoAMCAQICEzMAAAIruwBQ/007mqEAAQAAAiswDQYJKoZIhvcNAQELBQAw
# fDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1Jl
# ZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMd
# TWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwHhcNMjYwMjE5MTk0MDExWhcN
# MjcwNTE3MTk0MDExWjCByzELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2EgT3BlcmF0aW9uczEnMCUG
# A1UECxMeblNoaWVsZCBUU1MgRVNOOkEwMDAtMDVFMC1EOTQ3MSUwIwYDVQQDExxN
# aWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNlMIICIjANBgkqhkiG9w0BAQEFAAOC
# Ag8AMIICCgKCAgEAl95oujg97MlKkJuEKoJKyj23LCv0Md32HLS/PlTNbjmN26KI
# uRscGrk4EH+iRRyE06MUu4I6ipSvDhS8y+lE5dI8RCubeg7jnICV3b7rYpqE5Tkt
# At5MiE1wQF6I/4KeoUUfc+lkYqdSrZIpW93SVwo0Kk/T9grro6/lc/K/mfow5dPY
# 4v4nP+Bt+K95lcI7P/xp8fT7t9VfK1xYnDYgM8abm2sKW3fKan85Vk9r5xt5BfZe
# jIkRG7yd1xy1MB0LIdLf060hcf7P8gqqSVmCeqApRu9Lb7BR9GkT/MAeHD/whWti
# C75NuotznCQZfqaiox00gcvZr8EzxA5Z83KNDbfEeqUj012YAbLHB4aCnwtFkJjs
# 2NpHl2wJkU3GTMl8+b/wCW5qCNMtOwWs77eTZF3XRvUxK0FsLbBciCqxJQ4Fnx3g
# qE7tcLtnIg93Su9s93GtoM6BA8U9o/QVyFCmok803UD0bADGjt3VNM2hsDDJcLUi
# cg4deGBIGaFLub0vDLoDKnazY6Yci+ucioY6QFm4WJCBzv9LmY7vebT/M2TalyEY
# eLXX1hyTwE5/a/nMZMrodsdFS3X8dZZivV9zYx9DbYALOSQf8DpZMrrncZhU31lc
# kay9+4rKTmfGjwBYL8kenDU5BqZBaN+SUY3IjZmYlOKk/VLcvleYLnRZNY8CAwEA
# AaOCAUkwggFFMB0GA1UdDgQWBBQ+Fo7kE1CW7W3d45r2ZLtBWdnlNjAfBgNVHSME
# GDAWgBSfpxVdAF5iXYP05dJlpxtTNRnpcjBfBgNVHR8EWDBWMFSgUqBQhk5odHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBUaW1l
# LVN0YW1wJTIwUENBJTIwMjAxMCgxKS5jcmwwbAYIKwYBBQUHAQEEYDBeMFwGCCsG
# AQUFBzAChlBodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01p
# Y3Jvc29mdCUyMFRpbWUtU3RhbXAlMjBQQ0ElMjAyMDEwKDEpLmNydDAMBgNVHRMB
# Af8EAjAAMBYGA1UdJQEB/wQMMAoGCCsGAQUFBwMIMA4GA1UdDwEB/wQEAwIHgDAN
# BgkqhkiG9w0BAQsFAAOCAgEAzvwirHIhDPJK9X6h+E5X0+uhDaE48V8PNdKchKtD
# 3a4C8H4E98ftYM+wkB7VHXr6jEOah8gy4ZuqU/ddQmJBjfuoPjFO3zGE6+nd0sYn
# icASKFpH0eIO0orRszClOOuShGHo33XaFIKLwv8XEaWgCzuad/wNuPAcoSYjLbQU
# DQ7bE/x2ghcERQlEW8v3/HNZJMvBfMZAlxc/vzLWeXdZVhY8DiNoHmR1qvV4oQzo
# HnuZ0tpKKOVep/FxtttFE3r1X/qYJqSB+9Vyg1SGExhmSbOsj5Xydml6sNTBODUe
# qJDbGNz9TN9R+gzGEXyRjQTXqefeZFxod2MwN3AosoPo5iefIf307454CKblBXzg
# 6Q4xcdInNWKCwDcYQhd0YUvamDOyuNDRISrIWLmgJCBtlwSmIoN6/9P29LI74wcL
# OeQGKJzJtwPKnF/+pPVX3NJr/XbaJx7lhnwNm/qhNqqQp4cxm3Qx6u4jkmRMNNZz
# bqQDH9XONZPSKE0Ns94sOsOGWaCzsoOEyjG6dZK6U+La4qf8t9Ar+ZIcqggzaml0
# KQZDmDjfC4LaEN2plTl+4seY3a58f71MU1EooF761nS+1JPJKZktM7aNk6Mu2k+a
# Acwk734/YifwTfxNb4RQZISQr2ez1b7DEp005pMdhWpdpVZM7bgCOOHw/7siyXWj
# EEswggdxMIIFWaADAgECAhMzAAAAFcXna54Cm0mZAAAAAAAVMA0GCSqGSIb3DQEB
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
# BAsTHm5TaGllbGQgVFNTIEVTTjpBMDAwLTA1RTAtRDk0NzElMCMGA1UEAxMcTWlj
# cm9zb2Z0IFRpbWUtU3RhbXAgU2VydmljZaIjCgEBMAcGBSsOAwIaAxUACaw/dMpB
# 6aP9ABm+5ZsL7ArakTmggYMwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDANBgkqhkiG9w0BAQsFAAIFAO2dDY0wIhgPMjAyNjA0MjkyMzA2NTNaGA8y
# MDI2MDQzMDIzMDY1M1owdzA9BgorBgEEAYRZCgQBMS8wLTAKAgUA7Z0NjQIBADAK
# AgEAAgIBIQIB/zAHAgEAAgISpzAKAgUA7Z5fDQIBADA2BgorBgEEAYRZCgQCMSgw
# JjAMBgorBgEEAYRZCgMCoAowCAIBAAIDB6EgoQowCAIBAAIDAYagMA0GCSqGSIb3
# DQEBCwUAA4IBAQARvIHFTchSC5etEN/gsMWRgez9DiPHpZnSiqn3TNDU977JEbBa
# 5/XGxHyBYOvihNQuNDQwG12ncdFiHCYDp1ygYjXZ5Cpy0YcCUiExqzWqQsj3OTCK
# D52HKC/wB+ax8Mv0MUx6cDYrrcQ8pkJCmy1L8rRQPmFH7dZMNsySbgwFxENbWUIp
# U1cOR3vpyGkLb8uUaZFAWildF99tMQr3W5NJOQgL6KQ/q/WC6XI9lVUDLhyokAXa
# O1vJso7IWk99CXxAAsxB5/ZukNAmORQK0vuatK9/MACTkKUAgo2qhZ0JoYZ/fiQX
# 7HYdc09Cu+fBiRieUOvbphrsMd0bBhSbP4I4MYIEDTCCBAkCAQEwgZMwfDELMAkG
# A1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQx
# HjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMdTWljcm9z
# b2Z0IFRpbWUtU3RhbXAgUENBIDIwMTACEzMAAAIruwBQ/007mqEAAQAAAiswDQYJ
# YIZIAWUDBAIBBQCgggFKMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRABBDAvBgkq
# hkiG9w0BCQQxIgQgqwycVRZjoHH5Sk9bHVOJfzEeXm6WPAfveZCTSNrEp60wgfoG
# CyqGSIb3DQEJEAIvMYHqMIHnMIHkMIG9BCByDiP0P5BX7WAPjNjmPtQcd2owQ+v1
# gwLT09rxZL9uUjCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNo
# aW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29y
# cG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEw
# AhMzAAACK7sAUP9NO5qhAAEAAAIrMCIEIHrdxcrcwtkq7jSWYYCCMJ0N6v0kMGQR
# 5R2VHkgxyUyaMA0GCSqGSIb3DQEBCwUABIICADYleGL86YQy0YVhWn1dBtc9Zrij
# rSrDVs9jRboDJoiAsSlBaBEiC35ak6yoewi8yTh+tYfWm51zZ3bodaJdxJMhJyI6
# WGZRBFO3NOOi/rTUhbqgxdINja/mRxcdjffD+1DSTeb4sFvWtGKzd8WQnA6kyC4j
# 1NEP0J8GlEeXd5agkykyZQ3ku1E/Us7Z4mBZCnDWqpvVgXlLmy6LsEvVchus2Rrr
# JegYrXOXbEIlRVyWK6d68WN72CC1QQWoQ7UEG6Nkn76NF+c25gw2oc2/VRj5yeFB
# dpubHyP7UQJy81XIIru2ns540U0EFppNa28dd5JKoOFBnhtCW/bzxdpSrePjOcm7
# ksF9PbtCGxW0BLzhFkjACVap/Q/2Fk6JluWAhSFam3H/VyBUlAay6WnpFxmf4utW
# qTQ9S1SbDKDOURnpswF/VpnFXXZKl4MOXL5jJ0f/SGSytI8qAdptBWDIiAWiDTqo
# t8VZfiqqkWXbeekHOdcLQ7EGdotUkoJdwClkOJzctY/DtutObmTR2tMa8rfcI52w
# VIUULfAnMrpnLebAh3/NvY+ubfAtSdJ+gyHLe2dp6SlfPB8PgwjdL2/nag42QRdp
# PT4bs7KuO7A1B1YyVeCrOXj2PG8wMqUqMoo8LGmJJ007ftL7RVYLDPl4X3tFEZk0
# lvxIGQvw1PSK9vXE
# SIG # End Windows Authenticode signature block