# Copyright 2015 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import os

TAG = '1.6.39'
HASH = '19851afffbe2ffde62d918f7e9017dec778a7ce9c60c75cdc65072f086e6cdc9d9895eb7b207535a84cb5f4ead77ebc2aa9d80025f153662903023e1f7ab9bae'

deps = ['zlib']
variants = {
  'libpng-mt': {'PTHREADS': 1},
  'libpng-wasm-sjlj': {'SUPPORT_LONGJMP': 'wasm'},
  'libpng-mt-wasm-sjlj': {'PTHREADS': 1, 'SUPPORT_LONGJMP': 'wasm'},
}


def needed(settings):
  return settings.USE_LIBPNG


def get_lib_name(settings):
  suffix = ''
  if settings.PTHREADS:
    suffix += '-mt'
  if settings.SUPPORT_LONGJMP == 'wasm':
    suffix += '-wasm-sjlj'
  return f'libpng{suffix}.a'


def get(ports, settings, shared):
  # This is an emscripten-hosted mirror of the libpng repo from Sourceforge.
  ports.fetch_project('libpng', f'https://storage.googleapis.com/webassembly/emscripten-ports/libpng-{TAG}.tar.gz', sha512hash=HASH)

  def create(final):
    source_path = os.path.join(ports.get_dir(), 'libpng', 'libpng-' + TAG)
    ports.write_file(os.path.join(source_path, 'pnglibconf.h'), pnglibconf_h)
    ports.install_headers(source_path)

    flags = ['-sUSE_ZLIB']
    if settings.PTHREADS:
      flags += ['-pthread']
    if settings.SUPPORT_LONGJMP == 'wasm':
      flags.append('-sSUPPORT_LONGJMP=wasm')

    ports.build_port(source_path, final, 'libpng', flags=flags, exclude_files=['pngtest'], exclude_dirs=['scripts', 'contrib'])

  return [shared.cache.get_lib(get_lib_name(settings), create, what='port')]


def clear(ports, settings, shared):
  shared.cache.erase_lib(get_lib_name(settings))


def process_dependencies(settings):
  settings.USE_ZLIB = 1


def show():
  return 'libpng (-sUSE_LIBPNG or --use-port=libpng; zlib license)'


