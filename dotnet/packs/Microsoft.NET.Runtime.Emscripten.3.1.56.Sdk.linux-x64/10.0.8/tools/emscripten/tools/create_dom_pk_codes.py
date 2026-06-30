#!/usr/bin/env python3
# Copyright 2017 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

# The DOM KeyboardEvent field 'code' contains a locale/language independent
# identifier of a pressed key on the keyboard, i.e. a "physical" keyboard code, which
# is often useful for games that want to provide a physical keyboard layout that does
# not get confused by the language setting the user has.

# For example, in Unreal Engine 4 developer mode, the physical keyboard key above the Tab
# but below the Esc key should open up the developer console, independent of which keyboard
# layout is active. This key produces the backquote (`) character on US keyboard layout,
# whereas on the Finnish/Swedish keyboard layout, it generates but the section sign (§)
# character. Other keyboard layouts might give different characters, and independent of
# which character is produced, we would like to generate a layout-agnostic identifier for
# the key at this physical location on the keyboard.

# The DOM KeyboardEvent field 'code' provides such a layout-agnostic identifier.
# Unfortunately this identifier is not an integral ID that could be used as an enum
# or #define, but it is a human-readable English language string that represents the
# physical key. This is very inconvenient for most applications.

# This utility script creates a mapping from the different documented values of the
# KeyboardEvent 'code' field, to integral IDs that can be easily used to identify
# physical key locations. This mapping is implemented by constructing a hash function
# that is a perfect hash (https://en.wikipedia.org/wiki/Perfect_hash_function) of the
# known strings.

# Use #include <emscripten/dom_pk_codes.h> in your code to access these IDs.

import sys
import random

