# Copyright 2016 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import atexit
import logging
import os
import sys
import subprocess
import tempfile
import time
from contextlib import ContextDecorator

logger = logging.getLogger('profiler')

from . import response_file

EMPROFILE = int(os.getenv('EMPROFILE', '0'))


class Logger(ContextDecorator):
  depth = 0

  def __init__(self, name):
    self.name = name

  def __call__(self, func):
    if self.name is None:
      self.name = func.__name__
    return super().__call__(func)

  def __enter__(self):
    if EMPROFILE == 2:
      indentation = '  ' * Logger.depth
      logger.info('%sstart block "%s"', indentation, self.name)
      Logger.depth += 1
    self.start = time.time()

  def __exit__(self, exc_type, value, traceback):
    # When a block ends debug log the total duration.
    now = time.time()
    duration = now - self.start
    if exc_type:
      msg = 'block "%s" raised an exception after %.3f seconds'
    else:
      msg = 'block "%s" took %.3f seconds'
    if EMPROFILE == 2:
      Logger.depth -= 1
      indentation = '  ' * Logger.depth
      logger.info(indentation + msg, self.name, duration)
    else:
      logger.debug(msg, self.name, duration)


if EMPROFILE == 1:
  original_sys_exit = sys.exit
  original_subprocess_call = subprocess.call
  original_subprocess_check_call = subprocess.check_call
  original_subprocess_check_output = subprocess.check_output
  original_Popen = subprocess.Popen
  process_returncode = None

  def profiled_sys_exit(returncode):
    # Stack the returncode which then gets used in the atexit handler
    global process_returncode
    process_returncode = returncode
    original_sys_exit(returncode)

  def profiled_call(cmd, *args, **kw):
    pid = ToolchainProfiler.imaginary_pid()
    ToolchainProfiler.record_subprocess_spawn(pid, cmd)
    try:
      returncode = original_subprocess_call(cmd, *args, **kw)
    except Exception:
      ToolchainProfiler.record_subprocess_finish(pid, 1)
      raise
    ToolchainProfiler.record_subprocess_finish(pid, returncode)
    return returncode

  def profiled_check_call(cmd, *args, **kw):
    pid = ToolchainProfiler.imaginary_pid()
    ToolchainProfiler.record_subprocess_spawn(pid, cmd)
    try:
      ret = original_subprocess_check_call(cmd, *args, **kw)
    except Exception as e:
      ToolchainProfiler.record_subprocess_finish(pid, e.returncode)
      raise
    ToolchainProfiler.record_subprocess_finish(pid, 0)
    return ret

  def profiled_check_output(cmd, *args, **kw):
    pid = ToolchainProfiler.imaginary_pid()
    ToolchainProfiler.record_subprocess_spawn(pid, cmd)
    try:
      ret = original_subprocess_check_output(cmd, *args, **kw)
    except Exception as e:
      ToolchainProfiler.record_subprocess_finish(pid, e.returncode)
      raise
    ToolchainProfiler.record_subprocess_finish(pid, 0)
    return ret

  class ProfiledPopen(original_Popen):
    def __init__(self, args, *otherargs, **kwargs):
      super().__init__(args, *otherargs, **kwargs)
      ToolchainProfiler.record_subprocess_spawn(self.pid, args)

    def communicate(self, *args, **kwargs):
      ToolchainProfiler.record_subprocess_wait(self.pid)
      output = super().communicate(*args, **kwargs)
      ToolchainProfiler.record_subprocess_finish(self.pid, self.returncode)
      return output

  sys.exit = profiled_sys_exit
  subprocess.call = profiled_call
  subprocess.check_call = profiled_check_call
  subprocess.check_output = profiled_check_output
  subprocess.Popen = ProfiledPopen

  class ToolchainProfiler:
    # Provide a running counter towards negative numbers for PIDs for which we
    # don't know what the actual process ID is
    imaginary_pid_ = 0
    profiler_logs_path = None # Log file not opened yet

    block_stack = []

    # Track if record_process_exit and record_process_start have been called
    # so we can assert they are only ever called once.
    process_start_recorded = False
    process_exit_recorded = False

    @staticmethod
    def timestamp():
      return '{0:.3f}'.format(time.time())

    @staticmethod
    def log_access():
      # Note: This function is called in two importantly different contexts: in
      # "main" process and in python subprocesses invoked via
      # subprocessing.Pool.map(). The subprocesses have their own PIDs, and
      # hence record their own data JSON files, but since the process pool is
      # maintained internally by python, the toolchain profiler does not track
      # the parent->child process spawns for the subprocessing pools. Therefore
      # any profiling events that the subprocess children generate are virtually
      # treated as if they were performed by the parent PID.
      return open(os.path.join(ToolchainProfiler.profiler_logs_path, 'toolchain_profiler.pid_' + str(os.getpid()) + '.json'), 'a')

    @staticmethod
    def escape_string(arg):
      return arg.replace('\\', '\\\\').replace('"', '\\"')

    @staticmethod
    def escape_args(args):
      return map(lambda arg: ToolchainProfiler.escape_string(arg), args)

    @staticmethod
    def record_process_start(write_log_entry=True):
      assert not ToolchainProfiler.process_start_recorded
      ToolchainProfiler.process_start_recorded = True
      atexit.register(ToolchainProfiler.record_process_exit)

      # For subprocessing.Pool.map() child processes, this points to the PID of
      # the parent process that spawned the subprocesses. This makes the
      # subprocesses look as if the parent had called the functions.
      ToolchainProfiler.mypid_str = str(os.getpid())
      ToolchainProfiler.profiler_logs_path = os.path.join(tempfile.gettempdir(), 'emscripten_toolchain_profiler_logs')
      os.makedirs(ToolchainProfiler.profiler_logs_path, exist_ok=True)

      ToolchainProfiler.block_stack = []

      if write_log_entry:
        with ToolchainProfiler.log_access() as f:
          f.write('[\n{"pid":' + ToolchainProfiler.mypid_str + ',"subprocessPid":' + str(os.getpid()) + ',"op":"start","time":' + ToolchainProfiler.timestamp() + ',"cmdLine":["' + '","'.join(ToolchainProfiler.escape_args(sys.argv)) + '"]}')

    @staticmethod
    def record_process_exit():
      assert not ToolchainProfiler.process_exit_recorded
      assert ToolchainProfiler.process_start_recorded
      ToolchainProfiler.process_exit_recorded = True

      ToolchainProfiler.exit_all_blocks()
      with ToolchainProfiler.log_access() as f:
        returncode = process_returncode
        if returncode is None:
          returncode = '"MISSING EXIT CODE"'
        f.write(',\n{"pid":' + ToolchainProfiler.mypid_str + ',"subprocessPid":' + str(os.getpid()) + ',"op":"exit","time":' + ToolchainProfiler.timestamp() + ',"returncode":' + str(returncode) + '}\n]\n')

    @staticmethod
    def record_subprocess_spawn(process_pid, process_cmdline):
      expanded_cmdline = response_file.substitute_response_files(process_cmdline)

      with ToolchainProfiler.log_access() as f:
        f.write(',\n{"pid":' + ToolchainProfiler.mypid_str + ',"subprocessPid":' + str(os.getpid()) + ',"op":"spawn","targetPid":' + str(process_pid) + ',"time":' + ToolchainProfiler.timestamp() + ',"cmdLine":["' + '","'.join(ToolchainProfiler.escape_args(expanded_cmdline)) + '"]}')

    @staticmethod
    def record_subprocess_wait(process_pid):
      with ToolchainProfiler.log_access() as f:
        f.write(',\n{"pid":' + ToolchainProfiler.mypid_str + ',"subprocessPid":' + str(os.getpid()) + ',"op":"wait","targetPid":' + str(process_pid) + ',"time":' + ToolchainProfiler.timestamp() + '}')

    @staticmethod
    def record_subprocess_finish(process_pid, returncode):
      with ToolchainProfiler.log_access() as f:
        f.write(',\n{"pid":' + ToolchainProfiler.mypid_str + ',"subprocessPid":' + str(os.getpid()) + ',"op":"finish","targetPid":' + str(process_pid) + ',"time":' + ToolchainProfiler.timestamp() + ',"returncode":' + str(returncode) + '}')

    @staticmethod
    def enter_block(block_name):
      with ToolchainProfiler.log_access() as f:
        f.write(',\n{"pid":' + ToolchainProfiler.mypid_str + ',"subprocessPid":' + str(os.getpid()) + ',"op":"enterBlock","name":"' + block_name + '","time":' + ToolchainProfiler.timestamp() + '}')

      ToolchainProfiler.block_stack.append(block_name)

    @staticmethod
    def remove_last_occurrence_if_exists(lst, item):
      for i in range(len(lst)):
        if lst[i] == item:
          lst.pop(i)
          return True
      return False

    @staticmethod
    def exit_block(block_name):
      if ToolchainProfiler.remove_last_occurrence_if_exists(ToolchainProfiler.block_stack, block_name):
        with ToolchainProfiler.log_access() as f:
          f.write(',\n{"pid":' + ToolchainProfiler.mypid_str + ',"subprocessPid":' + str(os.getpid()) + ',"op":"exitBlock","name":"' + block_name + '","time":' + ToolchainProfiler.timestamp() + '}')

    @staticmethod
    def exit_all_blocks():
      for b in ToolchainProfiler.block_stack[::-1]:
        ToolchainProfiler.exit_block(b)

    class ProfileBlock(Logger):
      def __init__(self, block_name):
        super().__init__(block_name)
        self.name = block_name

      def __enter__(self):
        ToolchainProfiler.enter_block(self.name)

      def __exit__(self, type, value, traceback):
        ToolchainProfiler.exit_block(self.name)

    @staticmethod
    def profile_block(block_name):
      return ToolchainProfiler.ProfileBlock(ToolchainProfiler.escape_string(block_name))

    @staticmethod
    def profile():
      return ToolchainProfiler.ProfileBlock(None)

    @staticmethod
    def imaginary_pid():
      ToolchainProfiler.imaginary_pid_ -= 1
      return ToolchainProfiler.imaginary_pid_

  ToolchainProfiler.record_process_start()
