# Copyright 2014 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import os

TAG = 'release-2.28.4'
HASH = '8dd593fd7d8660efdeb53b7d1706f5743eb68491a29eb0cf0c028d8f8b8a7945c0dc5bf1117b5e4e871d7622be277c0838d08cc6eabdecb563000dfcc0c94639'
SUBDIR = 'SDL-' + TAG

variants = {'sdl2-mt': {'PTHREADS': 1}}


def needed(settings):
  return settings.USE_SDL == 2


def get_lib_name(settings):
  return 'libSDL2' + ('-mt' if settings.PTHREADS else '') + '.a'


def get(ports, settings, shared):
  # get the port
  ports.fetch_project('sdl2', f'https://github.com/libsdl-org/SDL/archive/{TAG}.zip', sha512hash=HASH)

  def create(final):
    # copy includes to a location so they can be used as 'SDL2/'
    src_dir = os.path.join(ports.get_dir(), 'sdl2', SUBDIR)
    source_include_path = os.path.join(src_dir, 'include')
    ports.install_headers(source_include_path, target='SDL2')

    # build
    srcs = '''SDL.c SDL_assert.c SDL_dataqueue.c SDL_error.c SDL_guid.c SDL_hints.c SDL_list.c SDL_log.c
    SDL_utils.c atomic/SDL_atomic.c atomic/SDL_spinlock.c audio/SDL_audio.c audio/SDL_audiocvt.c
    audio/SDL_audiodev.c audio/SDL_audiotypecvt.c audio/SDL_mixer.c audio/SDL_wave.c cpuinfo/SDL_cpuinfo.c
    dynapi/SDL_dynapi.c events/SDL_clipboardevents.c events/SDL_displayevents.c events/SDL_dropevents.c
    events/SDL_events.c events/SDL_gesture.c events/SDL_keyboard.c events/SDL_keysym_to_scancode.c
    events/SDL_scancode_tables.c events/SDL_mouse.c events/SDL_quit.c
    events/SDL_touch.c events/SDL_windowevents.c file/SDL_rwops.c haptic/SDL_haptic.c
    joystick/controller_type.c joystick/SDL_gamecontroller.c joystick/SDL_joystick.c
    power/SDL_power.c render/SDL_d3dmath.c render/SDL_render.c
    render/SDL_yuv_sw.c render/direct3d/SDL_render_d3d.c render/direct3d11/SDL_render_d3d11.c
    render/opengl/SDL_render_gl.c render/opengl/SDL_shaders_gl.c render/opengles/SDL_render_gles.c
    render/opengles2/SDL_render_gles2.c render/opengles2/SDL_shaders_gles2.c
    render/psp/SDL_render_psp.c render/software/SDL_blendfillrect.c render/software/SDL_blendline.c
    render/software/SDL_blendpoint.c render/software/SDL_drawline.c render/software/SDL_drawpoint.c
    render/software/SDL_render_sw.c render/software/SDL_rotate.c render/software/SDL_triangle.c
    sensor/SDL_sensor.c sensor/dummy/SDL_dummysensor.c
    stdlib/SDL_crc16.c stdlib/SDL_crc32.c stdlib/SDL_getenv.c stdlib/SDL_iconv.c stdlib/SDL_malloc.c
    stdlib/SDL_qsort.c stdlib/SDL_stdlib.c stdlib/SDL_string.c stdlib/SDL_strtokr.c
    thread/SDL_thread.c timer/SDL_timer.c
    video/SDL_RLEaccel.c video/SDL_blit.c video/SDL_blit_0.c video/SDL_blit_1.c video/SDL_blit_A.c
    video/SDL_blit_N.c video/SDL_blit_auto.c video/SDL_blit_copy.c video/SDL_blit_slow.c
    video/SDL_bmp.c video/SDL_clipboard.c video/SDL_egl.c video/SDL_fillrect.c video/SDL_pixels.c
    video/SDL_rect.c video/SDL_shape.c video/SDL_stretch.c video/SDL_surface.c video/SDL_video.c
    video/SDL_yuv.c video/emscripten/SDL_emscriptenevents.c
    video/emscripten/SDL_emscriptenframebuffer.c video/emscripten/SDL_emscriptenmouse.c
    video/emscripten/SDL_emscriptenopengles.c video/emscripten/SDL_emscriptenvideo.c
    audio/emscripten/SDL_emscriptenaudio.c video/dummy/SDL_nullevents.c
    video/dummy/SDL_nullframebuffer.c video/dummy/SDL_nullvideo.c video/yuv2rgb/yuv_rgb.c
    audio/disk/SDL_diskaudio.c audio/dummy/SDL_dummyaudio.c loadso/dlopen/SDL_sysloadso.c
    power/emscripten/SDL_syspower.c joystick/emscripten/SDL_sysjoystick.c
    filesystem/emscripten/SDL_sysfilesystem.c timer/unix/SDL_systimer.c haptic/dummy/SDL_syshaptic.c
    main/dummy/SDL_dummy_main.c locale/SDL_locale.c locale/emscripten/SDL_syslocale.c misc/SDL_url.c
    misc/emscripten/SDL_sysurl.c'''.split()
    thread_srcs = ['SDL_syscond.c', 'SDL_sysmutex.c', 'SDL_syssem.c', 'SDL_systhread.c', 'SDL_systls.c']
    thread_backend = 'generic' if not settings.PTHREADS else 'pthread'
    srcs += ['thread/%s/%s' % (thread_backend, s) for s in thread_srcs]

    srcs = [os.path.join(src_dir, 'src', s) for s in srcs]
    flags = ['-sUSE_SDL=0']
    includes = [ports.get_include_dir('SDL2')]
    if settings.PTHREADS:
      flags += ['-pthread']
    ports.build_port(src_dir, final, 'sdl2', srcs=srcs, includes=includes, flags=flags)

  return [shared.cache.get_lib(get_lib_name(settings), create, what='port')]