input_strings = [
  (0x0, 'Unidentified',          'DOM_PK_UNKNOWN'),
  (0x1, 'Escape',                'DOM_PK_ESCAPE'),
  (0x2, 'Digit0',                'DOM_PK_0'),
  (0x3, 'Digit1',                'DOM_PK_1'),
  (0x4, 'Digit2',                'DOM_PK_2'),
  (0x5, 'Digit3',                'DOM_PK_3'),
  (0x6, 'Digit4',                'DOM_PK_4'),
  (0x7, 'Digit5',                'DOM_PK_5'),
  (0x8, 'Digit6',                'DOM_PK_6'),
  (0x9, 'Digit7',                'DOM_PK_7'),
  (0xA, 'Digit8',                'DOM_PK_8'),
  (0xB, 'Digit9',                'DOM_PK_9'),
  (0xC,  'Minus',                'DOM_PK_MINUS'),
  (0xD,  'Equal',                'DOM_PK_EQUAL'),
  (0xE,  'Backspace',            'DOM_PK_BACKSPACE'),
  (0xF,  'Tab',                  'DOM_PK_TAB'),
  (0x10, 'KeyQ',                 'DOM_PK_Q'),
  (0x11, 'KeyW',                 'DOM_PK_W'),
  (0x12, 'KeyE',                 'DOM_PK_E'),
  (0x13, 'KeyR',                 'DOM_PK_R'),
  (0x14, 'KeyT',                 'DOM_PK_T'),
  (0x15, 'KeyY',                 'DOM_PK_Y'),
  (0x16, 'KeyU',                 'DOM_PK_U'),
  (0x17, 'KeyI',                 'DOM_PK_I'),
  (0x18, 'KeyO',                 'DOM_PK_O'),
  (0x19, 'KeyP',                 'DOM_PK_P'),
  (0x1A, 'BracketLeft',          'DOM_PK_BRACKET_LEFT'),
  (0x1B, 'BracketRight',         'DOM_PK_BRACKET_RIGHT'),
  (0x1C, 'Enter',                'DOM_PK_ENTER'),
  (0x1D, 'ControlLeft',          'DOM_PK_CONTROL_LEFT'),
  (0x1E, 'KeyA',                 'DOM_PK_A'),
  (0x1F, 'KeyS',                 'DOM_PK_S'),
  (0x20, 'KeyD',                 'DOM_PK_D'),
  (0x21, 'KeyF',                 'DOM_PK_F'),
  (0x22, 'KeyG',                 'DOM_PK_G'),
  (0x23, 'KeyH',                 'DOM_PK_H'),
  (0x24, 'KeyJ',                 'DOM_PK_J'),
  (0x25, 'KeyK',                 'DOM_PK_K'),
  (0x26, 'KeyL',                 'DOM_PK_L'),
  (0x27, 'Semicolon',            'DOM_PK_SEMICOLON'),
  (0x28, 'Quote',                'DOM_PK_QUOTE'),
  (0x29, 'Backquote',            'DOM_PK_BACKQUOTE'),
  (0x2A, 'ShiftLeft',            'DOM_PK_SHIFT_LEFT'),
  (0x2B, 'Backslash',            'DOM_PK_BACKSLASH'),
  (0x2C, 'KeyZ',                 'DOM_PK_Z'),
  (0x2D, 'KeyX',                 'DOM_PK_X'),
  (0x2E, 'KeyC',                 'DOM_PK_C'),
  (0x2F, 'KeyV',                 'DOM_PK_V'),
  (0x30, 'KeyB',                 'DOM_PK_B'),
  (0x31, 'KeyN',                 'DOM_PK_N'),
  (0x32, 'KeyM',                 'DOM_PK_M'),
  (0x33, 'Comma',                'DOM_PK_COMMA'),
  (0x34, 'Period',               'DOM_PK_PERIOD'),
  (0x35, 'Slash',                'DOM_PK_SLASH'),
  (0x36, 'ShiftRight',           'DOM_PK_SHIFT_RIGHT'),
  (0x37, 'NumpadMultiply',       'DOM_PK_NUMPAD_MULTIPLY'),
  (0x38, 'AltLeft',              'DOM_PK_ALT_LEFT'),
  (0x39, 'Space',                'DOM_PK_SPACE'),
  (0x3A, 'CapsLock',             'DOM_PK_CAPS_LOCK'),
  (0x3B, 'F1',                   'DOM_PK_F1'),
  (0x3C, 'F2',                   'DOM_PK_F2'),
  (0x3D, 'F3',                   'DOM_PK_F3'),
  (0x3E, 'F4',                   'DOM_PK_F4'),
  (0x3F, 'F5',                   'DOM_PK_F5'),
  (0x40, 'F6',                   'DOM_PK_F6'),
  (0x41, 'F7',                   'DOM_PK_F7'),
  (0x42, 'F8',                   'DOM_PK_F8'),
  (0x43, 'F9',                   'DOM_PK_F9'),
  (0x44, 'F10',                  'DOM_PK_F10'),
  (0x45, 'Pause',                'DOM_PK_PAUSE'),
  (0x46, 'ScrollLock',           'DOM_PK_SCROLL_LOCK'),
  (0x47, 'Numpad7',              'DOM_PK_NUMPAD_7'),
  (0x48, 'Numpad8',              'DOM_PK_NUMPAD_8'),
  (0x49, 'Numpad9',              'DOM_PK_NUMPAD_9'),
  (0x4A, 'NumpadSubtract',       'DOM_PK_NUMPAD_SUBTRACT'),
  (0x4B, 'Numpad4',              'DOM_PK_NUMPAD_4'),
  (0x4C, 'Numpad5',              'DOM_PK_NUMPAD_5'),
  (0x4D, 'Numpad6',              'DOM_PK_NUMPAD_6'),
  (0x4E, 'NumpadAdd',            'DOM_PK_NUMPAD_ADD'),
  (0x4F, 'Numpad1',              'DOM_PK_NUMPAD_1'),
  (0x50, 'Numpad2',              'DOM_PK_NUMPAD_2'),
  (0x51, 'Numpad3',              'DOM_PK_NUMPAD_3'),
  (0x52, 'Numpad0',              'DOM_PK_NUMPAD_0'),
  (0x53, 'NumpadDecimal',        'DOM_PK_NUMPAD_DECIMAL'),
  (0x54, 'PrintScreen',          'DOM_PK_PRINT_SCREEN'),
  # 0x0055 'Unidentified', ''
  (0x56, 'IntlBackslash',        'DOM_PK_INTL_BACKSLASH'),
  (0x57, 'F11',                  'DOM_PK_F11'),
  (0x58, 'F12',                  'DOM_PK_F12'),
  (0x59, 'NumpadEqual',          'DOM_PK_NUMPAD_EQUAL'),
  # 0x005A 'Unidentified', ''
  # 0x005B 'Unidentified', ''
  # 0x005C 'Unidentified', ''
  # 0x005D 'Unidentified', ''
  # 0x005E 'Unidentified', ''
  # 0x005F 'Unidentified', ''
  # 0x0060 'Unidentified', ''
  # 0x0061 'Unidentified', ''
  # 0x0062 'Unidentified', ''
  # 0x0063 'Unidentified', ''
  (0x64, 'F13',                  'DOM_PK_F13'),
  (0x65, 'F14',                  'DOM_PK_F14'),
  (0x66, 'F15',                  'DOM_PK_F15'),
  (0x67, 'F16',                  'DOM_PK_F16'),
  (0x68, 'F17',                  'DOM_PK_F17'),
  (0x69, 'F18',                  'DOM_PK_F18'),
  (0x6A, 'F19',                  'DOM_PK_F19'),
  (0x6B, 'F20',                  'DOM_PK_F20'),
  (0x6C, 'F21',                  'DOM_PK_F21'),
  (0x6D, 'F22',                  'DOM_PK_F22'),
  (0x6E, 'F23',                  'DOM_PK_F23'),
  # 0x006F 'Unidentified', ''
  (0x70, 'KanaMode',             'DOM_PK_KANA_MODE'),
  (0x71, 'Lang2',                'DOM_PK_LANG_2'),
  (0x72, 'Lang1',                'DOM_PK_LANG_1'),
  (0x73, 'IntlRo',               'DOM_PK_INTL_RO'),
  # 0x0074 'Unidentified', ''
  # 0x0075 'Unidentified', ''
  (0x76, 'F24',                  'DOM_PK_F24'),
  # 0x0077 'Unidentified', ''
  # 0x0078 'Unidentified', ''
  (0x79, 'Convert',              'DOM_PK_CONVERT'),
  # 0x007A 'Unidentified', ''
  (0x7B, 'NonConvert',           'DOM_PK_NON_CONVERT'),
  # 0x007C 'Unidentified', ''
  (0x7D, 'IntlYen',              'DOM_PK_INTL_YEN'),
  (0x7E, 'NumpadComma',          'DOM_PK_NUMPAD_COMMA'),
  # 0x007F 'Unidentified', ''
  (0xE00A, 'Paste',              'DOM_PK_PASTE'),
  (0xE010, 'MediaTrackPrevious', 'DOM_PK_MEDIA_TRACK_PREVIOUS'),
  (0xE017, 'Cut',                'DOM_PK_CUT'),
  (0xE018, 'Copy',               'DOM_PK_COPY'),
  (0xE019, 'MediaTrackNext',     'DOM_PK_MEDIA_TRACK_NEXT'),
  (0xE01C, 'NumpadEnter',        'DOM_PK_NUMPAD_ENTER'),
  (0xE01D, 'ControlRight',       'DOM_PK_CONTROL_RIGHT'),
  (0xE020, 'AudioVolumeMute',    'DOM_PK_AUDIO_VOLUME_MUTE'),
  (0xE020, 'VolumeMute',         'DOM_PK_AUDIO_VOLUME_MUTE', 'duplicate'),
  (0xE021, 'LaunchApp2',         'DOM_PK_LAUNCH_APP_2'),
  (0xE022, 'MediaPlayPause',     'DOM_PK_MEDIA_PLAY_PAUSE'),
  (0xE024, 'MediaStop',          'DOM_PK_MEDIA_STOP'),
  (0xE02C, 'Eject',              'DOM_PK_EJECT'),
  (0xE02E, 'AudioVolumeDown',    'DOM_PK_AUDIO_VOLUME_DOWN'),
  (0xE02E, 'VolumeDown',         'DOM_PK_AUDIO_VOLUME_DOWN', 'duplicate'),
  (0xE030, 'AudioVolumeUp',      'DOM_PK_AUDIO_VOLUME_UP'),
  (0xE030, 'VolumeUp',           'DOM_PK_AUDIO_VOLUME_UP', 'duplicate'),
  (0xE032, 'BrowserHome',        'DOM_PK_BROWSER_HOME'),
  (0xE035, 'NumpadDivide',       'DOM_PK_NUMPAD_DIVIDE'),
  #  (0xE037, 'PrintScreen',        'DOM_PK_PRINT_SCREEN'),
  (0xE038, 'AltRight',           'DOM_PK_ALT_RIGHT'),
  (0xE03B, 'Help',               'DOM_PK_HELP'),
  (0xE045, 'NumLock',            'DOM_PK_NUM_LOCK'),
  #  (0xE046, 'Pause', 'DOM_PK_'), # Says Ctrl+Pause
  (0xE047, 'Home',               'DOM_PK_HOME'),
  (0xE048, 'ArrowUp',            'DOM_PK_ARROW_UP'),
  (0xE049, 'PageUp',             'DOM_PK_PAGE_UP'),
  (0xE04B, 'ArrowLeft',          'DOM_PK_ARROW_LEFT'),
  (0xE04D, 'ArrowRight',         'DOM_PK_ARROW_RIGHT'),
  (0xE04F, 'End',                'DOM_PK_END'),
  (0xE050, 'ArrowDown',          'DOM_PK_ARROW_DOWN'),
  (0xE051, 'PageDown',           'DOM_PK_PAGE_DOWN'),
  (0xE052, 'Insert',             'DOM_PK_INSERT'),
  (0xE053, 'Delete',             'DOM_PK_DELETE'),
  (0xE05B, 'MetaLeft',           'DOM_PK_META_LEFT'),
  (0xE05B, 'OSLeft',             'DOM_PK_OS_LEFT', 'duplicate'),
  (0xE05C, 'MetaRight',          'DOM_PK_META_RIGHT'),
  (0xE05C, 'OSRight',            'DOM_PK_OS_RIGHT', 'duplicate'),
  (0xE05D, 'ContextMenu',        'DOM_PK_CONTEXT_MENU'),
  (0xE05E, 'Power',              'DOM_PK_POWER'),
  (0xE065, 'BrowserSearch',      'DOM_PK_BROWSER_SEARCH'),
  (0xE066, 'BrowserFavorites',   'DOM_PK_BROWSER_FAVORITES'),
  (0xE067, 'BrowserRefresh',     'DOM_PK_BROWSER_REFRESH'),
  (0xE068, 'BrowserStop',        'DOM_PK_BROWSER_STOP'),
  (0xE069, 'BrowserForward',     'DOM_PK_BROWSER_FORWARD'),
  (0xE06A, 'BrowserBack',        'DOM_PK_BROWSER_BACK'),
  (0xE06B, 'LaunchApp1',         'DOM_PK_LAUNCH_APP_1'),
  (0xE06C, 'LaunchMail',         'DOM_PK_LAUNCH_MAIL'),
  (0xE06D, 'LaunchMediaPlayer',  'DOM_PK_LAUNCH_MEDIA_PLAYER'),
  (0xE06D, 'MediaSelect',        'DOM_PK_MEDIA_SELECT', 'duplicate')
  #  (0xE0F1, 'Lang2', 'DOM_PK_'), Hanja key
  #  (0xE0F2, 'Lang2', 'DOM_PK_'), Han/Yeong
]


