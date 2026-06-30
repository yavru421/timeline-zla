# Copyright 2011 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

"""Simple color-enabled diagnositics reporting functions.
"""

import ctypes
import logging
import os
import sys
from typing import Dict


WINDOWS = sys.platform.startswith('win')

logger = logging.getLogger('diagnostics')
color_enabled = sys.stderr.isatty()
tool_name = os.path.splitext(os.path.basename(sys.argv[0]))[0]

# diagnostic levels
WARN = 1
ERROR = 2
FATAL = 3

# available colors
RED = 1
GREEN = 2
YELLOW = 3
BLUE = 4
MAGENTA = 5
CYAN = 6
WHITE = 7

# color for use for each diagnostic level
level_colors = {
    WARN: MAGENTA,
    ERROR: RED,
}

level_prefixes = {
    WARN: 'warning: ',
    ERROR: 'error: ',
}

# Constants from the Windows API
STD_OUTPUT_HANDLE = -11


def output_color_windows(color):
  # TODO(sbc): This code is duplicated in colored_logger.py.  Refactor.
  # wincon.h
  FOREGROUND_BLACK     = 0x0000 # noqa
  FOREGROUND_BLUE      = 0x0001 # noqa
  FOREGROUND_GREEN     = 0x0002 # noqa
  FOREGROUND_CYAN      = 0x0003 # noqa
  FOREGROUND_RED       = 0x0004 # noqa
  FOREGROUND_MAGENTA   = 0x0005 # noqa
  FOREGROUND_YELLOW    = 0x0006 # noqa
  FOREGROUND_GREY      = 0x0007 # noqa

  color_map = {
    RED: FOREGROUND_RED,
    GREEN: FOREGROUND_GREEN,
    YELLOW: FOREGROUND_YELLOW,
    BLUE: FOREGROUND_BLUE,
    MAGENTA: FOREGROUND_MAGENTA,
    CYAN: FOREGROUND_CYAN,
    WHITE: FOREGROUND_BLUE | FOREGROUND_GREEN | FOREGROUND_RED
  }

  sys.stderr.flush()
  hdl = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
  ctypes.windll.kernel32.SetConsoleTextAttribute(hdl, color_map[color])


def get_color_windows():
  SHORT = ctypes.c_short
  WORD = ctypes.c_ushort

  class COORD(ctypes.Structure):
    _fields_ = [
      ("X", SHORT),
      ("Y", SHORT)]

  class SMALL_RECT(ctypes.Structure):
    _fields_ = [
      ("Left", SHORT),
      ("Top", SHORT),
      ("Right", SHORT),
      ("Bottom", SHORT)]

  class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [
      ("dwSize", COORD),
      ("dwCursorPosition", COORD),
      ("wAttributes", WORD),
      ("srWindow", SMALL_RECT),
      ("dwMaximumWindowSize", COORD)]

  hdl = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
  csbi = CONSOLE_SCREEN_BUFFER_INFO()
  ctypes.windll.kernel32.GetConsoleScreenBufferInfo(hdl, ctypes.byref(csbi))
  return csbi.wAttributes


def reset_color_windows():
  sys.stderr.flush()
  hdl = ctypes.windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
  ctypes.windll.kernel32.SetConsoleTextAttribute(hdl, default_color)


def output_color(color):
  if WINDOWS:
    return output_color_windows(color)
  return '\033[3%sm' % color


def reset_color():
  if WINDOWS:
    return reset_color_windows()
  return '\033[0m'


def diag(level, msg, *args):
  # Format output message as:
  # <tool>: <level>: msg
  # With the `<level>:` part being colored accordingly.
  sys.stderr.write(tool_name + ': ')

  if color_enabled:
    output = output_color(level_colors[level])
    if output:
      sys.stderr.write(output)

  sys.stderr.write(level_prefixes[level])

  if color_enabled:
    output = reset_color()
    if output:
      sys.stderr.write(output)

  if args:
    msg = msg % args
  sys.stderr.write(str(msg))
  sys.stderr.write('\n')


def error(msg, *args):
  diag(ERROR, msg, *args)
  sys.exit(1)


def warn(msg, *args):
  diag(WARN, msg, *args)