pnglibconf_h = r'''/* pnglibconf.h - library build configuration */

/* libpng version 1.6.39 */

/* Copyright (c) 2018-2022 Cosmin Truta */
/* Copyright (c) 1998-2002,2004,2006-2018 Glenn Randers-Pehrson */

/* This code is released under the libpng license. */
/* For conditions of distribution and use, see the disclaimer */
/* and license in png.h */

/* EMSCRIPTEN: png.h is provided in the downloaded archive that this script */
/*             fetches. The license portion of that is: */

/*
 * Copyright (c) 2018-2019 Cosmin Truta
 * Copyright (c) 1998-2002,2004,2006-2018 Glenn Randers-Pehrson
 * Copyright (c) 1996-1997 Andreas Dilger
 * Copyright (c) 1995-1996 Guy Eric Schalnat, Group 42, Inc.
 *
 * This code is released under the libpng license. (See LICENSE, below.)
 */

/* EMSCRIPTEN: The contents of LICENSE are: */

/*
COPYRIGHT NOTICE, DISCLAIMER, and LICENSE
=========================================

PNG Reference Library License version 2
---------------------------------------

 * Copyright (c) 1995-2019 The PNG Reference Library Authors.
 * Copyright (c) 2018-2019 Cosmin Truta.
 * Copyright (c) 2000-2002, 2004, 2006-2018 Glenn Randers-Pehrson.
 * Copyright (c) 1996-1997 Andreas Dilger.
 * Copyright (c) 1995-1996 Guy Eric Schalnat, Group 42, Inc.

The software is supplied "as is", without warranty of any kind,
express or implied, including, without limitation, the warranties
of merchantability, fitness for a particular purpose, title, and
non-infringement.  In no event shall the Copyright owners, or
anyone distributing the software, be liable for any damages or
other liability, whether in contract, tort or otherwise, arising
from, out of, or in connection with the software, or the use or
other dealings in the software, even if advised of the possibility
of such damage.

Permission is hereby granted to use, copy, modify, and distribute
this software, or portions hereof, for any purpose, without fee,
subject to the following restrictions:

 1. The origin of this software must not be misrepresented; you
    must not claim that you wrote the original software.  If you
    use this software in a product, an acknowledgment in the product
    documentation would be appreciated, but is not required.

 2. Altered source versions must be plainly marked as such, and must
    not be misrepresented as being the original software.

 3. This Copyright notice may not be removed or altered from any
    source or altered source distribution.


PNG Reference Library License version 1 (for libpng 0.5 through 1.6.35)
-----------------------------------------------------------------------

libpng versions 1.0.7, July 1, 2000, through 1.6.35, July 15, 2018 are
Copyright (c) 2000-2002, 2004, 2006-2018 Glenn Randers-Pehrson, are
derived from libpng-1.0.6, and are distributed according to the same
disclaimer and license as libpng-1.0.6 with the following individuals
added to the list of Contributing Authors:

    Simon-Pierre Cadieux
    Eric S. Raymond
    Mans Rullgard
    Cosmin Truta
    Gilles Vollant
    James Yu
    Mandar Sahastrabuddhe
    Google Inc.
    Vadim Barkov

and with the following additions to the disclaimer:

    There is no warranty against interference with your enjoyment of
    the library or against infringement.  There is no warranty that our
    efforts or the library will fulfill any of your particular purposes
    or needs.  This library is provided with all faults, and the entire
    risk of satisfactory quality, performance, accuracy, and effort is
    with the user.

Some files in the "contrib" directory and some configure-generated
files that are distributed with libpng have other copyright owners, and
are released under other open source licenses.

libpng versions 0.97, January 1998, through 1.0.6, March 20, 2000, are
Copyright (c) 1998-2000 Glenn Randers-Pehrson, are derived from
libpng-0.96, and are distributed according to the same disclaimer and
license as libpng-0.96, with the following individuals added to the
list of Contributing Authors:

    Tom Lane
    Glenn Randers-Pehrson
    Willem van Schaik

libpng versions 0.89, June 1996, through 0.96, May 1997, are
Copyright (c) 1996-1997 Andreas Dilger, are derived from libpng-0.88,
and are distributed according to the same disclaimer and license as
libpng-0.88, with the following individuals added to the list of
Contributing Authors:

    John Bowler
    Kevin Bracey
    Sam Bushell
    Magnus Holmgren
    Greg Roelofs
    Tom Tanner

Some files in the "scripts" directory have other copyright owners,
but are released under this license.

libpng versions 0.5, May 1995, through 0.88, January 1996, are
Copyright (c) 1995-1996 Guy Eric Schalnat, Group 42, Inc.

For the purposes of this copyright and license, "Contributing Authors"
is defined as the following set of individuals:

    Andreas Dilger
    Dave Martindale
    Guy Eric Schalnat
    Paul Schmidt
    Tim Wegner

The PNG Reference Library is supplied "AS IS".  The Contributing
Authors and Group 42, Inc. disclaim all warranties, expressed or
implied, including, without limitation, the warranties of
merchantability and of fitness for any purpose.  The Contributing
Authors and Group 42, Inc. assume no liability for direct, indirect,
incidental, special, exemplary, or consequential damages, which may
result from the use of the PNG Reference Library, even if advised of
the possibility of such damage.

Permission is hereby granted to use, copy, modify, and distribute this
source code, or portions hereof, for any purpose, without fee, subject
to the following restrictions:

 1. The origin of this source code must not be misrepresented.

 2. Altered versions must be plainly marked as such and must not
    be misrepresented as being the original source.

 3. This Copyright notice may not be removed or altered from any
    source or altered source distribution.

The Contributing Authors and Group 42, Inc. specifically permit,
without fee, and encourage the use of this source code as a component
to supporting the PNG file format in commercial products.  If you use
this source code in a product, acknowledgment is not required but would
be appreciated.
*/

/* pnglibconf.h */
/* Machine generated file: DO NOT EDIT */
/* Derived from: scripts/pnglibconf.dfa */
#ifndef PNGLCONF_H
#define PNGLCONF_H
/* options */
#define PNG_16BIT_SUPPORTED
#define PNG_ALIGNED_MEMORY_SUPPORTED
/*#undef PNG_ARM_NEON_API_SUPPORTED*/
/*#undef PNG_ARM_NEON_CHECK_SUPPORTED*/
#define PNG_BENIGN_ERRORS_SUPPORTED
#define PNG_BENIGN_READ_ERRORS_SUPPORTED
/*#undef PNG_BENIGN_WRITE_ERRORS_SUPPORTED*/
#define PNG_BUILD_GRAYSCALE_PALETTE_SUPPORTED
#define PNG_CHECK_FOR_INVALID_INDEX_SUPPORTED
#define PNG_COLORSPACE_SUPPORTED
#define PNG_CONSOLE_IO_SUPPORTED
#define PNG_CONVERT_tIME_SUPPORTED
#define PNG_EASY_ACCESS_SUPPORTED
/*#undef PNG_ERROR_NUMBERS_SUPPORTED*/
#define PNG_ERROR_TEXT_SUPPORTED
#define PNG_FIXED_POINT_SUPPORTED
#define PNG_FLOATING_ARITHMETIC_SUPPORTED
#define PNG_FLOATING_POINT_SUPPORTED
#define PNG_FORMAT_AFIRST_SUPPORTED
#define PNG_FORMAT_BGR_SUPPORTED
#define PNG_GAMMA_SUPPORTED
#define PNG_GET_PALETTE_MAX_SUPPORTED
#define PNG_HANDLE_AS_UNKNOWN_SUPPORTED
#define PNG_INCH_CONVERSIONS_SUPPORTED
#define PNG_INFO_IMAGE_SUPPORTED
#define PNG_IO_STATE_SUPPORTED
#define PNG_MNG_FEATURES_SUPPORTED
#define PNG_POINTER_INDEXING_SUPPORTED
/*#undef PNG_POWERPC_VSX_API_SUPPORTED*/
/*#undef PNG_POWERPC_VSX_CHECK_SUPPORTED*/
#define PNG_PROGRESSIVE_READ_SUPPORTED
#define PNG_READ_16BIT_SUPPORTED
#define PNG_READ_ALPHA_MODE_SUPPORTED
#define PNG_READ_ANCILLARY_CHUNKS_SUPPORTED
#define PNG_READ_BACKGROUND_SUPPORTED
#define PNG_READ_BGR_SUPPORTED
#define PNG_READ_CHECK_FOR_INVALID_INDEX_SUPPORTED
#define PNG_READ_COMPOSITE_NODIV_SUPPORTED
#define PNG_READ_COMPRESSED_TEXT_SUPPORTED
#define PNG_READ_EXPAND_16_SUPPORTED
#define PNG_READ_EXPAND_SUPPORTED
#define PNG_READ_FILLER_SUPPORTED
#define PNG_READ_GAMMA_SUPPORTED
#define PNG_READ_GET_PALETTE_MAX_SUPPORTED
#define PNG_READ_GRAY_TO_RGB_SUPPORTED
#define PNG_READ_INTERLACING_SUPPORTED
#define PNG_READ_INT_FUNCTIONS_SUPPORTED
#define PNG_READ_INVERT_ALPHA_SUPPORTED
#define PNG_READ_INVERT_SUPPORTED
#define PNG_READ_OPT_PLTE_SUPPORTED
#define PNG_READ_PACKSWAP_SUPPORTED
#define PNG_READ_PACK_SUPPORTED
#define PNG_READ_QUANTIZE_SUPPORTED
#define PNG_READ_RGB_TO_GRAY_SUPPORTED
#define PNG_READ_SCALE_16_TO_8_SUPPORTED
#define PNG_READ_SHIFT_SUPPORTED
#define PNG_READ_STRIP_16_TO_8_SUPPORTED
#define PNG_READ_STRIP_ALPHA_SUPPORTED
#define PNG_READ_SUPPORTED
#define PNG_READ_SWAP_ALPHA_SUPPORTED
#define PNG_READ_SWAP_SUPPORTED
#define PNG_READ_TEXT_SUPPORTED
#define PNG_READ_TRANSFORMS_SUPPORTED
#define PNG_READ_UNKNOWN_CHUNKS_SUPPORTED
#define PNG_READ_USER_CHUNKS_SUPPORTED
#define PNG_READ_USER_TRANSFORM_SUPPORTED
#define PNG_READ_bKGD_SUPPORTED
#define PNG_READ_cHRM_SUPPORTED
#define PNG_READ_eXIf_SUPPORTED
#define PNG_READ_gAMA_SUPPORTED
#define PNG_READ_hIST_SUPPORTED
#define PNG_READ_iCCP_SUPPORTED
#define PNG_READ_iTXt_SUPPORTED
#define PNG_READ_oFFs_SUPPORTED
#define PNG_READ_pCAL_SUPPORTED
#define PNG_READ_pHYs_SUPPORTED
#define PNG_READ_sBIT_SUPPORTED
#define PNG_READ_sCAL_SUPPORTED
#define PNG_READ_sPLT_SUPPORTED
#define PNG_READ_sRGB_SUPPORTED
#define PNG_READ_tEXt_SUPPORTED
#define PNG_READ_tIME_SUPPORTED
#define PNG_READ_tRNS_SUPPORTED
#define PNG_READ_zTXt_SUPPORTED
#define PNG_SAVE_INT_32_SUPPORTED
#define PNG_SAVE_UNKNOWN_CHUNKS_SUPPORTED
#define PNG_SEQUENTIAL_READ_SUPPORTED
#define PNG_SETJMP_SUPPORTED
#define PNG_SET_OPTION_SUPPORTED
#define PNG_SET_UNKNOWN_CHUNKS_SUPPORTED
#define PNG_SET_USER_LIMITS_SUPPORTED
#define PNG_SIMPLIFIED_READ_AFIRST_SUPPORTED
#define PNG_SIMPLIFIED_READ_BGR_SUPPORTED
#define PNG_SIMPLIFIED_READ_SUPPORTED
#define PNG_SIMPLIFIED_WRITE_AFIRST_SUPPORTED
#define PNG_SIMPLIFIED_WRITE_BGR_SUPPORTED
#define PNG_SIMPLIFIED_WRITE_STDIO_SUPPORTED
#define PNG_SIMPLIFIED_WRITE_SUPPORTED
#define PNG_STDIO_SUPPORTED
#define PNG_STORE_UNKNOWN_CHUNKS_SUPPORTED
#define PNG_TEXT_SUPPORTED
#define PNG_TIME_RFC1123_SUPPORTED
#define PNG_UNKNOWN_CHUNKS_SUPPORTED
#define PNG_USER_CHUNKS_SUPPORTED
#define PNG_USER_LIMITS_SUPPORTED
#define PNG_USER_MEM_SUPPORTED
#define PNG_USER_TRANSFORM_INFO_SUPPORTED
#define PNG_USER_TRANSFORM_PTR_SUPPORTED
#undef PNG_WARNINGS_SUPPORTED
#define PNG_WRITE_16BIT_SUPPORTED
#define PNG_WRITE_ANCILLARY_CHUNKS_SUPPORTED
#define PNG_WRITE_BGR_SUPPORTED
#define PNG_WRITE_CHECK_FOR_INVALID_INDEX_SUPPORTED
#define PNG_WRITE_COMPRESSED_TEXT_SUPPORTED
#define PNG_WRITE_CUSTOMIZE_COMPRESSION_SUPPORTED
#define PNG_WRITE_CUSTOMIZE_ZTXT_COMPRESSION_SUPPORTED
#define PNG_WRITE_FILLER_SUPPORTED
#define PNG_WRITE_FILTER_SUPPORTED
#define PNG_WRITE_FLUSH_SUPPORTED
#define PNG_WRITE_GET_PALETTE_MAX_SUPPORTED
#define PNG_WRITE_INTERLACING_SUPPORTED
#define PNG_WRITE_INT_FUNCTIONS_SUPPORTED
#define PNG_WRITE_INVERT_ALPHA_SUPPORTED
#define PNG_WRITE_INVERT_SUPPORTED
#define PNG_WRITE_OPTIMIZE_CMF_SUPPORTED
#define PNG_WRITE_PACKSWAP_SUPPORTED
#define PNG_WRITE_PACK_SUPPORTED
#define PNG_WRITE_SHIFT_SUPPORTED
#define PNG_WRITE_SUPPORTED
#define PNG_WRITE_SWAP_ALPHA_SUPPORTED
#define PNG_WRITE_SWAP_SUPPORTED
#define PNG_WRITE_TEXT_SUPPORTED
#define PNG_WRITE_TRANSFORMS_SUPPORTED
#define PNG_WRITE_UNKNOWN_CHUNKS_SUPPORTED
#define PNG_WRITE_USER_TRANSFORM_SUPPORTED
#define PNG_WRITE_WEIGHTED_FILTER_SUPPORTED
#define PNG_WRITE_bKGD_SUPPORTED
#define PNG_WRITE_cHRM_SUPPORTED
#define PNG_WRITE_eXIf_SUPPORTED
#define PNG_WRITE_gAMA_SUPPORTED
#define PNG_WRITE_hIST_SUPPORTED
#define PNG_WRITE_iCCP_SUPPORTED
#define PNG_WRITE_iTXt_SUPPORTED
#define PNG_WRITE_oFFs_SUPPORTED
#define PNG_WRITE_pCAL_SUPPORTED
#define PNG_WRITE_pHYs_SUPPORTED
#define PNG_WRITE_sBIT_SUPPORTED
#define PNG_WRITE_sCAL_SUPPORTED
#define PNG_WRITE_sPLT_SUPPORTED
#define PNG_WRITE_sRGB_SUPPORTED
#define PNG_WRITE_tEXt_SUPPORTED
#define PNG_WRITE_tIME_SUPPORTED
#define PNG_WRITE_tRNS_SUPPORTED
#define PNG_WRITE_zTXt_SUPPORTED
#define PNG_bKGD_SUPPORTED
#define PNG_cHRM_SUPPORTED
#define PNG_eXIf_SUPPORTED
#define PNG_gAMA_SUPPORTED
#define PNG_hIST_SUPPORTED
#define PNG_iCCP_SUPPORTED
#define PNG_iTXt_SUPPORTED
#define PNG_oFFs_SUPPORTED
#define PNG_pCAL_SUPPORTED
#define PNG_pHYs_SUPPORTED
#define PNG_sBIT_SUPPORTED
#define PNG_sCAL_SUPPORTED
#define PNG_sPLT_SUPPORTED
#define PNG_sRGB_SUPPORTED
#define PNG_tEXt_SUPPORTED
#define PNG_tIME_SUPPORTED
#define PNG_tRNS_SUPPORTED
#define PNG_zTXt_SUPPORTED
/* end of options */
/* settings */
#define PNG_API_RULE 0
#define PNG_DEFAULT_READ_MACROS 1
#define PNG_GAMMA_THRESHOLD_FIXED 5000
#define PNG_IDAT_READ_SIZE PNG_ZBUF_SIZE
#define PNG_INFLATE_BUF_SIZE 1024
#define PNG_LINKAGE_API extern
#define PNG_LINKAGE_CALLBACK extern
#define PNG_LINKAGE_DATA extern
#define PNG_LINKAGE_FUNCTION extern
#define PNG_MAX_GAMMA_8 11
#define PNG_QUANTIZE_BLUE_BITS 5
#define PNG_QUANTIZE_GREEN_BITS 5
#define PNG_QUANTIZE_RED_BITS 5
#define PNG_TEXT_Z_DEFAULT_COMPRESSION (-1)
#define PNG_TEXT_Z_DEFAULT_STRATEGY 0
#define PNG_USER_CHUNK_CACHE_MAX 1000
#define PNG_USER_CHUNK_MALLOC_MAX 8000000
#define PNG_USER_HEIGHT_MAX 1000000
#define PNG_USER_WIDTH_MAX 1000000
#define PNG_ZBUF_SIZE 8192
#define PNG_ZLIB_VERNUM 0 /* unknown */
#define PNG_Z_DEFAULT_COMPRESSION (-1)
#define PNG_Z_DEFAULT_NOFILTER_STRATEGY 0
#define PNG_Z_DEFAULT_STRATEGY 1
#define PNG_sCAL_PRECISION 5
#define PNG_sRGB_PROFILE_CHECKS 2
/* end of settings */
#endif /* PNGLCONF_H */
'''

