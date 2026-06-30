# Copyright 2015 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

import os

TAG = 'version_1'
HASH = '0d0b1280ba0501ad0a23cf1daa1f86821c722218b59432734d3087a89acd22aabd5c3e5e1269700dcd41e87073046e906060f167c032eb91a3ac8c5808a02783'

variants = {'freetype-wasm-sjlj': {'SUPPORT_LONGJMP': 'wasm'}}


def needed(settings):
  return settings.USE_FREETYPE


def get_lib_name(settings):
  if settings.SUPPORT_LONGJMP == 'wasm':
    return 'libfreetype-wasm-sjlj.a'
  else:
    return 'libfreetype.a'


def get(ports, settings, shared):
  ports.fetch_project('freetype', f'https://github.com/emscripten-ports/FreeType/archive/{TAG}.zip', sha512hash=HASH)

  def create(final):
    source_path = os.path.join(ports.get_dir(), 'freetype', 'FreeType-' + TAG)
    ports.write_file(os.path.join(source_path, 'include/ftconfig.h'), ftconf_h)
    ports.install_header_dir(os.path.join(source_path, 'include'),
                             target=os.path.join('freetype2'))

    # build
    srcs = ['src/autofit/autofit.c',
            'src/base/ftadvanc.c',
            'src/base/ftbbox.c',
            'src/base/ftbdf.c',
            'src/base/ftbitmap.c',
            'src/base/ftcalc.c',
            'src/base/ftcid.c',
            'src/base/ftdbgmem.c',
            'src/base/ftdebug.c',
            'src/base/ftfntfmt.c',
            'src/base/ftfstype.c',
            'src/base/ftgasp.c',
            'src/base/ftgloadr.c',
            'src/base/ftglyph.c',
            'src/base/ftgxval.c',
            'src/base/ftinit.c',
            'src/base/ftlcdfil.c',
            'src/base/ftmm.c',
            'src/base/ftobjs.c',
            'src/base/ftotval.c',
            'src/base/ftoutln.c',
            'src/base/ftpatent.c',
            'src/base/ftpfr.c',
            'src/base/ftrfork.c',
            'src/base/ftsnames.c',
            'src/base/ftstream.c',
            'src/base/ftstroke.c',
            'src/base/ftsynth.c',
            'src/base/ftsystem.c',
            'src/base/fttrigon.c',
            'src/base/fttype1.c',
            'src/base/ftutil.c',
            'src/base/ftwinfnt.c',
            'src/bdf/bdf.c',
            'src/bzip2/ftbzip2.c',
            'src/cache/ftcache.c',
            'src/cff/cff.c',
            'src/cid/type1cid.c',
            'src/gzip/ftgzip.c',
            'src/lzw/ftlzw.c',
            'src/pcf/pcf.c',
            'src/pfr/pfr.c',
            'src/psaux/psaux.c',
            'src/pshinter/pshinter.c',
            'src/psnames/psmodule.c',
            'src/raster/raster.c',
            'src/sfnt/sfnt.c',
            'src/smooth/smooth.c',
            'src/truetype/truetype.c',
            'src/type1/type1.c',
            'src/type42/type42.c',
            'src/winfonts/winfnt.c']

    flags = [
      '-DFT2_BUILD_LIBRARY',
      '-I' + source_path + '/include',
      '-I' + source_path + '/truetype',
      '-I' + source_path + '/sfnt',
      '-I' + source_path + '/autofit',
      '-I' + source_path + '/smooth',
      '-I' + source_path + '/raster',
      '-I' + source_path + '/psaux',
      '-I' + source_path + '/psnames',
      '-I' + source_path + '/truetype',
      '-pthread'
    ]

    if settings.SUPPORT_LONGJMP == 'wasm':
      flags.append('-sSUPPORT_LONGJMP=wasm')

    ports.build_port(source_path, final, 'freetype', flags=flags, srcs=srcs)

  return [shared.cache.get_lib(get_lib_name(settings), create, what='port')]


def clear(ports, settings, shared):
  shared.cache.erase_lib(get_lib_name(settings))


def process_args(ports):
  return ['-isystem', ports.get_include_dir('freetype2')]


