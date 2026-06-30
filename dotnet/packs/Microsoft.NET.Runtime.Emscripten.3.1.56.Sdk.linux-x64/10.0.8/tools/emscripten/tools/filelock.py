# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# For more information, please refer to <http://unlicense.org>

# This software package was obtained from
# https://github.com/benediktschmitt/py-filelock
#
# Local changes:
# - Changed logger.info to logger.warn to avoid displaying logging
#   information under normal emscripten usage.

"""
A platform independent file lock that supports the with-statement.
"""


# Modules
# ------------------------------------------------
import logging
import os
import threading
import time
try:
    import warnings
except ImportError:
    warnings = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    import fcntl
except ImportError:
    fcntl = None


# Backward compatibility
# ------------------------------------------------
try:
    TimeoutError
except NameError:
    TimeoutError = OSError


# Data
# ------------------------------------------------
__all__ = [
    "Timeout",
    "BaseFileLock",
    "WindowsFileLock",
    "UnixFileLock",
    "SoftFileLock",
    "FileLock"
]

__version__ = "3.0.12"


_logger = None
def logger():
    """Returns the logger instance used in this module."""
    global _logger
    _logger = _logger or logging.getLogger(__name__)
    return _logger


# Exceptions
# ------------------------------------------------
class Timeout(TimeoutError):
    """
    Raised when the lock could not be acquired in *timeout*
    seconds.
    """

    def __init__(self, lock_file):
        """
        """
        #: The path of the file lock.
        self.lock_file = lock_file
        return None

    def __str__(self):
        temp = "The file lock '{}' could not be acquired."\
               .format(self.lock_file)
        return temp


# Classes
# ------------------------------------------------

# This is a helper class which is returned by :meth:`BaseFileLock.acquire`
# and wraps the lock to make sure __enter__ is not called twice when entering
# the with statement.
# If we would simply return *self*, the lock would be acquired again
# in the *__enter__* method of the BaseFileLock, but not released again
# automatically.
#
# :seealso: issue #37 (memory leak)
class _Acquire_ReturnProxy:

    def __init__(self, lock):
        self.lock = lock
        return None

    def __enter__(self):
        return self.lock

    def __exit__(self, exc_type, exc_value, traceback):
        self.lock.release()
        return None