# SIG # Begin Windows Authenticode signature block
# MIInOAYJKoZIhvcNAQcCoIInKTCCJyUCAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCBxs/pOXvQ0rC+4
# C7S1d8lbq7eWCEP1k4ZONGr9BEfphaCCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
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
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCBvhJYl+LNhHCSKRrSsNVEmlVc/n0ss
# GJswh597fb6yKjBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# AFdu18nzGlf5LrMY/9cI34vhQk/mq4eIZ88nNuWNtWCCRuSULprZ7AhYY2taykXK
# S0ZBEO2MkfJgTyYTFUsehc3JA4we+PpB3ZgM3cejPg/yvvRwWr6dw5NYKOpRn7Dr
# LGl8bDi+oYkSespSvSqM7QcHuj8/qk688McP5EEfraR4p+cFJP1SSHtmG8LLoS7Z
# e0f5tdwW/vfgsTXhvNtbvPKNZ4VQIZwkxXoGyFyynsMbyF1QXO3J6hxulN/pS3mE
# tzogd+0gUISBcBmp6ymZNFMB7Q5aGuI7CA2Lr59Vf2LtyhInvKDSa+7DECvLlrB1
# lVhk5l9hNd3cRm1HRkxOXTOhgheXMIIXkwYKKwYBBAGCNwMDATGCF4Mwghd/Bgkq
# hkiG9w0BBwKgghdwMIIXbAIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQgsCmm6vEA8Ce5Ks8+1OCGP5+P4ss6JLGgnnAX0eoeI+sCBmnnoCJoMBgTMjAy
# NjA0MzAwMDUwNDcuMzg3WjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
# BgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1p
# Y3Jvc29mdCBDb3Jwb3JhdGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2Eg
# T3BlcmF0aW9uczEnMCUGA1UECxMeblNoaWVsZCBUU1MgRVNOOjdGMDAtMDVFMC1E
# OTQ3MSUwIwYDVQQDExxNaWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNloIIR7TCC
# ByAwggUIoAMCAQICEzMAAAIeo6ykbjlvfEkAAQAAAh4wDQYJKoZIhvcNAQELBQAw
# fDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1Jl
# ZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMd
# TWljcm9zb2Z0IFRpbWUtU3RhbXAgUENBIDIwMTAwHhcNMjYwMjE5MTkzOTQ5WhcN
# MjcwNTE3MTkzOTQ5WjCByzELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0
# b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3Jh
# dGlvbjElMCMGA1UECxMcTWljcm9zb2Z0IEFtZXJpY2EgT3BlcmF0aW9uczEnMCUG
# A1UECxMeblNoaWVsZCBUU1MgRVNOOjdGMDAtMDVFMC1EOTQ3MSUwIwYDVQQDExxN
# aWNyb3NvZnQgVGltZS1TdGFtcCBTZXJ2aWNlMIICIjANBgkqhkiG9w0BAQEFAAOC
# Ag8AMIICCgKCAgEApdE47Ww8LEexXvGnOqJebNc4bU6ndgFqXIUIS6fRuZpkjNtz
# eX8kBgkNQ9OqzgNz4Fyhfu+r17zgrNlbC79aMI+JhxMhKoqvBiecgvv0DWEaWTwP
# HuzoHpMwzukv+L8v40zGG6d64bhYiigs01jkLXRXBfg9JN+vSO6ZvxNO0sjTBpLj
# XeZY+UifdVKhbmX4zAenENsIe+5rYkVFXY+d8o3Tao/hkJfmGs9vQY685+1NZZ/i
# aS5Z29MXRpmaCDymW8AVXFrci+LsoTC+0kk5ojn1l1PoPsjZdAnaCxi/C7VhxIvB
# bLkz3knUqpnjK7y2hJom01U0uL0EGPDT52+riOcuojVfbwRXJvC1P5Q04xk6j2u1
# AU+IHX+SZt8GK3whWeD/4+TKKk9CTjXGudI7eExiPdEooV2gxGKpNt0tCCWd1JFK
# bpA0U4yu9dwSMpH38cgajHkKnztM71n1Mewa5lKboEHMPffg8S5doH/rkBKUZp5W
# 61SfXb1vXbOH6hDzdoxtEMBdTwUoJTXFdUqamSorUIARksLv/NgCs7aAh8GER0Tc
# M8E1Xv9SjU75qgHeFIHrOMsDh9NoWmoE/MGGPDnVnYyp95NOdsPpJnNFAtBfolV0
# xmSDMb6PYgWUKF3oc0bVif1TrSrwskt3LCsze60rVicI0ls+nbTn9JfsrS0CAwEA
# AaOCAUkwggFFMB0GA1UdDgQWBBTmChaa6gQdCWZiXBQuHDz5nheCZDAfBgNVHSME
# GDAWgBSfpxVdAF5iXYP05dJlpxtTNRnpcjBfBgNVHR8EWDBWMFSgUqBQhk5odHRw
# Oi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBUaW1l
# LVN0YW1wJTIwUENBJTIwMjAxMCgxKS5jcmwwbAYIKwYBBQUHAQEEYDBeMFwGCCsG
# AQUFBzAChlBodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01p
# Y3Jvc29mdCUyMFRpbWUtU3RhbXAlMjBQQ0ElMjAyMDEwKDEpLmNydDAMBgNVHRMB
# Af8EAjAAMBYGA1UdJQEB/wQMMAoGCCsGAQUFBwMIMA4GA1UdDwEB/wQEAwIHgDAN
# BgkqhkiG9w0BAQsFAAOCAgEApKGQeTZyVRW+cCno0aJ5OdfGtkwTWKSnATLXy+gU
# tAEWgATjBmC5TzboSNR8JnpT/YV96Kt02hJv3A5JMzUAMw3nT4KESNke/vKaDUlr
# x1xALO0mTg5vceyqpQZDWTPXseF2NcjZlTgJlg40a+4yo2okG57X+xAuBjYpMRhm
# lVjo32Ld0PV9K/yrPCgZW8w0fc4wP0wnLUeHKNVqVNWUSxawfW5fHUcbG58k9qkO
# NRO3U9dkd9HiBlM4hLORjftulf6L1zottHSYjNd4WFr8tTTSQIZCjpSwdTjbp3en
# 34T3VHB1rLvFfpUdGmpDFeuB6g2y7pmawjcFKH1cd8TJPBeLQmCbUMS08sHN9LGQ
# A9UtrAtfefceiosQPqeNRS1JfIOuKB8t232Jx+cXeCTgYEKGqp3Ro3HLca/vBJJ4
# 4Ssq4AM603CiyW1Hs4KMnvG6wiyfsujwKBI6V0ZEmAFPMH0N2FkXJOgC8KFe1Ip/
# Pq6RkEm14RenNXUxWpF5goQpbneCAA2P7eiUZCftOhcy/ow3fCi1fEI++yX4rk4j
# yBuRv8ZZxqGRXF/ssgbQ782ROPHfmPh2FHf3L4R9RSpewB/uQMqLaiUhZrzPwbmE
# cdgdtGrFV4pVdpNiWzTtyxgs90PnaRJc8LHya5GtTf4HrZmu31qaMLDb6CGhEL42
# nfEwggdxMIIFWaADAgECAhMzAAAAFcXna54Cm0mZAAAAAAAVMA0GCSqGSIb3DQEB
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
# BAsTHm5TaGllbGQgVFNTIEVTTjo3RjAwLTA1RTAtRDk0NzElMCMGA1UEAxMcTWlj
# cm9zb2Z0IFRpbWUtU3RhbXAgU2VydmljZaIjCgEBMAcGBSsOAwIaAxUAg/0DZCgy
# FuFSBe496Itqm60dGv+ggYMwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMK
# V2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0
# IENvcnBvcmF0aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0Eg
# MjAxMDANBgkqhkiG9w0BAQsFAAIFAO2cqUwwIhgPMjAyNjA0MjkxNTU5MDhaGA8y
# MDI2MDQzMDE1NTkwOFowdzA9BgorBgEEAYRZCgQBMS8wLTAKAgUA7ZypTAIBADAK
# AgEAAgIZqAIB/zAHAgEAAgIT3TAKAgUA7Z36zAIBADA2BgorBgEEAYRZCgQCMSgw
# JjAMBgorBgEEAYRZCgMCoAowCAIBAAIDB6EgoQowCAIBAAIDAYagMA0GCSqGSIb3
# DQEBCwUAA4IBAQBMR7VLNzDFMYRj5UT+AntH4lJmAAArK5MjiGQjm4q1WNxQn29L
# +bBSeC+/8Zb+4qte4D7tSmf1+uJN3D5tQLuS7eGKdWKdX/7lXhSqf2m2cu7ehT7L
# Z30awHzwCIcBBOEOV486XqiaKwvXhoEw03P2Avrfivk+3zPX7+ThbEFSeiqQAIvB
# pIiCOnKSYvqgeipM+f666lSNVSNgoc8Ln9fLyQGq2RETbvDd6i1xs02bCKikNisZ
# gijloxuYxLynrmK28WX3R6QaohMi3bLqa3Ix7gth9cwKqK70FYZDaC62h8bm0W4R
# uknO6MCtRMe+IcfnFagOYOMXidF/H/KvuL9WMYIEDTCCBAkCAQEwgZMwfDELMAkG
# A1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQx
# HjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMdTWljcm9z
# b2Z0IFRpbWUtU3RhbXAgUENBIDIwMTACEzMAAAIeo6ykbjlvfEkAAQAAAh4wDQYJ
# YIZIAWUDBAIBBQCgggFKMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRABBDAvBgkq
# hkiG9w0BCQQxIgQgE8636YnS9wkb/WPyH5gH5ljneEAjYROz57rld5ONO3gwgfoG
# CyqGSIb3DQEJEAIvMYHqMIHnMIHkMIG9BCAvgV1q8/YHjIDPAb5/G6sR44R1ydvR
# AYsyEyMNAfbzgjCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNo
# aW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29y
# cG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEw
# AhMzAAACHqOspG45b3xJAAEAAAIeMCIEIAvbBsilYGWKwkmwfrGOvuMwCg+VuwfI
# qsOQOU0nAhHrMA0GCSqGSIb3DQEBCwUABIICACXADgtixPXj0qWCmnUOdrrxcHhc
# kjv1WL3+/bBMYjjU9u+t0SziPpU/+3BbEbJKknaGeiUJy+RTMxBYw2Lgf4CR5LMr
# 2DZ+gNQ3ca+wbzz+/WlA3OkxRkbnR4jT7Mi7klKHrphVL8Ua2uIssbf1JbJZWY5p
# 2lnZJGkRsqA7bJYQv9KQNRC9f+CnL6nF7CpvYYOSZRhqj0uzbiyFar5whHFxkYQc
# UskdKf1gV4NFdVQihQlue7Gn4yBxOx1jIXkd5rDZ3MAodqVZKoQmPRlzcM3QXgHn
# bhun3Cvx9YpBCEt6/5hSau8isL2jrbhpVvI0FPd620EJrokJWMnX1sM2kgEEsABu
# Pp7B9XKmehK2iNULT7RQj3RethwqhVkbq9l0l5De0XNYA7iKuzJj6xXz1uo9i+ZV
# 9QdiMX9m/PTjmq6/TLque/dYvLTD37/+N0PzJLW0+fOXcOUKONdaU79auDyTXdxs
# 3v2VF94XytDKWioSB8hNghG85nC/xbttW5lkscskK/JXfLwVtEmhdSEgxVKSEZaH
# MlqoRwtig0ueLO44P5OTYyYAGa+3GWXNLFbTxdTd+eSEckY0YHIFVp6vhxyIQGmM
# 4pXYdLVnubBwYLsZjtNDEumKQ6gn5htzuWk8J84o9OUpTE8OfdUMUtzhE0nh870Z
# 3BvQWMJHLIuEoM3o
# SIG # End Windows Authenticode signature block