class WarningManager:
  warnings: Dict[str, Dict] = {}

  def add_warning(self, name, enabled=True, part_of_all=True, shared=False, error=False):
    self.warnings[name] = {
      'enabled': enabled,
      'part_of_all': part_of_all,
      # True for flags that are shared with the underlying clang driver
      'shared': shared,
      'error': error,
    }

  def capture_warnings(self, cmd_args):
    for i in range(len(cmd_args)):
      if cmd_args[i] == '-w':
        for warning in self.warnings.values():
          warning['enabled'] = False
        continue

      if not cmd_args[i].startswith('-W'):
        continue

      if cmd_args[i] == '-Wall':
        for warning in self.warnings.values():
          if warning['part_of_all']:
            warning['enabled'] = True
        continue

      if cmd_args[i] == '-Werror':
        for warning in self.warnings.values():
          warning['error'] = True
        continue

      if cmd_args[i].startswith('-Werror=') or cmd_args[i].startswith('-Wno-error='):
        warning_name = cmd_args[i].split('=', 1)[1]
        if warning_name in self.warnings:
          enabled = not cmd_args[i].startswith('-Wno-')
          self.warnings[warning_name]['error'] = enabled
          if enabled:
            self.warnings[warning_name]['enabled'] = True
          cmd_args[i] = ''
          continue

      warning_name = cmd_args[i].replace('-Wno-', '').replace('-W', '')
      enabled = not cmd_args[i].startswith('-Wno-')

      # special case pre-existing warn-absolute-paths
      if warning_name == 'warn-absolute-paths':
        self.warnings['absolute-paths']['enabled'] = enabled
        cmd_args[i] = ''
        continue

      if warning_name in self.warnings:
        self.warnings[warning_name]['enabled'] = enabled
        if not self.warnings[warning_name]['shared']:
          cmd_args[i] = ''
        continue

    return cmd_args

  def warning(self, warning_type, message, *args):
    warning_info = self.warnings[warning_type]
    msg = (message % args) + ' [-W' + warning_type.lower().replace('_', '-') + ']'
    if warning_info['enabled']:
      if warning_info['error']:
        error(msg + ' [-Werror]')
      else:
        warn(msg)
    else:
      logger.debug('disabled warning: ' + msg)


def add_warning(name, enabled=True, part_of_all=True, shared=False, error=False):
  manager.add_warning(name, enabled, part_of_all, shared, error)


def enable_warning(name, as_error=False):
  manager.warnings[name]['enabled'] = True
  if as_error:
    manager.warnings[name]['error'] = True


def disable_warning(name):
  manager.warnings[name]['enabled'] = False


def is_enabled(name):
  return manager.warnings[name]['enabled']


def warning(warning_type, message, *args):
  manager.warning(warning_type, message, *args)


def capture_warnings(argv):
  return manager.capture_warnings(argv)


if WINDOWS:
  default_color = get_color_windows()

manager = WarningManager()

