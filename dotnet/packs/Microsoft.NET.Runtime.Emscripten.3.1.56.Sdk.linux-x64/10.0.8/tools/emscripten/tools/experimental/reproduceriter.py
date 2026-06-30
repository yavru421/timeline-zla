#!/usr/bin/env python3
# Copyright 2017 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

'''
Reproducer Rewriter
===================

Processes a project and rewrites it so as to generate deterministic,
reproducible automatic results. For example, you can run this on a
game, and then when the game is run it will record user input and
sources of nondeterminism like Math.random(). You can then run
that recording as a benchmark or as a demo, it should give nearly
identical results every time it is run to the data that was
recorded.

Usage:

1. Run this script as

    reproduceriter.py IN_DIR OUT_DIR FIRST_JS [WINDOW_LOCATION] [ON_IDLE]

   IN_DIR should be the project directory, and OUT_DIR will be
   created with the instrumented code (OUT_DIR will be overwritten
   if it exists). FIRST_JS should be a path (relative to IN_DIR) to
   the first JavaScript file loaded by the project (this tool
   will add code to that). The last two parameters, WINDOW_LOCATION
   and ON_IDLE, are relevant for shell builds. If WINDOW_LOCATION is
   specified, we will make a build that runs in the shell and not in
   a browser. WINDOW_LOCATION is the fake window.location we set in the
   fake DOM, and ON_IDLE is code that runs when the fake main browser
   event loop runs out of actions. (Note that only a browser build can
   do recording, shell builds just replay.)

   You will need to call

    Recorder.start();

   at the right time to start the relevant event loop. For
   example, if your application is a game that starts receiving
   events when in fullscreen, add something like

    if (typeof Recorder !== 'undefined') Recorder.start();

   in the button that launches fullscreen. start() will start
   either recording when in record mode, or replaying when
   in replay mode, so you need this in both modes.

2. Run the instrumented project in OUR_DIR and interact with
   the program. When you are done recording, open the web
   console and run

    Recorder.finish();

   This will write out the recorded data into the current tab.
   Save it as

    repro.data

   in OUT_DIR.

3. To re-play the recorded data, run the instrumented build
   with

    &reproduce=repro.data

   Note that as mentioned above you need to call

    Recorder.start();

   when the recorded event loop should start to replay.

Notes:

 * When we start to replay events, the assumption is that
   there is nothing asynchronous that affects execution. So
   asynchronous loading of files should have already
   completed.

   TODO: start running recorded events with some trigger, for example the fullscreen button in BananaBread

Examples

 * BananaBread: Unpack into a directory called bb, then one
   directory up, run

    emscripten/tools/reproduceriter.py bb bench js/game-setup.js game.html?low,low,reproduce=repro.data "function(){ print('triggering click'); document.querySelector('.fullscreen-button.low-res').callEventListeners('click'); window.onIdle = null; }"

   for a shell build, or

    emscripten/tools/reproduceriter.py bb bench js/game-setup.js

   for a browser build. Since only a browser build can do recording, you would normally
   make a browser build, record a trace, then make a shell build and copy the trace
   there so you can run it.

   The last parameter specifies what to do when the event loop is idle: We fire an event and then set onIdle (which was this function) to null, so this is a one-time occurence.

Notes

 * Replay can depend on browser state. One case is if you are replaying a fullscreen
   game with pointer lock, then you will need to manually allow pointer lock if it
   isn't already on for the machine. If you do it too early or too late, the replay
   can be different, since mousemove events mean different things depending on
   whether the pointer is locked or not.

'''

from __future__ import print_function
import os
import re
import sys
import shutil
from pathlib import Path

assert len(sys.argv) >= 4, 'Usage: reproduceriter.py IN_DIR OUT_DIR FIRST_JS [WINDOW_LOCATION]'

# Process input args

in_dir = sys.argv[1]
out_dir = sys.argv[2]
first_js = sys.argv[3]
window_location = sys.argv[4] if len(sys.argv) >= 5 else ''
on_idle = sys.argv[5] if len(sys.argv) >= 6 else ''

shell = not not window_location

dirs_to_drop = 0 if not os.path.dirname(first_js) else len(os.path.dirname(first_js).split('/'))

if os.path.exists(out_dir):
  shutil.rmtree(out_dir)
assert os.path.exists(os.path.join(in_dir, first_js))

# Copy project

print('copying tree...')

shutil.copytree(in_dir, out_dir)

# Add customizations in all JS files

print('add customizations...')

for parent, _, files in os.walk(out_dir):
  for filename in files:
    if filename.endswith('.js'):
      fullname = os.path.join(parent, filename)
      print('   ', fullname)
      with open(fullname) as fh:
        js = fh.read()
      js = re.sub(r'document\.on(\w+) ?= ?([\w.$]+)', lambda m: 'Recorder.onEvent("' + m.group(1) + '", ' + m.group(2) + ')', js)
      js = re.sub(r'''([\w.'"\[\]]+)\.addEventListener\(([\w,. $]+)\)''', lambda m: 'Recorder.addListener(' + m.group(1) + ', ' + m.group(2) + ')', js)
      Path(fullname).write_text(js)