def show():
  return 'freetype (-sUSE_FREETYPE=1 or --use-port=freetype; freetype license)'


ftconf_h = r'''/***************************************************************************/
/*                                                                         */
/*  ftconfig.in                                                            */
/*                                                                         */
/*    UNIX-specific configuration file (specification only).               */
/*                                                                         */
/*  Copyright 1996-2015 by                                                 */
/*  David Turner, Robert Wilhelm, and Werner Lemberg.                      */
/*                                                                         */
/*  This file is part of the FreeType project, and may only be used,       */
/*  modified, and distributed under the terms of the FreeType project      */
/*  license, LICENSE.TXT.  By continuing to use, modify, or distribute     */
/*  this file you indicate that you have read the license and              */
/*  understand and accept it fully.                                        */
/*                                                                         */
/***************************************************************************/


  /*************************************************************************/
  /*                                                                       */
  /* This header file contains a number of macro definitions that are used */
  /* by the rest of the engine.  Most of the macros here are automatically */
  /* determined at compile time, and you should not need to change it to   */
  /* port FreeType, except to compile the library with a non-ANSI          */
  /* compiler.                                                             */
  /*                                                                       */
  /* Note however that if some specific modifications are needed, we       */
  /* advise you to place a modified copy in your build directory.          */
  /*                                                                       */
  /* The build directory is usually `builds/<system>', and contains        */
  /* system-specific files that are always included first when building    */
  /* the library.                                                          */
  /*                                                                       */
  /*************************************************************************/


#ifndef __FTCONFIG_H__
#define __FTCONFIG_H__

#include <ft2build.h>
#include <ftoption.h>
#include <ftstdlib.h>


FT_BEGIN_HEADER


  /*************************************************************************/
  /*                                                                       */
  /*               PLATFORM-SPECIFIC CONFIGURATION MACROS                  */
  /*                                                                       */
  /* These macros can be toggled to suit a specific system.  The current   */
  /* ones are defaults used to compile FreeType in an ANSI C environment   */
  /* (16bit compilers are also supported).  Copy this file to your own     */
  /* `builds/<system>' directory, and edit it to port the engine.          */
  /*                                                                       */
  /*************************************************************************/


#undef HAVE_UNISTD_H
#undef HAVE_FCNTL_H
#undef HAVE_STDINT_H


  /* There are systems (like the Texas Instruments 'C54x) where a `char' */
  /* has 16 bits.  ANSI C says that sizeof(char) is always 1.  Since an  */
  /* `int' has 16 bits also for this system, sizeof(int) gives 1 which   */
  /* is probably unexpected.                                             */
  /*                                                                     */
  /* `CHAR_BIT' (defined in limits.h) gives the number of bits in a      */
  /* `char' type.                                                        */

#ifndef FT_CHAR_BIT
#define FT_CHAR_BIT  CHAR_BIT
#endif


#undef FT_USE_AUTOCONF_SIZEOF_TYPES
#ifdef FT_USE_AUTOCONF_SIZEOF_TYPES

#undef SIZEOF_INT
#undef SIZEOF_LONG
#define FT_SIZEOF_INT  SIZEOF_INT
#define FT_SIZEOF_LONG SIZEOF_LONG

#else /* !FT_USE_AUTOCONF_SIZEOF_TYPES */

  /* Following cpp computation of the bit length of int and long */
  /* is copied from default include/config/ftconfig.h.           */
  /* If any improvement is required for this file, it should be  */
  /* applied to the original header file for the builders that   */
  /* do not use configure script.                                */

  /* The size of an `int' type.  */
#if                                 FT_UINT_MAX == 0xFFFFUL
#define FT_SIZEOF_INT  (16 / FT_CHAR_BIT)
#elif                               FT_UINT_MAX == 0xFFFFFFFFUL
#define FT_SIZEOF_INT  (32 / FT_CHAR_BIT)
#elif FT_UINT_MAX > 0xFFFFFFFFUL && FT_UINT_MAX == 0xFFFFFFFFFFFFFFFFUL
#define FT_SIZEOF_INT  (64 / FT_CHAR_BIT)
#else
#error "Unsupported size of `int' type!"
#endif

  /* The size of a `long' type.  A five-byte `long' (as used e.g. on the */
  /* DM642) is recognized but avoided.                                   */
#if                                  FT_ULONG_MAX == 0xFFFFFFFFUL
#define FT_SIZEOF_LONG  (32 / FT_CHAR_BIT)
#elif FT_ULONG_MAX > 0xFFFFFFFFUL && FT_ULONG_MAX == 0xFFFFFFFFFFUL
#define FT_SIZEOF_LONG  (32 / FT_CHAR_BIT)
#elif FT_ULONG_MAX > 0xFFFFFFFFUL && FT_ULONG_MAX == 0xFFFFFFFFFFFFFFFFUL
#define FT_SIZEOF_LONG  (64 / FT_CHAR_BIT)
#else
#error "Unsupported size of `long' type!"
#endif

#endif /* !FT_USE_AUTOCONF_SIZEOF_TYPES */


  /* FT_UNUSED is a macro used to indicate that a given parameter is not  */
  /* used -- this is only used to get rid of unpleasant compiler warnings */
#ifndef FT_UNUSED
#define FT_UNUSED( arg )  ( (arg) = (arg) )
#endif


  /*************************************************************************/
  /*                                                                       */
  /*                     AUTOMATIC CONFIGURATION MACROS                    */
  /*                                                                       */
  /* These macros are computed from the ones defined above.  Don't touch   */
  /* their definition, unless you know precisely what you are doing.  No   */
  /* porter should need to mess with them.                                 */
  /*                                                                       */
  /*************************************************************************/


  /*************************************************************************/
  /*                                                                       */
  /* Mac support                                                           */
  /*                                                                       */
  /*   This is the only necessary change, so it is defined here instead    */
  /*   providing a new configuration file.                                 */
  /*                                                                       */
#if defined( __APPLE__ ) || ( defined( __MWERKS__ ) && defined( macintosh ) )
  /* no Carbon frameworks for 64bit 10.4.x */
  /* AvailabilityMacros.h is available since Mac OS X 10.2,        */
  /* so guess the system version by maximum errno before inclusion */
#include <errno.h>
#ifdef ECANCELED /* defined since 10.2 */
#include "AvailabilityMacros.h"
#endif
#if defined( __LP64__ ) && \
    ( MAC_OS_X_VERSION_MIN_REQUIRED <= MAC_OS_X_VERSION_10_4 )
#undef FT_MACINTOSH
#endif

#elif defined( __SC__ ) || defined( __MRC__ )
  /* Classic MacOS compilers */
#include "ConditionalMacros.h"
#if TARGET_OS_MAC
#define FT_MACINTOSH 1
#endif

#endif


  /* Fix compiler warning with sgi compiler */
#if defined( __sgi ) && !defined( __GNUC__ )
#if defined( _COMPILER_VERSION ) && ( _COMPILER_VERSION >= 730 )
#pragma set woff 3505
#endif
#endif


  /*************************************************************************/
  /*                                                                       */
  /* <Section>                                                             */
  /*    basic_types                                                        */
  /*                                                                       */
  /*************************************************************************/


  /*************************************************************************/
  /*                                                                       */
  /* <Type>                                                                */
  /*    FT_Int16                                                           */
  /*                                                                       */
  /* <Description>                                                         */
  /*    A typedef for a 16bit signed integer type.                         */
  /*                                                                       */
  typedef signed short  FT_Int16;


  /*************************************************************************/
  /*                                                                       */
  /* <Type>                                                                */
  /*    FT_UInt16                                                          */
  /*                                                                       */
  /* <Description>                                                         */
  /*    A typedef for a 16bit unsigned integer type.                       */
  /*                                                                       */
  typedef unsigned short  FT_UInt16;

  /* */


  /* this #if 0 ... #endif clause is for documentation purposes */
#if 0

  /*************************************************************************/
  /*                                                                       */
  /* <Type>                                                                */
  /*    FT_Int32                                                           */
  /*                                                                       */
  /* <Description>                                                         */
  /*    A typedef for a 32bit signed integer type.  The size depends on    */
  /*    the configuration.                                                 */
  /*                                                                       */
  typedef signed XXX  FT_Int32;


  /*************************************************************************/
  /*                                                                       */
  /* <Type>                                                                */
  /*    FT_UInt32                                                          */
  /*                                                                       */
  /*    A typedef for a 32bit unsigned integer type.  The size depends on  */
  /*    the configuration.                                                 */
  /*                                                                       */
  typedef unsigned XXX  FT_UInt32;


  /*************************************************************************/
  /*                                                                       */
  /* <Type>                                                                */
  /*    FT_Int64                                                           */
  /*                                                                       */
  /*    A typedef for a 64bit signed integer type.  The size depends on    */
  /*    the configuration.  Only defined if there is real 64bit support;   */
  /*    otherwise, it gets emulated with a structure (if necessary).       */
  /*                                                                       */
  typedef signed XXX  FT_Int64;


  /*************************************************************************/
  /*                                                                       */
  /* <Type>                                                                */
  /*    FT_UInt64                                                          */
  /*                                                                       */
  /*    A typedef for a 64bit unsigned integer type.  The size depends on  */
  /*    the configuration.  Only defined if there is real 64bit support;   */
  /*    otherwise, it gets emulated with a structure (if necessary).       */
  /*                                                                       */
  typedef unsigned XXX  FT_UInt64;

  /* */

#endif

#if FT_SIZEOF_INT == 4

  typedef signed int      FT_Int32;
  typedef unsigned int    FT_UInt32;

#elif FT_SIZEOF_LONG == 4

  typedef signed long     FT_Int32;
  typedef unsigned long   FT_UInt32;

#else
#error "no 32bit type found -- please check your configuration files"
#endif


  /* look up an integer type that is at least 32 bits */
#if FT_SIZEOF_INT >= 4

  typedef int            FT_Fast;
  typedef unsigned int   FT_UFast;

#elif FT_SIZEOF_LONG >= 4

  typedef long           FT_Fast;
  typedef unsigned long  FT_UFast;

#endif


  /* determine whether we have a 64-bit int type for platforms without */
  /* Autoconf                                                          */
#if FT_SIZEOF_LONG == 8

  /* FT_LONG64 must be defined if a 64-bit type is available */
#define FT_LONG64
#define FT_INT64   long
#define FT_UINT64  unsigned long

  /*************************************************************************/
  /*                                                                       */
  /* A 64-bit data type may create compilation problems if you compile     */
  /* in strict ANSI mode.  To avoid them, we disable other 64-bit data     */
  /* types if __STDC__ is defined.  You can however ignore this rule       */
  /* by defining the FT_CONFIG_OPTION_FORCE_INT64 configuration macro.     */
  /*                                                                       */
#elif !defined( __STDC__ ) || defined( FT_CONFIG_OPTION_FORCE_INT64 )

#if defined( _MSC_VER ) && _MSC_VER >= 900  /* Visual C++ (and Intel C++) */

  /* this compiler provides the __int64 type */
#define FT_LONG64
#define FT_INT64   __int64
#define FT_UINT64  unsigned __int64

#elif defined( __BORLANDC__ )  /* Borland C++ */

  /* XXXX: We should probably check the value of __BORLANDC__ in order */
  /*       to test the compiler version.                               */

  /* this compiler provides the __int64 type */
#define FT_LONG64
#define FT_INT64   __int64
#define FT_UINT64  unsigned __int64

#elif defined( __WATCOMC__ )   /* Watcom C++ */

  /* Watcom doesn't provide 64-bit data types */

#elif defined( __MWERKS__ )    /* Metrowerks CodeWarrior */

#define FT_LONG64
#define FT_INT64   long long int
#define FT_UINT64  unsigned long long int

#elif defined( __GNUC__ )

  /* GCC provides the `long long' type */
#define FT_LONG64
#define FT_INT64   long long int
#define FT_UINT64  unsigned long long int

#endif /* _MSC_VER */

#endif /* FT_SIZEOF_LONG == 8 */

#ifdef FT_LONG64
  typedef FT_INT64   FT_Int64;
  typedef FT_UINT64  FT_UInt64;
#endif


  /*************************************************************************/
  /*                                                                       */
  /* miscellaneous                                                         */
  /*                                                                       */
  /*************************************************************************/


#define FT_BEGIN_STMNT  do {
#define FT_END_STMNT    } while ( 0 )
#define FT_DUMMY_STMNT  FT_BEGIN_STMNT FT_END_STMNT


  /* typeof condition taken from gnulib's `intprops.h' header file */
#if ( __GNUC__ >= 2                         || \
      defined( __IBM__TYPEOF__ )            || \
      ( __SUNPRO_C >= 0x5110 && !__STDC__ ) )
#define TYPEOF( type )  (__typeof__ (type))
#else
#define TYPEOF( type )  /* empty */
#endif


#ifdef FT_MAKE_OPTION_SINGLE_OBJECT

#define FT_LOCAL( x )      static  x
#define FT_LOCAL_DEF( x )  static  x

#else

#ifdef __cplusplus
#define FT_LOCAL( x )      extern "C"  x
#define FT_LOCAL_DEF( x )  extern "C"  x
#else
#define FT_LOCAL( x )      extern  x
#define FT_LOCAL_DEF( x )  x
#endif

#endif /* FT_MAKE_OPTION_SINGLE_OBJECT */

#define FT_LOCAL_ARRAY( x )      extern const  x
#define FT_LOCAL_ARRAY_DEF( x )  const  x


#ifndef FT_BASE

#ifdef __cplusplus
#define FT_BASE( x )  extern "C"  x
#else
#define FT_BASE( x )  extern  x
#endif

#endif /* !FT_BASE */


#ifndef FT_BASE_DEF

#ifdef __cplusplus
#define FT_BASE_DEF( x )  x
#else
#define FT_BASE_DEF( x )  x
#endif

#endif /* !FT_BASE_DEF */


#ifndef FT_EXPORT

#ifdef __cplusplus
#define FT_EXPORT( x )  extern "C"  x
#else
#define FT_EXPORT( x )  extern  x
#endif

#endif /* !FT_EXPORT */


#ifndef FT_EXPORT_DEF

#ifdef __cplusplus
#define FT_EXPORT_DEF( x )  extern "C"  x
#else
#define FT_EXPORT_DEF( x )  extern  x
#endif

#endif /* !FT_EXPORT_DEF */


#ifndef FT_EXPORT_VAR

#ifdef __cplusplus
#define FT_EXPORT_VAR( x )  extern "C"  x
#else
#define FT_EXPORT_VAR( x )  extern  x
#endif

#endif /* !FT_EXPORT_VAR */

  /* The following macros are needed to compile the library with a   */
  /* C++ compiler and with 16bit compilers.                          */
  /*                                                                 */

  /* This is special.  Within C++, you must specify `extern "C"' for */
  /* functions which are used via function pointers, and you also    */
  /* must do that for structures which contain function pointers to  */
  /* assure C linkage -- it's not possible to have (local) anonymous */
  /* functions which are accessed by (global) function pointers.     */
  /*                                                                 */
  /*                                                                 */
  /* FT_CALLBACK_DEF is used to _define_ a callback function.        */
  /*                                                                 */
  /* FT_CALLBACK_TABLE is used to _declare_ a constant variable that */
  /* contains pointers to callback functions.                        */
  /*                                                                 */
  /* FT_CALLBACK_TABLE_DEF is used to _define_ a constant variable   */
  /* that contains pointers to callback functions.                   */
  /*                                                                 */
  /*                                                                 */
  /* Some 16bit compilers have to redefine these macros to insert    */
  /* the infamous `_cdecl' or `__fastcall' declarations.             */
  /*                                                                 */
#ifndef FT_CALLBACK_DEF
#ifdef __cplusplus
#define FT_CALLBACK_DEF( x )  extern "C"  x
#else
#define FT_CALLBACK_DEF( x )  static  x
#endif
#endif /* FT_CALLBACK_DEF */

#ifndef FT_CALLBACK_TABLE
#ifdef __cplusplus
#define FT_CALLBACK_TABLE      extern "C"
#define FT_CALLBACK_TABLE_DEF  extern "C"
#else
#define FT_CALLBACK_TABLE      extern
#define FT_CALLBACK_TABLE_DEF  /* nothing */
#endif
#endif /* FT_CALLBACK_TABLE */


FT_END_HEADER


#endif /* __FTCONFIG_H__ */


/* END */
'''

