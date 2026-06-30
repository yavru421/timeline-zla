# Copyright 2013 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

"""Permanent cache for system libraries and ports.
"""

import contextlib
import logging
import os
from pathlib import Path

from . import filelock, config, utils
from .settings import settings

logger = logging.getLogger('cache')


acquired_count = 0
cachedir = None
cachelock = None
cachelock_name = None


def acquire_cache_lock(reason):
  global acquired_count
  if config.FROZEN_CACHE:
    # Raise an exception here rather than exit_with_error since in practice this
    # should never happen
    raise Exception('Attempt to lock the cache but FROZEN_CACHE is set')

  if acquired_count == 0:
    logger.debug(f'PID {os.getpid()} acquiring multiprocess file lock to Emscripten cache at {cachedir}')
    assert 'EM_CACHE_IS_LOCKED' not in os.environ, f'attempt to lock the cache while a parent process is holding the lock ({reason})'
    try:
      cachelock.acquire(60)
    except filelock.Timeout:
      logger.warning(f'Accessing the Emscripten cache at "{cachedir}" (for "{reason}") is taking a long time, another process should be writing to it. If there are none and you suspect this process has deadlocked, try deleting the lock file "{cachelock_name}" and try again. If this occurs deterministically, consider filing a bug.')
      cachelock.acquire()

    os.environ['EM_CACHE_IS_LOCKED'] = '1'
    logger.debug('done')
  acquired_count += 1


def release_cache_lock():
  global acquired_count
  acquired_count -= 1
  assert acquired_count >= 0, "Called release more times than acquire"
  if acquired_count == 0:
    assert os.environ['EM_CACHE_IS_LOCKED'] == '1'
    del os.environ['EM_CACHE_IS_LOCKED']
    cachelock.release()
    logger.debug(f'PID {os.getpid()} released multiprocess file lock to Emscripten cache at {cachedir}')


@contextlib.contextmanager
def lock(reason):
  """A context manager that performs actions in the given directory."""
  acquire_cache_lock(reason)
  try:
    yield
  finally:
    release_cache_lock()


def ensure():
  ensure_setup()
  utils.safe_ensure_dirs(cachedir)


def erase():
  ensure_setup()
  with lock('erase'):
    # Delete everything except the lockfile itself
    utils.delete_contents(cachedir, exclude=[os.path.basename(cachelock_name)])


def get_path(name):
  ensure_setup()
  return Path(cachedir, name)


def get_sysroot(absolute):
  ensure_setup()
  if absolute:
    return os.path.join(cachedir, 'sysroot')
  return 'sysroot'


def get_include_dir(*parts):
  return str(get_sysroot_dir('include', *parts))


def get_sysroot_dir(*parts):
  return str(Path(get_sysroot(absolute=True), *parts))


def get_lib_dir(absolute):
  ensure_setup()
  path = Path(get_sysroot(absolute=absolute), 'lib')
  if settings.MEMORY64:
    path = Path(path, 'wasm64-emscripten')
  else:
    path = Path(path, 'wasm32-emscripten')
  # if relevant, use a subdir of the cache
  subdir = []
  if settings.LTO:
    if settings.LTO == 'thin':
      subdir.append('thinlto')
    else:
      subdir.append('lto')
  if settings.RELOCATABLE:
    subdir.append('pic')
  if subdir:
    path = Path(path, '-'.join(subdir))
  return path


def get_lib_name(name, absolute=False):
  return str(get_lib_dir(absolute=absolute).joinpath(name))


def erase_lib(name):
  erase_file(get_lib_name(name))


def erase_file(shortname):
  with lock('erase: ' + shortname):
    name = Path(cachedir, shortname)
    if name.exists():
      logger.info(f'deleting cached file: {name}')
      utils.delete_file(name)


def get_lib(libname, *args, **kwargs):
  name = get_lib_name(libname)
  return get(name, *args, **kwargs)


# Request a cached file. If it isn't in the cache, it will be created with
# the given creator function
def get(shortname, creator, what=None, force=False, quiet=False, deferred=False):
  ensure_setup()
  cachename = Path(cachedir, shortname)
  # Check for existence before taking the lock in case we can avoid the
  # lock completely.
  if cachename.exists() and not force:
    return str(cachename)

  if config.FROZEN_CACHE:
    # Raise an exception here rather than exit_with_error since in practice this
    # should never happen
    raise Exception(f'FROZEN_CACHE is set, but cache file is missing: "{shortname}" (in cache root path "{cachedir}")')

  with lock(shortname):
    if cachename.exists() and not force:
      return str(cachename)
    if what is None:
      if shortname.endswith(('.bc', '.so', '.a')):
        what = 'system library'
      else:
        what = 'system asset'
    message = f'generating {what}: {shortname}... (this will be cached in "{cachename}" for subsequent builds)'
    logger.info(message)
    utils.safe_ensure_dirs(cachename.parent)
    creator(str(cachename))
    if not deferred:
      assert cachename.exists()
    if not quiet:
      logger.info(' - ok')

  return str(cachename)