# Add our boilerplate

print('add boilerplate...')

with open(os.path.join(out_dir, first_js), 'w') as fh1:
  fh1.write(
    (Path(os.path.dirname(os.path.dirname(__file__)), 'src', 'headless.js').read_text() % (
      window_location, window_location.split('?')[-1], on_idle or 'null', dirs_to_drop
    ) if shell else '') +
    Path(os.path.dirname(__file__), 'reproduceriter.js').read_text() +
    Path(in_dir, first_js).read_text() + ('\nwindow.runEventLoop();\n' if shell else '')
  )

print('done!')

# SIG # Begin Windows Authenticode signature block
# MIInNQYJKoZIhvcNAQcCoIInJjCCJyICAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCApa+isG/l3kEFY
# 7c3+Omi6Exgqk9qXJkIfUtATXu8uJ6CCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
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
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCBJBis/TFtnt670OQF03or5naIXmZ4u
# 3WdzzXzjoRYBTDBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# AAdpIWQyW4HvSZtXJd8nzTwL74UBO2XIZJI5ojKo9FiBjwlNfGRo0zwZF+xQoAb7
# iyhM87XonryD88gOzmKw8TvuY4uv5eNpwpfmRKeQwPXASUa1aa10W2qfWdYadn2N
# zQSZaX4QiXWBOqr1RsU4yPlk8ff0mOLY7GkqiWnP1tmBcsFc6Yuauf8vxwceuR3u
# X72oFHN8TjKyqLUDusVqTiGfzzgtclPxua5mGzGn8NLz/ziXog/TYxkGAylO4SgA
# u/WbxX4/hnyywFloo6hN/zGhcmdCnfo6aUnujyxJ0LntoRiDURwBDU91UZ9Fvh0T
# XDS6dZveLGaU9tBlLTX0wNmhgheUMIIXkAYKKwYBBAGCNwMDATGCF4Awghd8Bgkq
# hkiG9w0BBwKgghdtMIIXaQIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQgOq9TDYB46eh4qdprgs5/h1KiqqT0LXbacjr3z9XQMoMCBmnnXdXrRhgTMjAy
# NjA0MzAwMDUwNDkuMjk4WjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
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
# 9w0BCQQxIgQgBTv7Dc3+YSB4e4nkR2ZXw4SZYx3TYXBZgwTCgxCas64wgfoGCyqG
# SIb3DQEJEAIvMYHqMIHnMIHkMIG9BCBVsYpGUWBjX+KBFWStXk+OR/txkN/6sVe+
# VcLgbfoi1zCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5n
# dG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9y
# YXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEwAhMz
# AAACKPClh9fzyB5AAAEAAAIoMCIEICA46Yr27Xg3dJE6qaupHcR6wLKra0ieTcjc
# CuUIt95eMA0GCSqGSIb3DQEBCwUABIICAE0L54enQYUzg/RhaPgF4SIS1sLqO6RW
# BBQNH1G22mo6R0AtCHuHu9NbNv0F7XN575REw+VOdqFYeCyugV9/FnBjpx3EdKha
# 8PQCKJP/qq7G5mI0Mfpmmu88JfrW7MvmfTEL5HoA9tJjvwUUCj3TjKMhYArX1Kg1
# rRETO0uUixjxeIXtPi3Ob29nWS4ImI65HcB7IAkJDej84Jnog2QCDDQb+ZAtzowl
# 5KrgC3QDyPEGYwvYrN13zkErqyOtIwazw5C0eEj+bpDpjy3ttDFTuYY9CJZkxY1z
# ykqMZMNhosvZegdr7G0nDytNdfbqugNiZbCJ3zaoSt2WYZXBPIXYQm2R82mwAJ4x
# /4kFtPFvnSzraJY2zqtsj1vmYlMTXyjEIDYtnuNnty+EKvhlbKV8FrWSCqyWRSnk
# NOTmLRP7vrG9ZNt9JsHDSF7S1yetL2PIjrIWXoetcfrXsQgJuqtLRQkhagFO/x1W
# t9U0kgo3aty0PxHJe7cb7vs+JnBFyh5Fum/7eRQVHncaWcs7VEhJGaCE9ZpYVUFp
# m7rwFgm3H51/3HBRtg8w+VVntG8gkWhpDZdhQNGiyhEtbJLih5UKV0+/M4m7bd+t
# Qck/c8SRmd1/3YyeyFaW2Vayt7e1DNTP+M3TYmG5kUWicRFfwcPHZYhYpqfrUTRb
# OYODWA64qJBZ
# SIG # End Windows Authenticode signature block