# SIG # Begin Windows Authenticode signature block
# MIInNQYJKoZIhvcNAQcCoIInJjCCJyICAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCAlosETWf/O82fG
# lIiJEOrzcsLam8WFXzy/bYe6wdKAVaCCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
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
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCDJvh76yurY+A40ZsAwl5l8JhGL1+Z7
# urntx0XSsHVGTzBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# AMGFgOdX6Cv9JZAhcT+NbH9mriezC3zC/RZ1jHTorpOCqCl4bta5qejNjA6X6Mi6
# GG4ot4Wf4V0RZ1ai84kl3YbPanBcMWZ1o999R6fgGbOk+qRSquXEenkJBorvm5qi
# wy7iOipABWHgGrrtUuQM5GALH3pFPAi9CAdl5ozgpOZQe6wQe5OvyrsDz+bJYl9G
# PP1lg1qjYC14DO/FdLNMaxHlk8E6UJb5lkgFEw/+a5o17bb1yB4D3ArD6bdugPN4
# dDuMcHVCzZG0lMQlXXPVN9TYiZ2JIxrZtqNknwYLXnlLYVxWEov0ez2GLL6mMDzq
# fXe0Qk75aNP1ic8fXT5ggrOhgheUMIIXkAYKKwYBBAGCNwMDATGCF4Awghd8Bgkq
# hkiG9w0BBwKgghdtMIIXaQIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQgvDc1qo2bUWRzXofKDh0HOvS2S99VgtJWGHVL3n9S3KUCBmnnbvCT3xgTMjAy
# NjA0MzAwMDUwNDguMjAxWjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
# BgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1p
# Y3Jvc29mdCBDb3Jwb3JhdGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2Eg
# T3BlcmF0aW9uczEnMCUGA1UECxMeblNoaWVsZCBUU1MgRVNOOkE5MzUtMDNFMC1E
# OTQ3MSUwIwYDVQQDExxNaWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNloIIR6jCC
# ByAwggUIoAMCAQICEzMAAAIn1cCDw7EuVy0AAQAAAicwDQYJKoZIhvcNAQELBQAw
# fDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1Jl
# ZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMd
# TWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwHhcNMjYwMjE5MTk0MDA0WhcN
# MjcwNTE3MTk0MDA0WjCByzELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2EgT3BlcmF0aW9uczEnMCUG
# A1UECxMeblNoaWVsZCBUU1MgRVNOOkE5MzUtMDNFMC1EOTQ3MSUwIwYDVQQDExxN
# aWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNlMIICIjANBgkqhkiG9w0BAQEFAAOC
# Ag8AMIICCgKCAgEA4sVstXwzki+Ko9wNaWncvnpSAy8Jxd1Li8ySDlsBh3BIK8cc
# LZ8r4lCA5pscpU1JdbvtqwT6ds0+AcMEIbxmiaRMarzy5QxZW35kn5SiPOnhaqH4
# me4/DU0TuJe8BoPTY5vprjWrk3BVtqnXyIyhPedDpK5vTJzDhmMvn4mzWHcUz0T6
# tU+DC2St7N73TMjBDpXXDkJEiqcQ+v9RpOoDpgrtioCPH9Hser2MZyg5fVtDi0hG
# v+svNqCG7JvtUAYnzkOO8VikxtQpr7Rq/OS8wO+fzAHFJkcOf6H/6hE9FBVdVrpT
# HCayOgwEgLDQjQfuli66LbgWQI/lTJam5+UTGekOCGOycGgIiF4e1Y8a58FDmGRv
# FhBoX6wPfHYvuyxJ/QKr7xDshvlEHI1YQgmzBl4oCV0gKXsnlrqQrA9I4EDDQsXw
# eQSwQ1sYHWN3SQRD4MX5IEw0CwYILVb9neQmMRyoCCLQeGyOXkm+Y5CBtlqLZxXr
# U9JXoKcPxKM8H9/WqOrRDWNtXlViM0cPxrJr8I2EBer1a8Tg9KRlbH6hhfLN1T3m
# O4SNk8RxTKjQNCAf2tjS2OyU8WACgD/9dRCWbe8W6gyzIA9WA3RhMxqUIo5t5wDw
# i9gnmz/45rvdGmydluNucoJRh0yP5wga8EqX0QoMM63xXpSWgijOvt+WhX8CAwEA
# AaOCAUkwggFFMB0GA1UdDgQWBBTS1ufDeDBkhurne41qoE/dqK30XjAfBgNVHSME
# GDAWgBSfpxVdAF5iXYP05dJlpxtTNRnpcjBfBgNVHR8EWDBWMFSgUqBQhk5odHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBUaW1l
# LVN0YW1wJTIwUENBJTIwMjAxMCgxKS5jcmwwbAYIKwYBBQUHAQEEYDBeMFwGCCsG
# AQUFBzAChlBodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01p
# Y3Jvc29mdCUyMFRpbWUtU3RhbXAlMjBQQ0ElMjAyMDEwKDEpLmNydDAMBgNVHRMB
# Af8EAjAAMBYGA1UdJQEB/wQMMAoGCCsGAQUFBwMIMA4GA1UdDwEB/wQEAwIHgDAN
# BgkqhkiG9w0BAQsFAAOCAgEAKp3LneD0gtbXm9h+p0bsu7A4iitdxVyYq1QeE38I
# 3aNjG/kC+I+8Gf5OBvT9AgDR2Raw0HCtFRQ08rK2LvGdAIWteGnA2T7MiKD7wBkU
# YWhxLn+zXJEY5H2v8paNSsiCPI2y/TfbCQKgTy/FeBTQY5Y7/tRhwzsNdu62c+WU
# kz6AD29kgNL+cg4HKVDH8YJT8qenJzz6EKU7Q/ThsfA8Jtj/qNUz8QSMuiNE/UWr
# rpaIFQrysH5X3i03CgL50htawo3q0l5lNQzVzrAA/27K0o4G1+ZgGw+100TBf72s
# AFhEhXJ/wY44s8XlmW9NGmEpZCQNq1bRZTDOPNWlVl3QG1zz+Uc1Ilk5YMh3/xu5
# QsR2FhiGbgdd092iOmPJhIJ/6LuNGohSaPK9PotD+RnTZ3lrcYkdAjClH5KPubP+
# 93MHtVn6fASl2tu9HInFUGrBX+bEVe6RZvle3zUV8Aru2p0zpoGu+szu/9rfszpY
# m76YU/kOmXfgdqmLEp+MQWmPmMx6Z8nC1uXLycoT8QQnG9aEWH4UcwgA29rrSNhL
# Rgo3Nj9oouC8keEDG/5/HDsHi/SKlUyis81ZPs2ScVd766eC8rkF8NDt9JWugXB3
# TQAAAfVAvN87NxvXfgJSH2SzPe7TFDSlo2waSIqxcei0wxV1bWUHe4asy2Aco24x
# 9LowggdxMIIFWaADAgECAhMzAAAAFcXna54Cm0mZAAAAAAAVMA0GCSqGSIb3DQEB
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
# BAsTHm5TaGllbGQgVFNTIEVTTjpBOTM1LTAzRTAtRDk0NzElMCMGA1UEAxMcTWlj
# cm9zb2Z0IFRpbWUtU3RhbXAgU2VydmljZaIjCgEBMAcGBSsOAwIaAxUAIx86rYT8
# DtBg3JAzAOseeJSIjCqggYMwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDANBgkqhkiG9w0BAQsFAAIFAO2dINEwIhgPMjAyNjA0MzAwMDI5MDVaGA8y
# MDI2MDUwMTAwMjkwNVowdDA6BgorBgEEAYRZCgQBMSwwKjAKAgUA7Z0g0QIBADAH
# AgEAAgIhejAHAgEAAgISYzAKAgUA7Z5yUQIBADA2BgorBgEEAYRZCgQCMSgwJjAM
# BgorBgEEAYRZCgMCoAowCAIBAAIDB6EgoQowCAIBAAIDAYagMA0GCSqGSIb3DQEB
# CwUAA4IBAQCQQZadjjFtkSjkN/qnD/M8rEj1XVaErGi5ZKm37PY6BDDE1wGUpLfM
# AtBfAdpJk6DPofIVcSVwsktZ1RBs+RcyiptiHV0NC2Jk4wOZTtoPcSuJ71DeMs7w
# mWFrum5LcLzmh5XhFpNWlXzEMEI4un7g6lAPrHLH/u53k+vs2KHnammyXlv1IMCY
# yXQmDQTVYAQ9/ewJS1BFpvgXr59lWrbQ7k+X4aYG0SjIN99Phq+lyyn1UogibXLF
# 3RdKoFL3X5zgIn7I0NYZgAPljLT2oZZaCt6GZ85o6kileNJDPxMq3PCgb33R8bAv
# s+4ihhMdf0uOr8qfFgPulTMjXHftTW44MYIEDTCCBAkCAQEwgZMwfDELMAkGA1UE
# BhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAc
# BgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMdTWljcm9zb2Z0
# IFRpbWUtU3RhbXAgUENBIDIwMTACEzMAAAIn1cCDw7EuVy0AAQAAAicwDQYJYIZI
# AWUDBAIBBQCgggFKMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRABBDAvBgkqhkiG
# 9w0BCQQxIgQgLpjfyvlmjZky+fJV/48I1GBiNFM+vItbhKumLcsg8ccwgfoGCyqG
# SIb3DQEJEAIvMYHqMIHnMIHkMIG9BCDl5wEaNaFSHDiySg6pRNGnav42fU13ZZ11
# kXFxk4QRcjCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5n
# dG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9y
# YXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEwAhMz
# AAACJ9XAg8OxLlctAAEAAAInMCIEIDdvcHNtlHUcHUsTlAr2FouuzO4tJN77x7jY
# pAX7nPpTMA0GCSqGSIb3DQEBCwUABIICAHUuvZ9/I85igI2Q2qsKeYXL7Q35E4SG
# mXZTEGfPMP4uEPGeEyPlL7VpyJJXXnHB2r48JS/gk9Dv+cvt7GU92N6kaTzhQ3Mo
# VVWUgIr+QiDHfWg3/oPrrFin0cf4nmme2L/KKoacM9K4WDNeuvvDY+NHjUVyYtbj
# jAL/8+47MHvF+hDm8nD32ga1QmkUFF7y3IwsfdowkrF0GjeFE3iOtQN3ybiP6WUh
# YisgNz0OPw7JvHlSPE64HnS4Dip7FayRfy3nBjPl5W+nIdAimiw2XJIgIAccoV9n
# IylTejB0G5oYnK3vvWyrBhm9NCMFNNIXYCav38LWiFLC1DSZZn7DEn1OpcNMGKPe
# O9eyZjRBe61Yr8AE7J6MRT+du8i6nBomxUW1mFS1cq+rHzrggX2ehm320nsS+00J
# Soy2NL4ENF8Vs5qgVsLDAPTo6lFjOZZFYG6TKGXVeMC7aFUX6kUVUDxzbYZy6rYZ
# rNJjsF92PegyowlwqWTaFu55dpfkRNI7cdZ5Wy9ebJ3SJCtGf6X/kMX+e9325nLK
# c9CnkVUh8hgfVX79sUDbP4bs3MSrAGkd9WUsBX8oVZcawIiPfvKq2jNgNBOJF4k7
# SpkLO011wlgLIsysLsg6BcseCo1YfZff8z27cHxklguncteRGP3TtqcGNMjUtoAR
# VmiANPXhjncl
# SIG # End Windows Authenticode signature block