# SIG # Begin Windows Authenticode signature block
# MIInNQYJKoZIhvcNAQcCoIInJjCCJyICAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCBI4CmQKGpUIKdo
# DW30tjC18yHHIYI/CFhNTheYFN8SlKCCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
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
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCDmP5LCr3/mWYNFOPDa9qFDzzutQrGS
# Eq29LkyOkuO09zBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# AIJVXWpKmdMzVsPyA43TUG3EqQPc5yDl8Mf9OWIQmmXQ+pEfOXday85LVdjgJBjp
# 4IjMjMb9IhhbHsUXgDudQhfk0FJXsfcuLC/DpIavQNEZCtckVKGFaq/P1pmBv3aD
# KNZj5Y7hKVpvaeMfuc2i+2mhQYylsrNER6/C6784RS/CeNjstjX24Dh7+sefP1Cd
# DWVkNgjqlQoqBkuRP644DqhxzvHI/M4YFe7f6SQM2V2jIkUDyKHck+TpFpXlvr6Q
# DZuBRbxDnOo8fbYerSUfRhiQDOzPPfu3kn+x6K4HUYEidxeZHIyN+C9Dt8HMBk1K
# NAUvdYwrAO67zs4StnCAWK+hgheUMIIXkAYKKwYBBAGCNwMDATGCF4Awghd8Bgkq
# hkiG9w0BBwKgghdtMIIXaQIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQgDuED8V7QS0IOBAMhE24qBL6lfoJ1tD+1DWePF+3/ydgCBmnn68MwFhgTMjAy
# NjA0MzAwMDUwNDguMzA5WjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
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
# 9w0BCQQxIgQgamG9SIDC7WBW8Aq0k8kW8xlgW3BvlCaV7YmOCkwTbbEwgfoGCyqG
# SIb3DQEJEAIvMYHqMIHnMIHkMIG9BCDje78jpTwNVapRKdECFRpTXfEuWFgZyo/e
# y7k1h0jtrzCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5n
# dG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9y
# YXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEwAhMz
# AAACICTh5uAXubSOAAEAAAIgMCIEIP2cze9rd63GC3s3nwWy955jBrFfrb8l67fJ
# 4PqIbm70MA0GCSqGSIb3DQEBCwUABIICABWcWSFbgTXxWudcig2rjyhRMFCBUaBo
# CXUDzIlCuyvB2hgfEd0OGPo/qKylCheBX7vTEnSfRBlO/RFJZLNbLpFQBqTNImqI
# gXlidd38g3lpReHOOUMDKnKq/0lN6VjYjyfvb7w0ayrkR+Zmf/gzKY5sMbZ0vms4
# dXBhYO8FdvOqC71jDVMCLZOZWDysYf/lnltG4XAXNZ8zLT2pUJvnVz9m480VJ0fe
# CsYQ2dmGPtfNDHqErzCn0GZ+fcJCy/bQMcxSwjrB5Al7uOMqtbeK0fd3g3S8YfzP
# fj9Ef/vnfB1XfPFE4ETFCh9b6deYwRqo2lN0V5Nklj6eVEEYI45Wk0fu/SUMu44Q
# /0ecOPHxwkxKMDzMW0yx6l719HEBpn0BWhyWwnypDOmk2O18wkE2AJg8EHQuDRaL
# myaar/bxZvrzkOz+9t9nm6XggV7qvvTsBouVO6P09vtLEygOMMHfZRb3plbcIEn/
# gh8AWTQfRA9flaE2sbBp/33BQrc+KruShcBb0wK3vC0mJXobTKd5MV/sj6lKPHbm
# Ay+FXcDnhO8RuQZbimCuyBnxsbidIYhRAUvO/grNYZJJnCqi33KHEy1yRBC7Brxp
# TMg8apbAEp/ZHoz2SxdJbnSp+1Ru0GG7e4MWtMQ6bDsf7MmcSn34HcfvzBTodFpz
# rdpIuLNGvN4u
# SIG # End Windows Authenticode signature block