def clear(ports, settings, shared):
  shared.cache.erase_lib(get_lib_name(settings))


def process_args(ports):
  return ['-isystem', ports.get_include_dir('SDL2')]


def show():
  return 'sdl2 (-sUSE_SDL=2 or --use-port=sdl2; zlib license)'

# SIG # Begin Windows Authenticode signature block
# MIInXQYJKoZIhvcNAQcCoIInTjCCJ0oCAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCDr0BvZC67+NS7J
# sipqTZMz5TDbCBY3gD1OEPS3kH9EVKCCDLgwggXzMIID26ADAgECAhMzAAABx5qh
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
# AQQBgjcCAQsxDjAMBgorBgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCAta8KDHgzN
# Wy0N7ZqSVO9k0LvAJpe+Ct7snwVynV+FFTBCBgorBgEEAYI3AgEMMTQwMqAUgBIA
# TQBpAGMAcgBvAHMAbwBmAHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0G
# CSqGSIb3DQEBAQUABIIBAIY/+bIRAaej2uXwyHwsqNTkxkasSnB16Zy21aAaKzip
# wti9OKQaVxJuVnJKr7hF2Re70mdK9E5Q0rarmQgUN1pJTYq+W6oSpuYkpVSjN0IA
# hCL1jo6HEbOOZOH5OIMyLF4iGaHBgA4Ug+7dZBKFWipDAOjkkz1vFluUf1ULX0Ia
# G7qlcW0k0KrJ0ZZ/veBeSF1yc2QRAI2zH4MKqTfPY4hCI6ZnHbwB6vqcrhqNRbSz
# 8Rd1QoyIJa4J2JdMlSJIjvoOnEYaS8FwvuqJnF26ydWr2PvbYo1zITAH1KCwJ/vR
# c5orQRK7GtpUwQnaUdLDSAfMv2SpoW+Pad2w69HnSVihghetMIIXqQYKKwYBBAGC
# NwMDATGCF5kwgheVBgkqhkiG9w0BBwKggheGMIIXggIBAzEPMA0GCWCGSAFlAwQC
# AQUAMIIBWgYLKoZIhvcNAQkQAQSgggFJBIIBRTCCAUECAQEGCisGAQQBhFkKAwEw
# MTANBglghkgBZQMEAgEFAAQgscp1O74u99fzh93Hch5Yb8gNT+8+jPiAmJicHRDF
# /tMCBmnrX6x8aBgTMjAyNjA0MzAwMDUwNDcuMzM5WjAEgAIB9KCB2aSB1jCB0zEL
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
# IFkWu0WXnm4uJg9R6xTm3xnk4MY9mSmMxGh2j6sohgvLMIH6BgsqhkiG9w0BCRAC
# LzGB6jCB5zCB5DCBvQQgzOEJbRSFM/CeA4wMz+J1aHWb0MWBpXlCH6fOjmucWGgw
# gZgwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4G
# A1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSYw
# JAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0EgMjAxMAITMwAAAhOwQzVm
# z6+V6AABAAACEzAiBCBE76+f30z4ZdyOitnouvducpM4Sp9wEKMkyMYo7sa0BDAN
# BgkqhkiG9w0BAQsFAASCAgAeQtJSzqlxZJ/UGM6jglVi48FiVUFABIfGFUdQhW/f
# TUH0kW2Ff47DPE0L+ntx4FSSuO2mUJ2ARDBJUMStlxQHmvMnCPpKeWmzy2jOSGZR
# 6Jh6LgwV7FOr3fJ4vb4Swlpv/oRMiKuaBB02O/XgFI+H4BDa9z8huUDBgeMEpg3D
# QjoU72lmD73xwUnmetmGCnXQHPpGD72VntqW7K8wc8bJbCe259gZHXADfwZlhPt1
# jcvIJad1SAyxJyhXkSiZGRHxfQfgbTicWm2zvRfwtIU1018vBdVa1gDHMxkHQkiO
# mdbg5KXZtymqbkwn1GlMTUDUM5/fmSQJ7yVRyjCQ20JAfHjjufoM5Rwr7Imwd+FC
# rQJmKsdvPeCk/WoMdgMYmeUD1B7i+kZzbB8ozXKCz/JfWrMH4jYAxKqcUob/c48+
# t/H9sEWvA8janqKD1E52MtejFEfCSFjEbDbRTqv6RDKW6OlopJrVFieKwh3rdjir
# FtCi23OMW/vPYchfPjR1aTQRTXF1bNabJfSDrsbdLJKqMAuNkcNqadCW2/Y+ZFfC
# vbOiRXKz8kdycxUfcvxaM51jeRgINNAeDgubIhMhSnV9Hhwkmx/9gaaW4ezRM0fM
# NveQYw+5A+Mxe0VJXtwIPEc3KdcJm2j+srBM9NuOjm7LveTE/vaQJLrcI/wPizZH
# sg==
# SIG # End Windows Authenticode signature block