class BaseFileLock:
    """
    Implements the base class of a file lock.
    """

    def __init__(self, lock_file, timeout = -1):
        """
        """
        # The path to the lock file.
        self._lock_file = lock_file

        # The file descriptor for the *_lock_file* as it is returned by the
        # os.open() function.
        # This file lock is only NOT None, if the object currently holds the
        # lock.
        self._lock_file_fd = None

        # The default timeout value.
        self.timeout = timeout

        # We use this lock primarily for the lock counter.
        self._thread_lock = threading.Lock()

        # The lock counter is used for implementing the nested locking
        # mechanism. Whenever the lock is acquired, the counter is increased and
        # the lock is only released, when this value is 0 again.
        self._lock_counter = 0
        return None

    @property
    def lock_file(self):
        """
        The path to the lock file.
        """
        return self._lock_file

    @property
    def timeout(self):
        """
        You can set a default timeout for the filelock. It will be used as
        fallback value in the acquire method, if no timeout value (*None*) is
        given.

        If you want to disable the timeout, set it to a negative value.

        A timeout of 0 means, that there is exactly one attempt to acquire the
        file lock.

        .. versionadded:: 2.0.0
        """
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        """
        """
        self._timeout = float(value)
        return None

    # Platform dependent locking
    # --------------------------------------------

    def _acquire(self):
        """
        Platform dependent. If the file lock could be
        acquired, self._lock_file_fd holds the file descriptor
        of the lock file.
        """
        raise NotImplementedError()

    def _release(self):
        """
        Releases the lock and sets self._lock_file_fd to None.
        """
        raise NotImplementedError()

    # Platform independent methods
    # --------------------------------------------

    @property
    def is_locked(self):
        """
        True, if the object holds the file lock.

        .. versionchanged:: 2.0.0

            This was previously a method and is now a property.
        """
        return self._lock_file_fd is not None

    def acquire(self, timeout=None, poll_intervall=0.05):
        """
        Acquires the file lock or fails with a :exc:`Timeout` error.

        .. code-block:: python

            # You can use this method in the context manager (recommended)
            with lock.acquire():
                pass

            # Or use an equivalent try-finally construct:
            lock.acquire()
            try:
                pass
            finally:
                lock.release()

        :arg float timeout:
            The maximum time waited for the file lock.
            If ``timeout < 0``, there is no timeout and this method will
            block until the lock could be acquired.
            If ``timeout`` is None, the default :attr:`~timeout` is used.

        :arg float poll_intervall:
            We check once in *poll_intervall* seconds if we can acquire the
            file lock.

        :raises Timeout:
            if the lock could not be acquired in *timeout* seconds.

        .. versionchanged:: 2.0.0

            This method returns now a *proxy* object instead of *self*,
            so that it can be used in a with statement without side effects.
        """
        # Use the default timeout, if no timeout is provided.
        if timeout is None:
            timeout = self.timeout

        # Increment the number right at the beginning.
        # We can still undo it, if something fails.
        with self._thread_lock:
            self._lock_counter += 1

        lock_id = id(self)
        lock_filename = self._lock_file
        start_time = time.time()
        try:
            while True:
                with self._thread_lock:
                    if not self.is_locked:
                        logger().debug('Attempting to acquire lock %s on %s', lock_id, lock_filename)
                        self._acquire()

                if self.is_locked:
                    logger().debug('Lock %s acquired on %s', lock_id, lock_filename)
                    break
                elif timeout >= 0 and time.time() - start_time > timeout:
                    logger().debug('Timeout on acquiring lock %s on %s', lock_id, lock_filename)
                    raise Timeout(self._lock_file)
                else:
                    logger().debug(
                        'Lock %s not acquired on %s, waiting %s seconds ...',
                        lock_id, lock_filename, poll_intervall
                    )
                    time.sleep(poll_intervall)
        except:
            # Something did go wrong, so decrement the counter.
            with self._thread_lock:
                self._lock_counter = max(0, self._lock_counter - 1)

            raise
        return _Acquire_ReturnProxy(lock = self)

    def release(self, force = False):
        """
        Releases the file lock.

        Please note, that the lock is only completly released, if the lock
        counter is 0.

        Also note, that the lock file itself is not automatically deleted.

        :arg bool force:
            If true, the lock counter is ignored and the lock is released in
            every case.
        """
        with self._thread_lock:

            if self.is_locked:
                self._lock_counter -= 1

                if self._lock_counter == 0 or force:
                    lock_id = id(self)
                    lock_filename = self._lock_file

                    logger().debug('Attempting to release lock %s on %s', lock_id, lock_filename)
                    self._release()
                    self._lock_counter = 0
                    logger().debug('Lock %s released on %s', lock_id, lock_filename)

        return None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        return None

    def __del__(self):
        self.release(force = True)
        return None


# Windows locking mechanism
# ~~~~~~~~~~~~~~~~~~~~~~~~~

class WindowsFileLock(BaseFileLock):
    """
    Uses the :func:`msvcrt.locking` function to hard lock the lock file on
    windows systems.
    """

    def _acquire(self):
        open_mode = os.O_RDWR | os.O_CREAT | os.O_TRUNC

        try:
            fd = os.open(self._lock_file, open_mode)
        except OSError:
            pass
        else:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except (IOError, OSError):
                os.close(fd)
            else:
                self._lock_file_fd = fd
        return None

    def _release(self):
        fd = self._lock_file_fd
        self._lock_file_fd = None
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        os.close(fd)

        try:
            os.remove(self._lock_file)
        # Probably another instance of the application
        # that acquired the file lock.
        except OSError:
            pass
        return None

# Unix locking mechanism
# ~~~~~~~~~~~~~~~~~~~~~~

class UnixFileLock(BaseFileLock):
    """
    Uses the :func:`fcntl.flock` to hard lock the lock file on unix systems.
    """

    def _acquire(self):
        open_mode = os.O_RDWR | os.O_CREAT | os.O_TRUNC
        fd = os.open(self._lock_file, open_mode)

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            os.close(fd)
        else:
            self._lock_file_fd = fd
        return None

    def _release(self):
        # Do not remove the lockfile:
        #
        #   https://github.com/benediktschmitt/py-filelock/issues/31
        #   https://stackoverflow.com/questions/17708885/flock-removing-locked-file-without-race-condition
        fd = self._lock_file_fd
        self._lock_file_fd = None
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        return None