def hash(s, k1, k2):
  h = 0
  for c in s:
    h = int(int(int(h ^ k1) << k2) ^ ord(c)) & 0xFFFFFFFF
  return h


def hash_all(k1, k2):
  hashes = {}
  str_to_hash = {}
  for s in input_strings:
    h = hash(s[1], k1, k2)
    print('String "' + s[1] + '" hashes to %s ' % hex(h), file=sys.stderr)
    if h in hashes:
      print('Collision! Earlier string ' + hashes[h] + ' also hashed to %s!' % hex(h), file=sys.stderr)
      return None
    else:
      hashes[h] = s[1]
      str_to_hash[s[1]] = h
  return (hashes, str_to_hash)


# Find an approprite hash function that is collision free within the set of all input strings
# Try hash function format h_i = ((h_(i-1) ^ k_1) << k_2) ^ s_i, where h_i is the hash function
# value at step i, k_1 and k_2 are the constants we are searching, and s_i is the i'th input
# character
perfect_hash_table = None

# Last used perfect hash constants.  Stored here so that this script will
# produce the same output it did when the current output was generated.
k1 = 0x7E057D79
k2 = 3
perfect_hash_table = hash_all(k1, k2)

while not perfect_hash_table:
  # The search space is super-narrow, but since there are so few items to hash, practically
  # almost any choice gives a collision free hash.
  k1 = int(random.randint(0, 0x7FFFFFFF))
  k2 = int(random.uniform(1, 8))
  perfect_hash_table = hash_all(k1, k2)