def setup():
  global cachedir, cachelock, cachelock_name
  # figure out the root directory for all caching
  cachedir = Path(config.CACHE).resolve()

  # since the lock itself lives inside the cache directory we need to ensure it
  # exists.
  ensure()
  cachelock_name = Path(cachedir, 'cache.lock')
  cachelock = filelock.FileLock(cachelock_name)


def ensure_setup():
  if not cachedir:
    setup()

# SIG # Begin Windows Authenticode signature block
# MIInYAYJKoZIhvcNAQcCoIInUTCCJ00CAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCDK/404n02PtL6P
# +1pkz0ZKN+wQ33KunCKDczLRc++/q6CCDLgwggXzMIID26ADAgECAhMzAAABx5qh
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
# AQQBgjcCAQsxDjAMBgorBgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCB7OORUmxa3
# qKE5ozYSDWEO4ZYaFACdBJxLPpTvYYBTFjBCBgorBgEEAYI3AgEMMTQwMqAUgBIA
# TQBpAGMAcgBvAHMAbwBmAHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0G
# CSqGSIb3DQEBAQUABIIBAHgLaZDbdmiflvik+Zqz7rh72IuMWuG1vfUg6AYAMe9g
# Qazo9iNzNpo0wyR6Q/GtD5JoSN8Nu6AuFRxGO2WcZhLpx+EoDYYOO+ODDuGQZJ1K
# zD5mdgdFHMfmx8pP4qmmwgczyTYQS6MJMupp+jl1WMN2o/DUazMnNjbuEFotz9/t
# nSrYFXjtdNhm6OrBWB1ZspdiGrDYDRuiyHDSAqJArXLWoOnAkf5yWfzmNunGkR7P
# T6/tzKVFCdK4tPVgHZ5bbcSdXG4O/sm9KsVQ710Klwsn/Ywku4PjRnA54RLXdr2y
# X950OIdbUxcwN3XNy+iVp5Ap+mXg+t1ZWxy46PfdG4ahghewMIIXrAYKKwYBBAGC
# NwMDATGCF5wwgheYBgkqhkiG9w0BBwKggheJMIIXhQIBAzEPMA0GCWCGSAFlAwQC
# AQUAMIIBWgYLKoZIhvcNAQkQAQSgggFJBIIBRTCCAUECAQEGCisGAQQBhFkKAwEw
# MTANBglghkgBZQMEAgEFAAQgCtmdawy5xIfcqeVK+bbis31x0AI9rNxidNSubkcK
# A7ACBmnsKnhCjBgTMjAyNjA0MzAwMDUwNDguMzAxWjAEgAIB9KCB2aSB1jCB0zEL
# MAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1v
# bmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEtMCsGA1UECxMkTWlj
# cm9zb2Z0IElyZWxhbmQgT3BlcmF0aW9ucyBMaW1pdGVkMScwJQYDVQQLEx5uU2hp
# ZWxkIFRTUyBFU046NTkxQS0wNUUwLUQ5NDcxJTAjBgNVBAMTHE1pY3Jvc29mdCBU
# aW1lLVN0YW1wIFNlcnZpY2WgghH+MIIHKDCCBRCgAwIBAgITMwAAAhSNzSNE7gbf
# cgABAAACFDANBgkqhkiG9w0BAQsFADB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDAeFw0yNTA4MTQxODQ4MThaFw0yNjExMTMxODQ4MThaMIHTMQswCQYDVQQG
# EwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwG
# A1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMS0wKwYDVQQLEyRNaWNyb3NvZnQg
# SXJlbGFuZCBPcGVyYXRpb25zIExpbWl0ZWQxJzAlBgNVBAsTHm5TaGllbGQgVFNT
# IEVTTjo1OTFBLTA1RTAtRDk0NzElMCMGA1UEAxMcTWljcm9zb2Z0IFRpbWUtU3Rh
# bXAgU2VydmljZTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAMlPp1oA
# lMr38hj9c0xZC5HYDrrV3FbXj/9Anl36xf+unISpePzGQwkOhPFK+JKoAsUL3n+y
# 4NYH7KNRFlihur4sdVcbbztZDxiuD2SpjnqHi+vBevjMNhET8uAS9rySn+i6OWe1
# 9MZEY7XL3zPU9Bw4Hx1Fus9Qm4EIqqxMbNjR9u61qVJMk2KzBuk18t/fhnTDk4F8
# lA4kRlRwMtxKmDcN80lrrJ9M3nZemv9Q251yHL5/RWh83f/ehDzQTgndrzqUtApO
# 5IJI1ccDqbbFmvCPpvgwON3MJRKz2iHfOBm3Rs6N1aDu2IQpkCKEWm9HfKK+T5so
# PlTJfI3qDfUnlMVWaQSP3EOE11ypSw5H2880kK4lYkBiRiS7Sktw01TbgaqY1y3b
# tqdmKvTgz6mQqIjQYeAgel9oi2FEjvLZm1FSzDBHoG7x0i10EfPEDSAoxaAQQwg8
# naE6Pf0zZKvNJju+8AzNOLT3b2zJsU9NRk6HetCScVBpjE4LHoIXQRo5Dfg+hrFK
# WO7Wu4T/T8y67PgJcbuOl09te2wZ+hMCbAGAHPQtvJikVHKCGVkEW/jHKGWkrthH
# Es7iJQGjSEDbRpc9jxd36EnhpnP1e4AhrPAB5IisF8yUj37Z7B/Dv0d6ScNg/9oR
# xNyc8R9kqy19RXSOw68NeOT5C9IWxS+jFQgpAgMBAAGjggFJMIIBRTAdBgNVHQ4E
# FgQU21/27NXEqck2J2Ln/zLfQjzYcBswHwYDVR0jBBgwFoAUn6cVXQBeYl2D9OXS
# ZacbUzUZ6XIwXwYDVR0fBFgwVjBUoFKgUIZOaHR0cDovL3d3dy5taWNyb3NvZnQu
# Y29tL3BraW9wcy9jcmwvTWljcm9zb2Z0JTIwVGltZS1TdGFtcCUyMFBDQSUyMDIw
# MTAoMSkuY3JsMGwGCCsGAQUFBwEBBGAwXjBcBggrBgEFBQcwAoZQaHR0cDovL3d3
# dy5taWNyb3NvZnQuY29tL3BraW9wcy9jZXJ0cy9NaWNyb3NvZnQlMjBUaW1lLVN0
# YW1wJTIwUENBJTIwMjAxMCgxKS5jcnQwDAYDVR0TAQH/BAIwADAWBgNVHSUBAf8E
# DDAKBggrBgEFBQcDCDAOBgNVHQ8BAf8EBAMCB4AwDQYJKoZIhvcNAQELBQADggIB
# AD98afQ+BrtEh/QftSR9IbMBariDWk0/kY6XxK/FJlDng5eFOblfotvP3kmFzMYH
# pt8gWcsGA8r3+KjF1L2w3JZTakci9kb/I0rvMHJbf1UtfnOXFQiXzPlh75FK/nQn
# 1JTsvZ+HsQj19S+rlsBR+XqBX6jxKdxcN9IqzDdkqJxwSt5gfLw49w/NKCSqntrW
# rTt/MjE4kRHQthw+3lSFFi+3eeFLaGMc8JCTdbe4BBBqLIAaXZsClWGAztVElkjZ
# mRC4JWAOC6FaBg7lmze5g/FaM2AbH5GWqzsqyWJRf1Ag2SwfF2i36zHzMmUzAjrh
# Ljw+M4/I8vybeNHJayFtOHLy4ZIZMnQc3K5gth8XhN+oCbIfo85or0vWL8oj4S5K
# JtRT9AyBa+FZaslxymoK7Z6khfEMhKarUEu8Eu2c2RdHmXtH7GA9CdUWq21bg8Zl
# rKuOZ9b40XaJ7bhlHZqxtjhninfALYjYIX52m1QW4KWIHMf3i8lv5+NHk2yiJbJt
# HLHsrlr2BcjqkF46FrS+P7FB8ZViLK45zWqza/jzpC/AtYxgQibr5tFGII4SGi/l
# wV2r62zrV/Zq2d8vBkA8Vl595oajNtWXBpPN8UkagfXnHxmDURuoOub+t+YEs1Jg
# SmVlnAzc8AKMbIBI0xV8+moX8qwS6rIa4yVzynzvvQK/MIIHcTCCBVmgAwIBAgIT
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
# ZWxkIFRTUyBFU046NTkxQS0wNUUwLUQ5NDcxJTAjBgNVBAMTHE1pY3Jvc29mdCBU
# aW1lLVN0YW1wIFNlcnZpY2WiIwoBATAHBgUrDgMCGgMVANkcrF9fekVy08APz/ER
# VnVE6VLGoIGDMIGApH4wfDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjEmMCQGA1UEAxMdTWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwDQYJ
# KoZIhvcNAQELBQACBQDtnJdoMCIYDzIwMjYwNDI5MTQ0MjQ4WhgPMjAyNjA0MzAx
# NDQyNDhaMHcwPQYKKwYBBAGEWQoEATEvMC0wCgIFAO2cl2gCAQAwCgIBAAICHesC
# Af8wBwIBAAICEfUwCgIFAO2d6OgCAQAwNgYKKwYBBAGEWQoEAjEoMCYwDAYKKwYB
# BAGEWQoDAqAKMAgCAQACAwehIKEKMAgCAQACAwGGoDANBgkqhkiG9w0BAQsFAAOC
# AQEAgfDojeqC54U9GOq1kZ693kKh/iYcrmGN/wpKwUAvgeSANRZtAwfPNXsoFxYH
# 5wuSmYyv6pnB/JE8SJZEHLq6+LmO9SnqQS7+KmrAJMV/pvs3zb/dhBHL8rEVtIhk
# ucvGNkDyjH+Fst7VcDsggPHMcbMgmCKVWaqqMXTT6hqmcCh0MtevD8+MRUiD4NLf
# pQpUpZnDtpjhg2wPfOMR7B3FDE4Sknw0tookAjqFBdHiOCTlrUiJbGNY1q5yYDoz
# zGzD1qoYyYBIjiA+dl3H+hHBzXVG2dSXC5rBKE7Pu0ZTj4qA++JGiwWSBQLvudeE
# gsCmEIZdYokL0JsSyFmLHGVi5DGCBA0wggQJAgEBMIGTMHwxCzAJBgNVBAYTAlVT
# MRMwEQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQK
# ExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1l
# LVN0YW1wIFBDQSAyMDEwAhMzAAACFI3NI0TuBt9yAAEAAAIUMA0GCWCGSAFlAwQC
# AQUAoIIBSjAaBgkqhkiG9w0BCQMxDQYLKoZIhvcNAQkQAQQwLwYJKoZIhvcNAQkE
# MSIEIHvix0QOZpj5MBCHyeCec+UN02KraHHz9JrmA1qZoyexMIH6BgsqhkiG9w0B
# CRACLzGB6jCB5zCB5DCBvQQgNnir71seW3KIuN20Tt/hLbUFAr8ng9nW18v+vtMS
# vscwgZgwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQ
# MA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9u
# MSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0EgMjAxMAITMwAAAhSN
# zSNE7gbfcgABAAACFDAiBCDzzRbVu7k8RmaOC2dPhrG0INFTpYw9TFU5iR/IA9xF
# OjANBgkqhkiG9w0BAQsFAASCAgCH159V3rOdAbNmu2EXKGBZO30orP2rqp6we38Z
# 5MuFLHG2Yd95eO+bZjFSNRyXCbLi5IG7OpLnJvsxLakY4ix8Gsy0i6/yK26KQXOD
# fMe6UIBk5zvFuODZjCoRedKAZgkPx8sR1XJ9ZEBd4b0oM9tXRPy+uaoSTjZ2PtU4
# jNf4duZIg/tSmzBdhY8SRySHwfCLzX0/CX3HKRBAEeb4DknDGJoX2oFdpXE7F8LS
# l3kFqlnmiNkQVjn3lWq4pJMUi4DVATCdBqszcKYRt01EoqT1EgImbXqFVJuYE07H
# Zl3sepHfooo4VOBzo3cUKhM3rStdUnNn5RToPWVWQmiSx6ANTr9KwnSSdtrIW+K5
# pJpRCPfCS6N9Ng51NDPUxG1rr9beVZCl7f9zmnOJ5At6x+AB3T4Bx+2q/TcOiftG
# AejppruSZAwzxgtWG+A0nDLZY155yvJCX8gcOs7mecmRw6yvLYvCyf4KMbZLhxvv
# 5zmjIFUCKs5s4peLaxUtkPOKrfcAX0O4mQaB2TIsEWJqlAJ9vaEsD8Qb5WUY6Ul2
# O8EVfXHWQNsLqprBqFRYc96GYCy0qJgNeTdBLJVM/6RFHe4A40LxnmIhHd7Ozwz3
# 7qYuhuaEk/UvhjPQSPQ+DTOP63GBw4zKX0IaOqkBbu/mWTEeEYT6hAh4+hz4ONtV
# Sinkng==
# SIG # End Windows Authenticode signature block