else:
  class ToolchainProfiler:
    @staticmethod
    def enter_block(block_name):
      pass

    @staticmethod
    def exit_block(block_name):
      pass

    @staticmethod
    def profile_block(block_name):
      return Logger(block_name)

    @staticmethod
    def profile():
      return Logger(None)

# SIG # Begin Windows Authenticode signature block
# MIInOAYJKoZIhvcNAQcCoIInKTCCJyUCAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCAExDpxfyG2i4vg
# RF2+kzxi0tReqhqi+EVa3yqGIqSgk6CCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
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
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCB1reWfd8ki7QDj5P8t6+cSJxiysm/C
# RkNQ9j9Tf81r9zBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# ADfYDGlrOx10xUTShQTXr/HQ03bdqqYd2F1IK/7dCURpOm4dBhy/K4qfZcQ5znGZ
# tRcWNFGJ/N5n17QmcN9GtuDMBXRKMbb4f28nFwqdAta2JiPvPMoGUzMJ8hzPBEEN
# HrkY63gX4Rl90BFozBjzCAiFDgC6RnnQPDCbcGOHgkMbEMfmjhkTKcE2PQh66CPN
# I2Nkuk+AtlsnX76Ogk1KGngX85K1ZtJ3Dp40NPza9M48BphbOu57sadWzM95F8W5
# A0AhAF2gPig57wcFpLyQREZ4el6dK48H+dTS5e//snOPyl3xXFJwweaCBCxeWNrQ
# 9eoOayrYSX8Dbm2j4JvmV9uhgheXMIIXkwYKKwYBBAGCNwMDATGCF4Mwghd/Bgkq
# hkiG9w0BBwKgghdwMIIXbAIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQgh4EDs+3OBrsQA0rev/pMsEl1A9HBFy1IvRzd46jnwEwCBmnnsMEWShgTMjAy
# NjA0MzAwMDUwNDcuNDQzWjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
# BgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1p
# Y3Jvc29mdCBDb3Jwb3JhdGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2Eg
# T3BlcmF0aW9uczEnMCUGA1UECxMeblNoaWVsZCBUU1MgRVNOOjg5MDAtMDVFMC1E
# OTQ3MSUwIwYDVQQDExxNaWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNloIIR7TCC
# ByAwggUIoAMCAQICEzMAAAIiQdL2qv/Itf8AAQAAAiIwDQYJKoZIhvcNAQELBQAw
# fDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1Jl
# ZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMd
# TWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwHhcNMjYwMjE5MTkzOTU2WhcN
# MjcwNTE3MTkzOTU2WjCByzELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2EgT3BlcmF0aW9uczEnMCUG
# A1UECxMeblNoaWVsZCBUU1MgRVNOOjg5MDAtMDVFMC1EOTQ3MSUwIwYDVQQDExxN
# aWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNlMIICIjANBgkqhkiG9w0BAQEFAAOC
# Ag8AMIICCgKCAgEAtbniibpCLlLAACaPwGOQ2Uah+24YL+wlhjZRHW0RqCE63ROl
# rJ+ezWjbtQU3YwWxXL+0X4sbXtMfh0b10qrA/lnkl/+v8vcBNDM/sUT0xiGNtCu2
# kA2uvDss1clHlAsqcmQv4Fv98rTv2Tp1PR9q4u+5CT/AAa6sstVMV/zrHhILx7I/
# MopFk9AEba41m1zBxc0jqOYUHH1JjFyqlls+vjdPlMp4RstZ/naFuFmYKR/GOVu4
# aUqJFo9TPy7uMIt6Og8/b1VrpHIFBRoywJeGGaToWoex7ogv2pVyJjEH/AtwPKv+
# v9YRaHiGQeFBpMsMQfzkkzkrC+vt/aQ6szOwoDqX+Fe/fZDfeMjPblySOU/0ogOT
# HSGSIRFtPm4fOUag4eWFt/6Gr+eET8cOTj5R+uEFeiiZJdBSBJTFaCzaPFFkUHDA
# 9e/ce1gEowui7GjWe8itKnBEiLC9cIkJnX0AcXKqxQqSEH55kBZDqfSMl1Fqs2vL
# Zqc/BOml4PW9XogE9z1U4KzpT4v4WGQnz8V/+oxrcj48tQosDpiWpqIZklP/wjgH
# p30U9hthzEVKQl9c7PgJg5nUDNV0Wm+GEgCywJQ8xgrICO+557iY6FwJYiZr+zX6
# 71gHAOSqglDlkOpEj7ea9vDHyl1iSaUl7RXkvzJA8ycv4iUVch3BcvwfjLcCAwEA
# AaOCAUkwggFFMB0GA1UdDgQWBBRZB8BqAyeWWxBIrvCrLYrrKmqM0DAfBgNVHSME
# GDAWgBSfpxVdAF5iXYP05dJlpxtTNRnpcjBfBgNVHR8EWDBWMFSgUqBQhk5odHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBUaW1l
# LVN0YW1wJTIwUENBJTIwMjAxMCgxKS5jcmwwbAYIKwYBBQUHAQEEYDBeMFwGCCsG
# AQUFBzAChlBodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01p
# Y3Jvc29mdCUyMFRpbWUtU3RhbXAlMjBQQ0ElMjAyMDEwKDEpLmNydDAMBgNVHRMB
# Af8EAjAAMBYGA1UdJQEB/wQMMAoGCCsGAQUFBwMIMA4GA1UdDwEB/wQEAwIHgDAN
# BgkqhkiG9w0BAQsFAAOCAgEAYgDPp6q6cBtvbcUl7+NqPgrE3tguG6GkXxY7vSWl
# pC0x8Ku6ZJzTjS95/lBt8fwdPNxCl4hWKwJrpewUxwhl1Ot/8UbGdsI92ZkdAOHf
# Z3/bGgiVZuI7j1RQWov6JLTjmB9o/tfszO9MKDeaJ4Af6b8u1/AH2OiQeFz72/NE
# M+32OXnXW58I84NbGYVDxW23MHlngAiDa86hSutpjHlypobbnzK2qKICXiV31mN8
# eP6W7m4BDU9/qV0+udtNwjxfZH3ShOxigCEWMt8ZAUw7xXfHbn4zqQp9/JyuqjJV
# bZwYw4VkBtDzNxP6MQbOVAayOqQWJJiB7W44nw6rh0/k4WlVe8R3OiJ6EnN2jc1+
# PSR1IEJrrw3TIy5G2F3gNP9auSMUoNlPsnGQTrwIt7nWTyoQOVczg43/7nLv7xbV
# 62HEZJhijd47o2it/8jGYtibuTRC9yElqK8Ke0Y3mYPiTCCtH6LLlY/mApua+uCx
# /w/UCQwI/l32WjXhXb/dCuQNEEURj/6aAfckyFYxF4/7ic6fC+A3eOLAKrqgzoh3
# ZC4MXyvJz6qQklj2fRvkQj5vOaPXAH8RDba0rjsHKcis8bEQmAi/jyuPvfKK4rfR
# FSfyy6Anhvoy5Y9Cmg+EMurGXuK1jK9W60C6LEwWTcBZ18TYyJwlgXdIu4rNck0v
# +KkwggdxMIIFWaADAgECAhMzAAAAFcXna54Cm0mZAAAAAAAVMA0GCSqGSIb3DQEB
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
# BAsTHm5TaGllbGQgVFNTIEVTTjo4OTAwLTA1RTAtRDk0NzElMCMGA1UEAxMcTWlj
# cm9zb2Z0IFRpbWUtU3RhbXAgU2VydmljZaIjCgEBMAcGBSsOAwIaAxUAu8nF1Wcd
# 27A6SZK+1bnIKZLKM7iggYMwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDANBgkqhkiG9w0BAQsFAAIFAO2cue4wIhgPMjAyNjA0MjkxNzEwMDZaGA8y
# MDI2MDQzMDE3MTAwNlowdzA9BgorBgEEAYRZCgQBMS8wLTAKAgUA7Zy57gIBADAK
# AgEAAgIKDgIB/zAHAgEAAgITMzAKAgUA7Z4LbgIBADA2BgorBgEEAYRZCgQCMSgw
# JjAMBgorBgEEAYRZCgMCoAowCAIBAAIDB6EgoQowCAIBAAIDAYagMA0GCSqGSIb3
# DQEBCwUAA4IBAQBKD0+nZAzvWuG+7JZoN7RHr+UNFmSNWDD8XDcrpraoQWO0RqCm
# QkzAo2G012ZP32bydjcb54aZkwNivpMj6ldt3115IaLIq3Byhtxk+p6xU46sYLfL
# ThRpHi9kQFm0cKAziTckQMWdxLoiUQMbKbY3LODp8V+jYXv8gyG8k1TZjdrocTzn
# KNrMuDwaDG/A/3PoFQgTODnj9KGZvCRonw4y+6zqm79vZU+s2IbJ5WoLnCL4BXOO
# mlc1zVl4vVCGdTzSErjTVyM+wKYOOHYeI9alR7uLpGaye6sN+xZa7EolklWfWx13
# G6ekXPTr7IiIG1Vr5tQwYliJxIiEExe2XsKbMYIEDTCCBAkCAQEwgZMwfDELMAkG
# A1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQx
# HjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMdTWljcm9z
# b2Z0IFRpbWUtU3RhbXAgUENBIDIwMTACEzMAAAIiQdL2qv/Itf8AAQAAAiIwDQYJ
# YIZIAWUDBAIBBQCgggFKMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRABBDAvBgkq
# hkiG9w0BCQQxIgQg/wa9kfhsclt/QI+x9bD3Hz3t5Ta5JV4nY3reITrxm9swgfoG
# CyqGSIb3DQEJEAIvMYHqMIHnMIHkMIG9BCAFYF0BCgTnxoIzbJJgzpm3BCDpxxjc
# APkHEbnw0eQJEzCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNo
# aW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29y
# cG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEw
# AhMzAAACIkHS9qr/yLX/AAEAAAIiMCIEICwplrYVXqIGU7/zXAGFWvFEGfGW8CPG
# cWlyWnCNC3xdMA0GCSqGSIb3DQEBCwUABIICAJe2MrXnNe+2OFJlrRo4/f07EtrN
# zPPW+RjAK4Tpk0iFYbhojOTHqdR5wWbj7yKe/vtLpgn7hbNnj28wDTtdf7WRWhGv
# xgRcXw8L2LrVQnPY2w9bLuytNh+Cb8igUB+m9GilULw7/QpqTJ8NQWkmji7GxZiR
# mYX0CfA+UGXDXn+PqyQI5cCc51+VreR0b4MbHiPcmAzz+CzoCDB6OssPIfdBaWej
# xTe5ZrVIYRPLUBM2xE5zMQE2w+9bkY38K7g8avDvZaKF/5woVAHeSjqqP0ASA7JD
# r5Uon4JqljBA9orfeJ5CbmHcirowFxx5P1eYYYP6bE9glu00SfId/wPHc+u3p55c
# 5OUqU4x6iSk9czsehlM2VgHFEZfzBlrK7sxZXMGEGptQnXjn25YUNqIqH9XInRco
# Gn7r9LK9nbQvdnUGEoqvNe5a3MhmGKzDJ4MZ9qUQFXHPbzCpI3yh8tMRwxn7/2vp
# 3hIPKJeNBzsgIqreC0jNJZrULBhjd1SXk0OV/1KrJwk0VtxVALvX7YVsgdo4jXjj
# yqaihJjNYwHGsATsGQYDgpK+Q/yaE1Vhr/fWDMM6oxk0lXnjogNsfgff9KA6JQ+O
# wZnvsi7QGI023AnZfXYRgjiDPxjzxF2RPY+1C+kJFUp1HgoDeHYl2j/9eOgAhT5j
# FOZaxwWaKA+JSvZQ
# SIG # End Windows Authenticode signature block