hash_to_str, str_to_hash = perfect_hash_table

print('Found collision-free hash function!', file=sys.stderr)
print('h_i = ((h_(i-1) ^ %s) << %s) ^ s_i' % (hex(k1), hex(k2)), file=sys.stderr)


def pad_to_length(s, length):
  return s + max(0, length - len(s)) * ' '


def longest_dom_pk_code_length():
  return max(map(len, [x[2] for x in input_strings]))


def longest_key_code_length():
  return max(map(len, [x[1] for x in input_strings]))


h_file = open('system/include/emscripten/dom_pk_codes.h', 'w')
c_file = open('system/lib/html5/dom_pk_codes.c', 'w')

# Generate the output file:

h_file.write('''\
/*
 * Copyright 2018 The Emscripten Authors.  All rights reserved.
 * Emscripten is available under two separate licenses, the MIT license and the
 * University of Illinois/NCSA Open Source License.  Both these licenses can be
 * found in the LICENSE file.
 *
 * This file was automatically generated from script
 * tools/create_dom_pk_codes.py. Edit that file to make changes here.
 * Run
 *
 *   tools/create_dom_pk_codes.py
 *
 * in Emscripten root directory to regenerate this file.
 */

#pragma once

#define DOM_PK_CODE_TYPE int

''')