# Soft lock
# ~~~~~~~~~

class SoftFileLock(BaseFileLock):
    """
    Simply watches the existence of the lock file.
    """

    def _acquire(self):
        open_mode = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_TRUNC
        try:
            fd = os.open(self._lock_file, open_mode)
        except (IOError, OSError):
            pass
        else:
            self._lock_file_fd = fd
        return None

    def _release(self):
        os.close(self._lock_file_fd)
        self._lock_file_fd = None

        try:
            os.remove(self._lock_file)
        # The file is already deleted and that's what we want.
        except OSError:
            pass
        return None


# Platform filelock
# ~~~~~~~~~~~~~~~~~

#: Alias for the lock, which should be used for the current platform. On
#: Windows, this is an alias for :class:`WindowsFileLock`, on Unix for
#: :class:`UnixFileLock` and otherwise for :class:`SoftFileLock`.
FileLock = None

if msvcrt:
    FileLock = WindowsFileLock
elif fcntl:
    FileLock = UnixFileLock
else:
    FileLock = SoftFileLock

    if warnings is not None:
        warnings.warn("only soft file lock is available")

# SIG # Begin Windows Authenticode signature block
# MIInNQYJKoZIhvcNAQcCoIInJjCCJyICAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCBeuwVj7jMwyGt1
# 86rPg9OTctUrGpDpgrzo4vhL7v6ihaCCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
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
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCCKKC5vbuXxQ+cbNx06RnsxsIxH+SRL
# sQarDsyQvbSYxDBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# AAJ1Fv2Y1fcQYBNUcDvXzbSnpCxUlw3/OtlDcMiJ2XldbZDjQCahZFcaxTKhQLaW
# CiJ6O1ETUf2EwAHSC/lzfl8jj/roLbdeDKZYoRthFLhz5L0M+J83tcZXaaB8sDQC
# wd3zM1QxDXT9rOVaKhLjH7H0h6WZ0ZOP+m98X/X48l9LxlZGUOgc85RbOtdWS6ol
# shO2T1cuk4j9DEExHYELcH8t+y7ZAUKSHZIbVyA7CMqFjcH87ZOcND7sxKKgVOU9
# T9gQvrNNzjoHEk5SOE3FK4y5uZf8hCSGIek3bpCa9OenmbnXxQCeyIbNtVgXKgnv
# D8XltWiFZvBXAzvSY6fX24WhgheUMIIXkAYKKwYBBAGCNwMDATGCF4Awghd8Bgkq
# hkiG9w0BBwKgghdtMIIXaQIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQgB1VCD5tk335EXDZ7tTlB1Tp6fWR21U0Loqdbhpfc5S4CBmnnXdXrNxgTMjAy
# NjA0MzAwMDUwNDguNjEzWjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
# BgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1p
# Y3Jvc29mdCBDb3Jwb3JhdGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2Eg
# T3BlcmF0aW9uczEnMCUGA1UECxMeblNoaWVsZCBUU1MgRVNOOkE0MDAtMDVFMC1E
# OTQ3MSUwIwYDVQQDExxNaWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNloIIR6jCC
# ByAwggUIoAMCAQICEzMAAAIo8KWH1/PIHkAAAQAAAigwDQYJKoZIhvcNAQELBQAw
# fDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1Jl
# ZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMd
# TWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwHhcNMjYwMjE5MTk0MDA2WhcN
# MjcwNTE3MTk0MDA2WjCByzELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2EgT3BlcmF0aW9uczEnMCUG
# A1UECxMeblNoaWVsZCBUU1MgRVNOOkE0MDAtMDVFMC1EOTQ3MSUwIwYDVQQDExxN
# aWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNlMIICIjANBgkqhkiG9w0BAQEFAAOC
# Ag8AMIICCgKCAgEAro725P7KnAkkXmWiXwrn9TcEXHO15J4ROsJC6H5DY9ZsRAIN
# +astsXBY4I2q7VbwNPVvEB3KcjKlUlzk8TRybJpNKj9ggy71ALpVoO2kuaATkaRF
# 9aM959Edpz6nh9CBytcycY8Wh1ttQG7mdGfsDN1mDc5AZXB5lXtN2Ru65ZNvIe9q
# +T+TBPBRqRZmFuR5e6bCm4CxH62AIrabbbG/rGbAVCPoTCpeLiyWKLSsmb9XsDiI
# pwX0VPEKLIr46H2gXs1H/TXVfohq1od9tVp0rCtwPyZehi7W0ll3CVlC4G8bqp6G
# zyvmJQd9e+EzFk4F+GFoxu6NDrc/6YxzQigWwe/PHcp4S3RmOgdPBPfuEhq0abLc
# uIiRzsnRwgOTOIucmEcLHbrfoJr8SKU/MjVyXIyQoNLzvJr/5xWPVsrb9qpgrQhR
# YrxlFqlNtP7FHkaKEGRokDiUJ9PeQo94rCLL0T/ClO4TfxAyPB1bG/zT8zBS70c5
# 60Z49Ezpw4jk1HJ2MJpPl36EtaMLJHAggsB52wtNA+fM/N8uyuWSQe+OYXJ+AhNp
# 0d3ukRrK+NsuarbejHc/7OzE5w0tlJlR1l9V/x2Xt1JV/II/7ety+dMSD6pEQgRH
# TNQAzVGkn6PTkIim/249XYmQhk3xA1AQS6KdZoZMCBfNn2qZVdm7rGflOJECAwEA
# AaOCAUkwggFFMB0GA1UdDgQWBBSqyaWM+PLc6Lr1ZAVbYQEhaUPdwzAfBgNVHSME
# GDAWgBSfpxVdAF5iXYP05dJlpxtTNRnpcjBfBgNVHR8EWDBWMFSgUqBQhk5odHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBUaW1l
# LVN0YW1wJTIwUENBJTIwMjAxMCgxKS5jcmwwbAYIKwYBBQUHAQEEYDBeMFwGCCsG
# AQUFBzAChlBodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01p
# Y3Jvc29mdCUyMFRpbWUtU3RhbXAlMjBQQ0ElMjAyMDEwKDEpLmNydDAMBgNVHRMB
# Af8EAjAAMBYGA1UdJQEB/wQMMAoGCCsGAQUFBwMIMA4GA1UdDwEB/wQEAwIHgDAN
# BgkqhkiG9w0BAQsFAAOCAgEAkOjXy5q0WoYFbYFoN/NxmktO3x8qHem4XFDjbdrX
# rfugWjbh9K+wAZFR4XjqcQXa1KzhGFRGiIovXSt3LmSzZqdYlAMf1W5jmWJe8c/r
# Ta4wlqq4NY0JqtKEQfIhOECacDYRj+u6GOYbmCFNA+JYQ6Goan4CiZ/9AZPvVCgz
# 8OV5VGJq3hZiZY/WEM3Dz3qfDMQV8Yf2OSO70HkWluUo7Yi0Di0ZN4IL62g7OUn+
# PTCVevwcMVwtq71HxBV+klA6KKiiBPTYFSEatEWbuzrdItCLPh7zz9IQeisDsTIN
# Ulijn07RaVqXaPDCb4Cgh5D6VxM4Kaz/qciB7ju4FUZUk7G2ARS4dsiHf4rTOLmC
# 9EftkkgQU6UkkbYaxrhJhJSOQQhzMczIP6Kh0j8GQCAJDNguMcYtEre6jLgPpvmc
# xWJH6BeNUKEiZ/h46oalmENJv0jvfypyUSSVMDHeU4jJ42fhPwyYlK8ubnYlskKb
# 349oUBSNHY4WoaAFw2s3hHIixdrhJ07q/VH43MDrp/6DGPlC37ZzotoyizK63ldP
# e2pM8/ycaZw4GCVP7YFO30H5YOyKoi/ftNu+vo6EB6NtZlXmOWA/Cof5FGmOiZvz
# kzPPBu3r08/6p0bpsaL04zErb6WwBzUYZkk3SD01d9gsrsQykv1eWuYsAPn/VYga
# PsIwggdxMIIFWaADAgECAhMzAAAAFcXna54Cm0mZAAAAAAAVMA0GCSqGSIb3DQEB
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
# BAsTHm5TaGllbGQgVFNTIEVTTjpBNDAwLTA1RTAtRDk0NzElMCMGA1UEAxMcTWlj
# cm9zb2Z0IFRpbWUtU3RhbXAgU2VydmljZaIjCgEBMAcGBSsOAwIaAxUAda25hZM0
# u6gCtTmr9PAFJ4WzSFKggYMwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDANBgkqhkiG9w0BAQsFAAIFAO2dD7YwIhgPMjAyNjA0MjkyMzE2MDZaGA8y
# MDI2MDQzMDIzMTYwNlowdDA6BgorBgEEAYRZCgQBMSwwKjAKAgUA7Z0PtgIBADAH
# AgEAAgIhAzAHAgEAAgITMDAKAgUA7Z5hNgIBADA2BgorBgEEAYRZCgQCMSgwJjAM
# BgorBgEEAYRZCgMCoAowCAIBAAIDB6EgoQowCAIBAAIDAYagMA0GCSqGSIb3DQEB
# CwUAA4IBAQAuPbBwQifoUHwwua0/KZk5uSD0BrCC+CTrHoG+KWU/vCRmqVVh4ZOc
# 1XkOHsg9Ns1j+NV8dkUTCDpqmnJzPA/ynmGSHjbVs4wqt2qium17r+fGWoHTyNqo
# WodGpx0THU6Ym1ynTVQ0QhFwkvcf0lpUu0j8mpgIiAyvN4p0fb7+Ec3wqLqEehg3
# wpbql3qzJ0mRiqIA3SDyC0owGgAdNRlVuNvxPLxjUxLVXh3ys84wOnC8k2nJ9FvB
# 57SU9YuVh7cchRsgY6EirvnUFgL0L11jfCSJVItMk13fE0apTe43hFlqIjgY0GhM
# Rs/8dg1Ht3fyjmCpBDvJ1YF7f55iKS9fMYIEDTCCBAkCAQEwgZMwfDELMAkGA1UE
# BhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAc
# BgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMdTWljcm9zb2Z0
# IFRpbWUtU3RhbXAgUENBIDIwMTACEzMAAAIo8KWH1/PIHkAAAQAAAigwDQYJYIZI
# AWUDBAIBBQCgggFKMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRABBDAvBgkqhkiG
# 9w0BCQQxIgQga8xb5JhWSpoWLTezJ8gLgqBYjinXrdxnBxOkDV16mI0wgfoGCyqG
# SIb3DQEJEAIvMYHqMIHnMIHkMIG9BCBVsYpGUWBjX+KBFWStXk+OR/txkN/6sVe+
# VcLgbfoi1zCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5n
# dG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9y
# YXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEwAhMz
# AAACKPClh9fzyB5AAAEAAAIoMCIEICA46Yr27Xg3dJE6qaupHcR6wLKra0ieTcjc
# CuUIt95eMA0GCSqGSIb3DQEBCwUABIICAF7wxDW0ECMLm2/lla7q37Lo0xPfzBXc
# lfsW0mnt7Ue3gp3baaFHGqnhSvjSInZokZTxGIpot0D2dPemx4bQ/+GO8+vlVDL9
# SPQwWmGNZX5ZnFSp1jSclX5QCzFESixV/KZTj8qDNeuX1mWyTvh2GQJubrKd3000
# FmG2IusbFEYjzWfOq96XRz/2K4g9QVfZqcx/gzJuq1Bx7a9GAFEY7Xw0YDUu9Lwb
# fNCLpYV1f7sXW3RWWcY8aayOyT10umyW2QS48c7uZSHwBW00EQhjNAZ8jHCq3/Wl
# Z9Z2YvNSjpTdGyjC5omgajm0mzV7Hd0zU64zRamX4IKXcAyt3IX7/BLt2a46RXxB
# kh9Scsa9vhgdX5Tq/dcE4tinA9EtG5WLx+Y9u3O5e9qkuC9rWN/DFQPUJQMAucRJ
# 0NoYxmVi2jsnIu7TZ/Fx8GV6panK9mIDWVPE1pQua+aIFAqRUvDGlR+tp9wOrL/y
# Va3SW2R46Upfa591alLfSaF3JLNNsvm3cnvcZGGvKqlaCFNKJ+3vUr9OShGIhZ8t
# TGbqk1gqJtr5rdyJYNz3Ne55IvEm7dGfvWJvvXn+y0ajmPhNJapcRAhi4vNAqBPn
# TaVGih2r2Gfxl2Q4KDl4nFxMMYnsiESt3L3mOTLzqVOnS1UFO2vPwHpUHQWAeAQG
# kRLQJoG1Z2wJ
# SIG # End Windows Authenticode signature block