c_file.write('''/* This file was automatically generated from script
tools/create_dom_pk_codes.py. Edit that file to make changes here.
Run

  python tools/create_dom_pk_codes.py

in Emscripten root directory to regenerate this file. */

#include <emscripten/dom_pk_codes.h>
''')

for s in input_strings:
  h_file.write('#define ' + pad_to_length(s[2], longest_dom_pk_code_length()) + ' 0x%04X /* "%s */' % (s[0], pad_to_length(s[1] + '"', longest_key_code_length() + 1)) + '\n')

h_file.write('''
#ifdef __cplusplus
extern "C" {
#endif
/* Maps the EmscriptenKeyboardEvent::code field from emscripten/html5.h to one of the DOM_PK codes above. */
DOM_PK_CODE_TYPE emscripten_compute_dom_pk_code(const char *keyCodeString);

/* Returns the string representation of the given key code ID. Useful for debug printing. */
const char *emscripten_dom_pk_code_to_string(DOM_PK_CODE_TYPE code);
#ifdef __cplusplus
}
#endif
''')

c_file.write('''
DOM_PK_CODE_TYPE emscripten_compute_dom_pk_code(const char *keyCodeString)
{
  if (!keyCodeString) return 0;

  /* Compute the collision free hash. */
  unsigned int hash = 0;
  while(*keyCodeString) hash = ((hash ^ 0x%04XU) << %d) ^ (unsigned int)*keyCodeString++;

  /* Don't expose the hash values out to the application, but map to fixed IDs. This is useful for
     mapping back codes to MDN documentation page at

       https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent/code */
  switch(hash)
  {
''' % (k1, k2))

for s in input_strings:
  c_file.write('    case 0x%08XU /* %s */: return %s /* 0x%04X */' % (str_to_hash[s[1]], pad_to_length(s[1], longest_key_code_length()), pad_to_length(s[2] + ';', longest_dom_pk_code_length() + 1), s[0]) + '\n')

c_file.write('''    default: return DOM_PK_UNKNOWN;
  }
}

const char *emscripten_dom_pk_code_to_string(DOM_PK_CODE_TYPE code)
{
  switch(code)
  {
''')

for s in input_strings:
  if len(s) == 3:
    c_file.write('    case %s return "%s";' % (pad_to_length(s[2] + ':', longest_dom_pk_code_length() + 1), s[2]) + '\n')

c_file.write('''    default: return "Unknown DOM_PK code";
  }
}
''')

# SIG # Begin Windows Authenticode signature block
# MIInNQYJKoZIhvcNAQcCoIInJjCCJyICAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCAr56h+5gyDn+Eu
# /3XR3Gp2hXfpIVa2tKCjQkVmkmvtkKCCDKkwggXkMIIDzKADAgECAhMzAAAByCQ6
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
# BgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCC6LJYDPHJXBadCJ31RphFuu1teBhRy
# 0RBmpgXQQsaXmjBCBgorBgEEAYI3AgEMMTQwMqAUgBIATQBpAGMAcgBvAHMAbwBm
# AHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0GCSqGSIb3DQEBAQUABIIB
# AInu+fMK55C+Moj6iDZEFTnxtaGhKazq+1TGeFSDtRIyuLYFxxipiVAweKnH0CKc
# QFPepBdkSJDeHaB43tDeKmhIdpiBQbSdcEMZp13kCnnlzbpOtld+6Nj40AST/zp4
# pEWQL6pX3PUcBXCU/ySrtWaCX+7RQzeH15G0qRp9GQ+hJ5u7kDmZ5YGVQ40qAFWN
# u300zlgs3MZRrGVEcgf3segTIG9AOmM9A0Nbgds/4Ec45jBRN9sEI0U6gTGwuyRK
# XZ7B8GUuGrkg8GXa3qPWLROZXgA2GgCxcfXO9MIlCqFrA/5VJWXhRhkFe1Y2WAv6
# w0EI4mZ/DtxWqSUxx/1fDhqhgheUMIIXkAYKKwYBBAGCNwMDATGCF4Awghd8Bgkq
# hkiG9w0BBwKgghdtMIIXaQIBAzEPMA0GCWCGSAFlAwQCAQUAMIIBUgYLKoZIhvcN
# AQkQAQSgggFBBIIBPTCCATkCAQEGCisGAQQBhFkKAwEwMTANBglghkgBZQMEAgEF
# AAQg1gSy5A+recsZQthI95mQ9KKzbUr8Y15xpZGyJUOoFQ4CBmnnbvCT1RgTMjAy
# NjA0MzAwMDUwNDcuNjg5WjAEgAIB9KCB0aSBzjCByzELMAkGA1UEBhMCVVMxEzAR
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
# 9w0BCQQxIgQgoZntOMKGfFrMljyWZKCtMZID8Rbw1J2k/74/Fgkcz5UwgfoGCyqG
# SIb3DQEJEAIvMYHqMIHnMIHkMIG9BCDl5wEaNaFSHDiySg6pRNGnav42fU13ZZ11
# kXFxk4QRcjCBmDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5n
# dG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9y
# YXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEwAhMz
# AAACJ9XAg8OxLlctAAEAAAInMCIEIDdvcHNtlHUcHUsTlAr2FouuzO4tJN77x7jY
# pAX7nPpTMA0GCSqGSIb3DQEBCwUABIICALivHaVpeXekA7OJfqMTKJhGwP4FxHad
# ZR53+1XLyUK2UGJPSxIrTH8O0P5XBiNOx72CWBxfmPYKaRa+zdq5a70vj6zvHzlU
# 0+ocE+wFT5dEAa2s5a0YJdwPk+mGWkF6jb5f3BVUKUDDaRRcFY7uWq+fKX2I+g4r
# GG2DkCII7eWVjDVIHoyMY6qEXi5mWAQ8TRQvDNoCYdMUusj1R3YbmzdhFnmvtGEz
# 8X4tFmoYXJdxAWQXGCHX/4/JqfsqNOkcmPB/Jt+8dfH5sx/ewtNFwiN1x5dcVAnL
# 3be8M0Sk2/raolhmcz4LHhf/d31Tx5AAsKydk1Dm6/8FmJq/T8jyzxjlnMRfsBi9
# LupxNBTz4z8TIWTCFufqvjeep3o1UnLVISnTC2lKxB+dC0Wwy7dtuPMqdinYH6C6
# /Y/Fw3BJXuWCfW92yCwZfnExcO0ci7fdjqrYckd0jEhC3iQGu4Uk+AhupthTI+Em
# H35X4y7535TLIKg/TTUUvFD38AUtgY7IIZQqvHkKCud9QbJutDHBD/N5/OWT59hU
# W1u5ylALiX40bpkGDILMmLgrm02CRxqOIcn9vq8ObK5WqlAOaUhm3IH8qLQyHYgZ
# LhjmrdV2QsW5clE76LRQBFfr9Wg6PdaHKlx2NOZRF++aL2ud1NdxcMM13I51fd/K
# sK7IszjHreqp
# SIG # End Windows Authenticode signature block