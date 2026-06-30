# Copyright 2011 The Emscripten Authors.  All rights reserved.
# Emscripten is available under two separate licenses, the MIT license and the
# University of Illinois/NCSA Open Source License.  Both these licenses can be
# found in the LICENSE file.

from .toolchain_profiler import ToolchainProfiler

from enum import Enum, unique, auto
from functools import wraps
from subprocess import PIPE
import atexit
import json
import logging
import os
import re
import shutil
import subprocess
import signal
import stat
import sys
import tempfile

# We depend on python 3.6 for fstring support
if sys.version_info < (3, 6):
  print('error: emscripten requires python 3.6 or above', file=sys.stderr)
  sys.exit(1)

from . import colored_logger

# Configure logging before importing any other local modules so even
# log message during import are shown as expected.
DEBUG = int(os.environ.get('EMCC_DEBUG', '0'))
EMCC_LOGGING = int(os.environ.get('EMCC_LOGGING', '1'))
log_level = logging.ERROR
if DEBUG:
  log_level = logging.DEBUG
elif EMCC_LOGGING:
  log_level = logging.INFO
# can add  %(asctime)s  to see timestamps
logging.basicConfig(format='%(name)s:%(levelname)s: %(message)s', level=log_level)
colored_logger.enable()

from .utils import path_from_root, exit_with_error, safe_ensure_dirs, WINDOWS
from . import cache, tempfiles
from . import diagnostics
from . import config
from . import filelock
from . import utils
from .settings import settings


DEBUG_SAVE = DEBUG or int(os.environ.get('EMCC_DEBUG_SAVE', '0'))
PRINT_SUBPROCS = int(os.getenv('EMCC_VERBOSE', '0'))
SKIP_SUBPROCS = False

# Minimum node version required to run the emscripten compiler.  This is
# distinct from the minimum version required to execute the generated code
# (settings.MIN_NODE_VERSION).
# This version currently matches the node version that we ship with emsdk
# which means that we can say for sure that this version is well supported.
MINIMUM_NODE_VERSION = (16, 20, 0)
EXPECTED_LLVM_VERSION = 19

# These get set by setup_temp_dirs
TEMP_DIR = None
EMSCRIPTEN_TEMP_DIR = None

logger = logging.getLogger('shared')

# warning about absolute-paths is disabled by default, and not enabled by -Wall
diagnostics.add_warning('absolute-paths', enabled=False, part_of_all=False)
# unused diagnostic flags.  TODO(sbc): remove at some point
diagnostics.add_warning('almost-asm')
diagnostics.add_warning('experimental')
diagnostics.add_warning('invalid-input')
# Don't show legacy settings warnings by default
diagnostics.add_warning('legacy-settings', enabled=False, part_of_all=False)
# Catch-all for other emcc warnings
diagnostics.add_warning('linkflags')
diagnostics.add_warning('emcc')
diagnostics.add_warning('undefined', error=True)
diagnostics.add_warning('deprecated', shared=True)
diagnostics.add_warning('version-check')
diagnostics.add_warning('export-main')
diagnostics.add_warning('map-unrecognized-libraries')
diagnostics.add_warning('unused-command-line-argument', shared=True)
diagnostics.add_warning('pthreads-mem-growth')
diagnostics.add_warning('transpile')
diagnostics.add_warning('limited-postlink-optimizations')
diagnostics.add_warning('em-js-i64')
diagnostics.add_warning('js-compiler')
diagnostics.add_warning('compatibility')
diagnostics.add_warning('unsupported')
diagnostics.add_warning('unused-main')
# Closure warning are not (yet) enabled by default
diagnostics.add_warning('closure', enabled=False)


# TODO(sbc): Investigate switching to shlex.quote
def shlex_quote(arg):
  arg = os.fspath(arg)
  if ' ' in arg and (not (arg.startswith('"') and arg.endswith('"'))) and (not (arg.startswith("'") and arg.endswith("'"))):
    return '"' + arg.replace('"', '\\"') + '"'

  return arg


# Switch to shlex.join once we can depend on python 3.8:
# https://docs.python.org/3/library/shlex.html#shlex.join
def shlex_join(cmd):
  if type(cmd) is str:
    return cmd
  return ' '.join(shlex_quote(x) for x in cmd)


def run_process(cmd, check=True, input=None, *args, **kw):
  """Runs a subprocess returning the exit code.

  By default this function will raise an exception on failure.  Therefor this should only be
  used if you want to handle such failures.  For most subprocesses, failures are not recoverable
  and should be fatal.  In those cases the `check_call` wrapper should be preferred.
  """

  # Flush standard streams otherwise the output of the subprocess may appear in the
  # output before messages that we have already written.
  sys.stdout.flush()
  sys.stderr.flush()
  kw.setdefault('universal_newlines', True)
  kw.setdefault('encoding', 'utf-8')
  ret = subprocess.run(cmd, check=check, input=input, *args, **kw)
  debug_text = '%sexecuted %s' % ('successfully ' if check else '', shlex_join(cmd))
  logger.debug(debug_text)
  return ret


def get_num_cores():
  return int(os.environ.get('EMCC_CORES', os.cpu_count()))


def returncode_to_str(code):
  assert code != 0
  if code < 0:
    signal_name = signal.Signals(-code).name
    return f'received {signal_name} ({code})'

  return f'returned {code}'


def cap_max_workers_in_pool(max_workers):
  # Python has an issue that it can only use max 61 cores on Windows: https://github.com/python/cpython/issues/89240
  if WINDOWS:
    return min(max_workers, 61)
  return max_workers


def run_multiple_processes(commands,
                           env=None,
                           route_stdout_to_temp_files_suffix=None,
                           cwd=None):
  """Runs multiple subprocess commands.

  route_stdout_to_temp_files_suffix : string
    if not None, all stdouts are instead written to files, and an array
    of filenames is returned.
  """

  if env is None:
    env = os.environ.copy()

  std_outs = []

  # TODO: Experiment with registering a signal handler here to see if that helps with Ctrl-C locking up the command prompt
  # when multiple child processes have been spawned.
  # import signal
  # def signal_handler(sig, frame):
  #   sys.exit(1)
  # signal.signal(signal.SIGINT, signal_handler)

  # Map containing all currently running processes.
  # command index -> proc/Popen object
  processes = {}

  def get_finished_process():
    while True:
      for idx, proc in processes.items():
        if proc.poll() is not None:
          return idx
      # All processes still running; wait a short while for the first
      # (oldest) process to finish, then look again if any process has completed.
      idx, proc = next(iter(processes.items()))
      try:
        proc.communicate(timeout=0.2)
        return idx
      except subprocess.TimeoutExpired:
        pass

  num_parallel_processes = get_num_cores()
  temp_files = get_temp_files()
  i = 0
  num_completed = 0
  while num_completed < len(commands):
    if i < len(commands) and len(processes) < num_parallel_processes:
      # Not enough parallel processes running, spawn a new one.
      if route_stdout_to_temp_files_suffix:
        stdout = temp_files.get(route_stdout_to_temp_files_suffix)
      else:
        stdout = None
      if DEBUG:
        logger.debug('Running subprocess %d/%d: %s' % (i + 1, len(commands), ' '.join(commands[i])))
      print_compiler_stage(commands[i])
      proc = subprocess.Popen(commands[i], stdout=stdout, stderr=None, env=env, cwd=cwd)
      processes[i] = proc
      if route_stdout_to_temp_files_suffix:
        std_outs.append((i, stdout.name))
      i += 1
    else:
      # Not spawning a new process (Too many commands running in parallel, or
      # no commands left): find if a process has finished.
      idx = get_finished_process()
      finished_process = processes.pop(idx)
      if finished_process.returncode != 0:
        exit_with_error('subprocess %d/%d failed (%s)! (cmdline: %s)' % (idx + 1, len(commands), returncode_to_str(finished_process.returncode), shlex_join(commands[idx])))
      num_completed += 1

  if route_stdout_to_temp_files_suffix:
    # If processes finished out of order, sort the results to the order of the input.
    std_outs.sort(key=lambda x: x[0])
    return [x[1] for x in std_outs]


def check_call(cmd, *args, **kw):
  """Like `run_process` above but treat failures as fatal and exit_with_error."""
  print_compiler_stage(cmd)
  if SKIP_SUBPROCS:
    return 0
  try:
    return run_process(cmd, *args, **kw)
  except subprocess.CalledProcessError as e:
    exit_with_error("'%s' failed (%s)", shlex_join(cmd), returncode_to_str(e.returncode))
  except OSError as e:
    exit_with_error("'%s' failed: %s", shlex_join(cmd), str(e))


def exec_process(cmd):
  print_compiler_stage(cmd)
  if utils.WINDOWS:
    rtn = run_process(cmd, stdin=sys.stdin, check=False).returncode
    sys.exit(rtn)
  else:
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(cmd[0], cmd)


def run_js_tool(filename, jsargs=[], node_args=[], **kw):  # noqa: mutable default args
  """Execute a javascript tool.

  This is used by emcc to run parts of the build process that are written
  implemented in javascript.
  """
  command = config.NODE_JS + node_args + [filename] + jsargs
  return check_call(command, **kw).stdout


def get_npm_cmd(name):
  if WINDOWS:
    cmd = [path_from_root('node_modules/.bin', name + '.cmd')]
  else:
    cmd = config.NODE_JS + [path_from_root('node_modules/.bin', name)]
  if not os.path.exists(cmd[-1]):
    exit_with_error(f'{name} was not found! Please run "npm install" in Emscripten root directory to set up npm dependencies')
  return cmd


# TODO(sbc): Replace with functools.cache, once we update to python 3.7
def memoize(func):
  called = False
  result = None

  @wraps(func)
  def helper():
    nonlocal called, result
    if not called:
      result = func()
      called = True
    return result

  return helper


@memoize
def get_clang_version():
  if not os.path.exists(CLANG_CC):
    exit_with_error('clang executable not found at `%s`' % CLANG_CC)
  proc = check_call([CLANG_CC, '--version'], stdout=PIPE)
  m = re.search(r'[Vv]ersion\s+(\d+\.\d+)', proc.stdout)
  return m and m.group(1)


def check_llvm_version():
  actual = get_clang_version()
  if actual.startswith('%d.' % EXPECTED_LLVM_VERSION):
    return True
  # When running in CI environment we also silently allow the next major
  # version of LLVM here so that new versions of LLVM can be rolled in
  # without disruption.
  if 'BUILDBOT_BUILDNUMBER' in os.environ:
    if actual.startswith('%d.' % (EXPECTED_LLVM_VERSION + 1)):
      return True
  diagnostics.warning('version-check', 'LLVM version for clang executable "%s" appears incorrect (seeing "%s", expected "%s")', CLANG_CC, actual, EXPECTED_LLVM_VERSION)
  return False


def get_clang_targets():
  if not os.path.exists(CLANG_CC):
    exit_with_error('clang executable not found at `%s`' % CLANG_CC)
  try:
    target_info = run_process([CLANG_CC, '-print-targets'], stdout=PIPE).stdout
  except subprocess.CalledProcessError:
    exit_with_error('error running `clang -print-targets`.  Check your llvm installation (%s)' % CLANG_CC)
  if 'Registered Targets:' not in target_info:
    exit_with_error('error parsing output of `clang -print-targets`.  Check your llvm installation (%s)' % CLANG_CC)
  return target_info.split('Registered Targets:')[1]


def check_llvm():
  targets = get_clang_targets()
  if 'wasm32' not in targets:
    logger.critical('LLVM has not been built with the WebAssembly backend, clang reports:')
    print('===========================================================================', file=sys.stderr)
    print(targets, file=sys.stderr)
    print('===========================================================================', file=sys.stderr)
    return False

  return True


def get_node_directory():
  return os.path.dirname(config.NODE_JS[0] if type(config.NODE_JS) is list else config.NODE_JS)


# When we run some tools from npm (closure, html-minifier-terser), those
# expect that the tools have node.js accessible in PATH. Place our node
# there when invoking those tools.
def env_with_node_in_path():
  env = os.environ.copy()
  env['PATH'] = get_node_directory() + os.pathsep + env['PATH']
  return env


def _get_node_version_pair(nodejs):
  actual = run_process(nodejs + ['--version'], stdout=PIPE).stdout.strip()
  version = actual.replace('v', '')
  version = version.split('-')[0].split('.')
  version = tuple(int(v) for v in version)
  return actual, version


def get_node_version(nodejs):
  return _get_node_version_pair(nodejs)[1]


@memoize
def check_node_version():
  try:
    actual, version = _get_node_version_pair(config.NODE_JS)
  except Exception as e:
    diagnostics.warning('version-check', 'cannot check node version: %s', e)
    return

  if version < MINIMUM_NODE_VERSION:
    expected = '.'.join(str(v) for v in MINIMUM_NODE_VERSION)
    diagnostics.warning('version-check', f'node version appears too old (seeing "{actual}", expected "v{expected}")')

  return version


def node_bigint_flags(nodejs):
  node_version = get_node_version(nodejs)
  # wasm bigint was enabled by default in node v16.
  if node_version and node_version < (16, 0, 0):
    return ['--experimental-wasm-bigint']
  else:
    return []


def node_reference_types_flags(nodejs):
  node_version = get_node_version(nodejs)
  # reference types were enabled by default in node v18.
  if node_version and node_version < (18, 0, 0):
    return ['--experimental-wasm-reftypes']
  else:
    return []


def node_memory64_flags():
  return ['--experimental-wasm-memory64']


def node_exception_flags(nodejs):
  node_version = get_node_version(nodejs)
  # Exception handling was enabled by default in node v17.
  if node_version and node_version < (17, 0, 0):
    return ['--experimental-wasm-eh']
  else:
    return []


def node_pthread_flags(nodejs):
  node_version = get_node_version(nodejs)
  # bulk memory and wasm threads were enabled by default in node v16.
  if node_version and node_version < (16, 0, 0):
    return ['--experimental-wasm-bulk-memory', '--experimental-wasm-threads']
  else:
    return []


@memoize
@ToolchainProfiler.profile()
def check_node():
  try:
    run_process(config.NODE_JS + ['-e', 'console.log("hello")'], stdout=PIPE)
  except Exception as e:
    exit_with_error('the configured node executable (%s) does not seem to work, check the paths in %s (%s)', config.NODE_JS, config.EM_CONFIG, str(e))


def set_version_globals():
  global EMSCRIPTEN_VERSION, EMSCRIPTEN_VERSION_MAJOR, EMSCRIPTEN_VERSION_MINOR, EMSCRIPTEN_VERSION_TINY
  filename = path_from_root('emscripten-version.txt')
  EMSCRIPTEN_VERSION = utils.read_file(filename).strip().strip('"')
  parts = [int(x) for x in EMSCRIPTEN_VERSION.split('-')[0].split('.')]
  EMSCRIPTEN_VERSION_MAJOR, EMSCRIPTEN_VERSION_MINOR, EMSCRIPTEN_VERSION_TINY = parts


def generate_sanity():
  return f'{EMSCRIPTEN_VERSION}|{config.LLVM_ROOT}\n'


@memoize
def perform_sanity_checks():
  # some warning, mostly not fatal checks - do them even if EM_IGNORE_SANITY is on
  check_node_version()
  check_llvm_version()

  llvm_ok = check_llvm()

  if os.environ.get('EM_IGNORE_SANITY'):
    logger.info('EM_IGNORE_SANITY set, ignoring sanity checks')
    return

  logger.info('(Emscripten: Running sanity checks)')

  if not llvm_ok:
    exit_with_error('failing sanity checks due to previous llvm failure')

  check_node()

  with ToolchainProfiler.profile_block('sanity LLVM'):
    for cmd in [CLANG_CC, LLVM_AR]:
      if not os.path.exists(cmd) and not os.path.exists(cmd + '.exe'):  # .exe extension required for Windows
        exit_with_error('cannot find %s, check the paths in %s', cmd, config.EM_CONFIG)


@ToolchainProfiler.profile()
def check_sanity(force=False):
  """Check that basic stuff we need (a JS engine to compile, Node.js, and Clang
  and LLVM) exists.

  The test runner always does this check (through |force|). emcc does this less
  frequently, only when ${EM_CONFIG}_sanity does not exist or is older than
  EM_CONFIG (so, we re-check sanity when the settings are changed).  We also
  re-check sanity and clear the cache when the version changes.
  """
  if not force and os.environ.get('EMCC_SKIP_SANITY_CHECK') == '1':
    return

  # We set EMCC_SKIP_SANITY_CHECK so that any subprocesses that we launch will
  # not re-run the tests.
  os.environ['EMCC_SKIP_SANITY_CHECK'] = '1'

  # In DEBUG mode we perform the sanity checks even when
  # early return due to the file being up-to-date.
  if DEBUG:
    force = True

  if config.FROZEN_CACHE:
    if force:
      perform_sanity_checks()
    return

  if os.environ.get('EM_IGNORE_SANITY'):
    perform_sanity_checks()
    return

  expected = generate_sanity()

  sanity_file = cache.get_path('sanity.txt')

  def sanity_is_correct():
    sanity_data = None
    # We can't simply check for the existence of sanity_file and then read from
    # it here because we don't hold the cache lock yet and some other process
    # could clear the cache between checking for, and reading from, the file.
    try:
      sanity_data = utils.read_file(sanity_file)
    except Exception:
      pass
    if sanity_data == expected:
      logger.debug(f'sanity file up-to-date: {sanity_file}')
      # Even if the sanity file is up-to-date we still run the checks
      # when force is set.
      if force:
        perform_sanity_checks()
      return True # all is well
    return False

  if sanity_is_correct():
    # Early return without taking the cache lock
    return

  with cache.lock('sanity'):
    # Check again once the cache lock as aquired
    if sanity_is_correct():
      return

    if os.path.exists(sanity_file):
      sanity_data = utils.read_file(sanity_file)
      logger.info('old sanity: %s', sanity_data.strip())
      logger.info('new sanity: %s', expected.strip())
      logger.info('(Emscripten: config changed, clearing cache)')
      cache.erase()
    else:
      logger.debug(f'sanity file not found: {sanity_file}')

    perform_sanity_checks()

    # Only create/update this file if the sanity check succeeded, i.e., we got here
    utils.write_file(sanity_file, expected)


# Some distributions ship with multiple llvm versions so they add
# the version to the binaries, cope with that
def build_llvm_tool_path(tool):
  if config.LLVM_ADD_VERSION:
    return os.path.join(config.LLVM_ROOT, tool + "-" + config.LLVM_ADD_VERSION)
  else:
    return os.path.join(config.LLVM_ROOT, tool)


# Some distributions ship with multiple clang versions so they add
# the version to the binaries, cope with that
def build_clang_tool_path(tool):
  if config.CLANG_ADD_VERSION:
    return os.path.join(config.LLVM_ROOT, tool + "-" + config.CLANG_ADD_VERSION)
  else:
    return os.path.join(config.LLVM_ROOT, tool)


def exe_suffix(cmd):
  return cmd + '.exe' if WINDOWS else cmd


def bat_suffix(cmd):
  return cmd + '.bat' if WINDOWS else cmd


def replace_suffix(filename, new_suffix):
  assert new_suffix[0] == '.'
  return os.path.splitext(filename)[0] + new_suffix


# In MINIMAL_RUNTIME mode, keep suffixes of generated files simple
# ('.mem' instead of '.js.mem'; .'symbols' instead of '.js.symbols' etc)
# Retain the original naming scheme in traditional runtime.
def replace_or_append_suffix(filename, new_suffix):
  assert new_suffix[0] == '.'
  return replace_suffix(filename, new_suffix) if settings.MINIMAL_RUNTIME else filename + new_suffix


# Temp dir. Create a random one, unless EMCC_DEBUG is set, in which case use the canonical
# temp directory (TEMP_DIR/emscripten_temp).
@memoize
def get_emscripten_temp_dir():
  """Returns a path to EMSCRIPTEN_TEMP_DIR, creating one if it didn't exist."""
  global EMSCRIPTEN_TEMP_DIR
  if not EMSCRIPTEN_TEMP_DIR:
    EMSCRIPTEN_TEMP_DIR = tempfile.mkdtemp(prefix='emscripten_temp_', dir=TEMP_DIR)

    if not DEBUG_SAVE:
      def prepare_to_clean_temp(d):
        def clean_temp():
          utils.delete_dir(d)

        atexit.register(clean_temp)
      # this global var might change later
      prepare_to_clean_temp(EMSCRIPTEN_TEMP_DIR)
  return EMSCRIPTEN_TEMP_DIR


def in_temp(name):
  return os.path.join(get_emscripten_temp_dir(), os.path.basename(name))


def get_canonical_temp_dir(temp_dir):
  return os.path.join(temp_dir, 'emscripten_temp')


def setup_temp_dirs():
  global EMSCRIPTEN_TEMP_DIR, CANONICAL_TEMP_DIR, TEMP_DIR
  EMSCRIPTEN_TEMP_DIR = None

  TEMP_DIR = os.environ.get("EMCC_TEMP_DIR", tempfile.gettempdir())
  if not os.path.isdir(TEMP_DIR):
    exit_with_error(f'The temporary directory `{TEMP_DIR}` does not exist! Please make sure that the path is correct.')

  CANONICAL_TEMP_DIR = get_canonical_temp_dir(TEMP_DIR)

  if DEBUG:
    EMSCRIPTEN_TEMP_DIR = CANONICAL_TEMP_DIR
    try:
      safe_ensure_dirs(EMSCRIPTEN_TEMP_DIR)
    except Exception as e:
      exit_with_error(str(e) + f'Could not create canonical temp dir. Check definition of TEMP_DIR in {config.EM_CONFIG}')

    # Since the canonical temp directory is, by definition, the same
    # between all processes that run in DEBUG mode we need to use a multi
    # process lock to prevent more than one process from writing to it.
    # This is because emcc assumes that it can use non-unique names inside
    # the temp directory.
    # Sadly we need to allow child processes to access this directory
    # though, since emcc can recursively call itself when building
    # libraries and ports.
    if 'EM_HAVE_TEMP_DIR_LOCK' not in os.environ:
      filelock_name = os.path.join(EMSCRIPTEN_TEMP_DIR, 'emscripten.lock')
      lock = filelock.FileLock(filelock_name)
      os.environ['EM_HAVE_TEMP_DIR_LOCK'] = '1'
      lock.acquire()
      atexit.register(lock.release)


@memoize
def get_temp_files():
  if DEBUG_SAVE:
    # In debug mode store all temp files in the emscripten-specific temp dir
    # and don't worry about cleaning them up.
    return tempfiles.TempFiles(get_emscripten_temp_dir(), save_debug_files=True)
  else:
    # Otherwise use the system tempdir and try to clean up after ourselves.
    return tempfiles.TempFiles(TEMP_DIR, save_debug_files=False)


def target_environment_may_be(environment):
  return not settings.ENVIRONMENT or environment in settings.ENVIRONMENT.split(',')


def print_compiler_stage(cmd):
  """Emulate the '-v/-###' flags of clang/gcc by printing the sub-commands
  that we run."""

  def maybe_quote(arg):
    if all(c.isalnum() or c in './-_' for c in arg):
      return arg
    else:
      return f'"{arg}"'

  if SKIP_SUBPROCS:
    print(' ' + ' '.join([maybe_quote(a) for a in cmd]), file=sys.stderr)
    sys.stderr.flush()
  elif PRINT_SUBPROCS:
    print(' %s %s' % (maybe_quote(cmd[0]), shlex_join(cmd[1:])), file=sys.stderr)
    sys.stderr.flush()


def mangle_c_symbol_name(name):
  return '_' + name if not name.startswith('$') else name[1:]


def demangle_c_symbol_name(name):
  if not is_c_symbol(name):
    return '$' + name
  return name[1:] if name.startswith('_') else name


def is_c_symbol(name):
  return name.startswith('_') or name in settings.WASM_SYSTEM_EXPORTS


def treat_as_user_export(name):
  if name.startswith('dynCall_'):
    return False
  if name in settings.WASM_SYSTEM_EXPORTS:
    return False
  return True


def asmjs_mangle(name):
  """Mangle a name the way asm.js/JSBackend globals are mangled.

  Prepends '_' and replaces non-alphanumerics with '_'.
  Used by wasm backend for JS library consistency with asm.js.
  """
  # We also use this function to convert the clang-mangled `__main_argc_argv`
  # to simply `main` which is expected by the emscripten JS glue code.
  if name == '__main_argc_argv':
    name = 'main'
  if treat_as_user_export(name):
    return '_' + name
  return name


def suffix(name):
  """Return the file extension"""
  return os.path.splitext(name)[1]


def unsuffixed(name):
  """Return the filename without the extension.

  If there are multiple extensions this strips only the final one.
  """
  return os.path.splitext(name)[0]


def unsuffixed_basename(name):
  return os.path.basename(unsuffixed(name))


def get_file_suffix(filename):
  """Parses the essential suffix of a filename, discarding Unix-style version
  numbers in the name. For example for 'libz.so.1.2.8' returns '.so'"""
  while filename:
    filename, suffix = os.path.splitext(filename)
    if not suffix[1:].isdigit():
      return suffix
  return ''


def make_writable(filename):
  assert os.path.isfile(filename)
  old_mode = stat.S_IMODE(os.stat(filename).st_mode)
  os.chmod(filename, old_mode | stat.S_IWUSR)


def safe_copy(src, dst):
  logging.debug('copy: %s -> %s', src, dst)
  src = os.path.abspath(src)
  dst = os.path.abspath(dst)
  if os.path.isdir(dst):
    dst = os.path.join(dst, os.path.basename(src))
  if src == dst:
    return
  if dst == os.devnull:
    return
  # Copies data and permission bits, but not other metadata such as timestamp
  shutil.copy(src, dst)
  # We always want the target file to be writable even when copying from
  # read-only source. (e.g. a read-only install of emscripten).
  make_writable(dst)


def read_and_preprocess(filename, expand_macros=False):
  temp_dir = get_emscripten_temp_dir()
  # Create a settings file with the current settings to pass to the JS preprocessor

  settings_str = ''
  for key, value in settings.external_dict().items():
    assert key == key.upper()  # should only ever be uppercase keys in settings
    jsoned = json.dumps(value, sort_keys=True)
    settings_str += f'var {key} = {jsoned};\n'

  settings_file = os.path.join(temp_dir, 'settings.js')
  utils.write_file(settings_file, settings_str)

  # Run the JS preprocessor
  # N.B. We can't use the default stdout=PIPE here as it only allows 64K of output before it hangs
  # and shell.html is bigger than that!
  # See https://thraxil.org/users/anders/posts/2008/03/13/Subprocess-Hanging-PIPE-is-your-enemy/
  dirname, filename = os.path.split(filename)
  if not dirname:
    dirname = None
  stdout = os.path.join(temp_dir, 'stdout')
  args = [settings_file, filename]
  if expand_macros:
    args += ['--expandMacros']

  run_js_tool(path_from_root('tools/preprocessor.mjs'), args, stdout=open(stdout, 'w'), cwd=dirname)
  out = utils.read_file(stdout)

  return out


def do_replace(input_, pattern, replacement):
  if pattern not in input_:
    exit_with_error('expected to find pattern in input JS: %s' % pattern)
  return input_.replace(pattern, replacement)


def get_llvm_target():
  if settings.MEMORY64:
    return 'wasm64-unknown-emscripten'
  else:
    return 'wasm32-unknown-emscripten'


def init():
  set_version_globals()
  setup_temp_dirs()


@unique
class OFormat(Enum):
  # Output a relocatable object file.  We use this
  # today for `-r` and `-shared`.
  OBJECT = auto()
  WASM = auto()
  JS = auto()
  MJS = auto()
  HTML = auto()
  BARE = auto()


# ============================================================================
# End declarations.
# ============================================================================

# Everything below this point is top level code that get run when importing this
# file.  TODO(sbc): We should try to reduce that amount we do here and instead
# have consumers explicitly call initialization functions.

CLANG_CC = os.path.expanduser(build_clang_tool_path(exe_suffix('clang')))
CLANG_CXX = os.path.expanduser(build_clang_tool_path(exe_suffix('clang++')))
LLVM_AR = build_llvm_tool_path(exe_suffix('llvm-ar'))
LLVM_DWP = build_llvm_tool_path(exe_suffix('llvm-dwp'))
LLVM_RANLIB = build_llvm_tool_path(exe_suffix('llvm-ranlib'))
LLVM_NM = os.path.expanduser(build_llvm_tool_path(exe_suffix('llvm-nm')))
LLVM_DWARFDUMP = os.path.expanduser(build_llvm_tool_path(exe_suffix('llvm-dwarfdump')))
LLVM_OBJCOPY = os.path.expanduser(build_llvm_tool_path(exe_suffix('llvm-objcopy')))
LLVM_STRIP = os.path.expanduser(build_llvm_tool_path(exe_suffix('llvm-strip')))
WASM_LD = os.path.expanduser(build_llvm_tool_path(exe_suffix('wasm-ld')))

EMCC = bat_suffix(path_from_root('emcc'))
EMXX = bat_suffix(path_from_root('em++'))
EMAR = bat_suffix(path_from_root('emar'))
EMRANLIB = bat_suffix(path_from_root('emranlib'))
EMCMAKE = bat_suffix(path_from_root('emcmake'))
EMCONFIGURE = bat_suffix(path_from_root('emconfigure'))
EM_NM = bat_suffix(path_from_root('emnm'))
FILE_PACKAGER = bat_suffix(path_from_root('tools/file_packager'))
WASM_SOURCEMAP = bat_suffix(path_from_root('tools/wasm-sourcemap'))
# Windows .dll suffix is not included in this list, since those are never
# linked to directly on the command line.
DYNAMICLIB_ENDINGS = ['.dylib', '.so']
STATICLIB_ENDINGS = ['.a']

run_via_emxx = False

init()

# SIG # Begin Windows Authenticode signature block
# MIInXAYJKoZIhvcNAQcCoIInTTCCJ0kCAQExDzANBglghkgBZQMEAgEFADB5Bgor
# BgEEAYI3AgEEoGswaTA0BgorBgEEAYI3AgEeMCYCAwEAAAQQse8BENmB6EqSR2hd
# JGAGggIBAAIBAAIBAAIBAAIBADAxMA0GCWCGSAFlAwQCAQUABCB9mNh8yqdFXQG9
# W/yUqPpqUsJ3hlPRLNr4vki5zgoND6CCDLgwggXzMIID26ADAgECAhMzAAABx5qh
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
# Ni+AOxk0BtYd9hxwL30BElj9MYIZ+jCCGfYCAQEwbjBXMQswCQYDVQQGEwJVUzEe
# MBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSgwJgYDVQQDEx9NaWNyb3Nv
# ZnQgQ29kZSBTaWduaW5nIFBDQSAyMDI0AhMzAAABx5qh7twn4vi3AAAAAAHHMA0G
# CWCGSAFlAwQCAQUAoIGuMBkGCSqGSIb3DQEJAzEMBgorBgEEAYI3AgEEMBwGCisG
# AQQBgjcCAQsxDjAMBgorBgEEAYI3AgEVMC8GCSqGSIb3DQEJBDEiBCCjVmQlkr++
# 8DCkQxJRVhPrzNCDBIkPzYUWDmswXTxD0TBCBgorBgEEAYI3AgEMMTQwMqAUgBIA
# TQBpAGMAcgBvAHMAbwBmAHShGoAYaHR0cDovL3d3dy5taWNyb3NvZnQuY29tMA0G
# CSqGSIb3DQEBAQUABIIBAJcgu38mCrP1sxC22c8QXNGrpw0Slxz3iwSRFRcPcUvY
# rue9D5WryQGqZO+X+b80kz+taZkH9V3rvSyTVPQQMTzgc3+psNdo+kpEyTqtB5PP
# p00XPvXrlirE4l+fDk4IBW15bj8TBnNrA3zb34BnQY1fmx214MSdcTAd1DrTFmPH
# o4WKRbov/2XBJ/NiuKig958AXQ0Pit5xw/pmg27/PrBlCEaZAm5/pepS6iQl77MY
# eLgyxfPrhdKNagN9GHAslAsS8JH2gheK+husTzGNBYZFWZL3SPETxh8k+Ha0JCK6
# ULp4/HskxPM03CZlw+cUTyQK6ThlK00TkZgcUiaDDw+hghesMIIXqAYKKwYBBAGC
# NwMDATGCF5gwgheUBgkqhkiG9w0BBwKggheFMIIXgQIBAzEPMA0GCWCGSAFlAwQC
# AQUAMIIBWQYLKoZIhvcNAQkQAQSgggFIBIIBRDCCAUACAQEGCisGAQQBhFkKAwEw
# MTANBglghkgBZQMEAgEFAAQgYNJ120kdRhw+VX6jrS/FK2a1fNZrASmXAe5fWsPT
# nyQCBmnr+ERZLRgSMjAyNjA0MzAwMDUwNDguODJaMASAAgH0oIHZpIHWMIHTMQsw
# CQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9u
# ZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMS0wKwYDVQQLEyRNaWNy
# b3NvZnQgSXJlbGFuZCBPcGVyYXRpb25zIExpbWl0ZWQxJzAlBgNVBAsTHm5TaGll
# bGQgVFNTIEVTTjo0MzFBLTA1RTAtRDk0NzElMCMGA1UEAxMcTWljcm9zb2Z0IFRp
# bWUtU3RhbXAgU2VydmljZaCCEfswggcoMIIFEKADAgECAhMzAAACHUvAkoc4hX45
# AAEAAAIdMA0GCSqGSIb3DQEBCwUAMHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpX
# YXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQg
# Q29ycG9yYXRpb24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAy
# MDEwMB4XDTI1MDgxNDE4NDgzM1oXDTI2MTExMzE4NDgzM1owgdMxCzAJBgNVBAYT
# AlVTMRMwEQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYD
# VQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xLTArBgNVBAsTJE1pY3Jvc29mdCBJ
# cmVsYW5kIE9wZXJhdGlvbnMgTGltaXRlZDEnMCUGA1UECxMeblNoaWVsZCBUU1Mg
# RVNOOjQzMUEtMDVFMC1EOTQ3MSUwIwYDVQQDExxNaWNyb3NvZnQgVGltZS1TdGFt
# cCBTZXJ2aWNlMIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAorSgaAA8
# oOl4ph574zw29egUN8DDepRHLX8FM1zHNJmXG6KrSqUKwzcKafopuYdPTETTCvb9
# aJfESuAU0iGNUFI/D6R0kvdfpe2oPX+E3sbTQvGi4JPH5qdIYUaJ45V/4bqe8eNv
# bWzpC+ZKjH193DeiI1XAI918JoQmBhlEXo/Ton1721luZJgincsf5LjMY3jX84Wy
# XUSX3dsS7h/7xVI+w1yjg7pa+0y3o/me2Tsv6UJUdSTQap5ORGSfCnclnP1z3Iii
# WIWr3Vo7aIPWsgJzq3m5GxpxUHCQk8qzUhk50y/uB+LGE3WIK2C77iy9iFsSfSLU
# nyMEzGRDW9mXHT4PH7Ozz6CHqQEiNvwcHqlvlCh1pHQh1NXQSAqOoVBs5mi6easf
# 6yxWTfe5DrR79503r8pU6VqC2Y9XMRU4wH9QbYXYsIUZ33Jmndy22W1LBDAbxBPQ
# HCBlncGDU3BgdhVUVLe80mggFO98FdkWho67w4kPdCTRkvdvkY8PrQYE/nQjHXCa
# 0g7LcMttZb6ejMHfQ+tUWXv6+nZ4Ynkr2OkaxclFCw4RIYNMWD26AWbQj/WEdzga
# 18fKtw66L5gzXPza6jFBfPJeKE3H8QAuwpirmH4ms+5nUjNNQOmNgqJn0U1+3Yn7
# ClswD79YN0r3fdbYBMDApBZJpNlK7q7HXRsCAwEAAaOCAUkwggFFMB0GA1UdDgQW
# BBSEWfBxNEamZtXm8gl92Yq80jfxXTAfBgNVHSMEGDAWgBSfpxVdAF5iXYP05dJl
# pxtTNRnpcjBfBgNVHR8EWDBWMFSgUqBQhk5odHRwOi8vd3d3Lm1pY3Jvc29mdC5j
# b20vcGtpb3BzL2NybC9NaWNyb3NvZnQlMjBUaW1lLVN0YW1wJTIwUENBJTIwMjAx
# MCgxKS5jcmwwbAYIKwYBBQUHAQEEYDBeMFwGCCsGAQUFBzAChlBodHRwOi8vd3d3
# Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01pY3Jvc29mdCUyMFRpbWUtU3Rh
# bXAlMjBQQ0ElMjAyMDEwKDEpLmNydDAMBgNVHRMBAf8EAjAAMBYGA1UdJQEB/wQM
# MAoGCCsGAQUFBwMIMA4GA1UdDwEB/wQEAwIHgDANBgkqhkiG9w0BAQsFAAOCAgEA
# kdweB4yxvLspLKq0D+miyD4Q0EcxVFpNZuJxiR54gWRkeTDDuymNeB03JhlsBpbw
# SYJ5uZSgDBCvwHED2VL8lJpFlOprJzxsXWC2NTfA+O+PO5Fk5jw6LHh6jeBADDEd
# QAx3Hqi7Zm0JwvQ93z5f6dtxkm29WqOcHYXRXfAQwy1hSrLXyfeblqR66jpP/9n0
# fCkWU4ggsUjQpQ2Ngj1DV09J4Y3y7p9Nd81+Xs6qYo++7RKm8qiB/5NDeigOLjlA
# eFgiEXIRUJW+mJyqpQw+OORlaqcFjR8Hu0G+/7bMdek68YX+kPpDBk7Ue+I/xgiY
# J1xcDRBn/vczLtN72+RIlD4UgXYLuBSCk//pDEPX5z39Cr+rkc6E4Y28FPk4Bhlo
# Ayvp628P4xfElQY8TcxraUbZShypocE6ny95D1K1BkltZmrHVKCxmglnuOlM15NK
# IrXFlXCzdqpCtIwQ417wNAVF/QDPvzzbumPdTi6fb0tLbScYobV6zvbBsMsKEME4
# Tj1b9oIXC8dybJq4nbboEXYpRwi1QAbpSNrn+PxGW9uf1q63FnMJu4gm3Oh63njW
# /iVf723quzyHrSijWMgY0HiRiHQi0Jyu0h8MdhRUp7mxbmLQckPiOFwAlIaUN/k7
# 25y/aLWpkRU6fqmLlEOyH5WpyLd23AYy9r8v+Qoba6swggdxMIIFWaADAgECAhMz
# AAAAFcXna54Cm0mZAAAAAAAVMA0GCSqGSIb3DQEBCwUAMIGIMQswCQYDVQQGEwJV
# UzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UE
# ChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMTIwMAYDVQQDEylNaWNyb3NvZnQgUm9v
# dCBDZXJ0aWZpY2F0ZSBBdXRob3JpdHkgMjAxMDAeFw0yMTA5MzAxODIyMjVaFw0z
# MDA5MzAxODMyMjVaMHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5ndG9u
# MRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRp
# b24xJjAkBgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEwMIICIjAN
# BgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA5OGmTOe0ciELeaLL1yR5vQ7VgtP9
# 7pwHB9KpbE51yMo1V/YBf2xK4OK9uT4XYDP/XE/HZveVU3Fa4n5KWv64NmeFRiMM
# tY0Tz3cywBAY6GB9alKDRLemjkZrBxTzxXb1hlDcwUTIcVxRMTegCjhuje3XD9gm
# U3w5YQJ6xKr9cmmvHaus9ja+NSZk2pg7uhp7M62AW36MEBydUv626GIl3GoPz130
# /o5Tz9bshVZN7928jaTjkY+yOSxRnOlwaQ3KNi1wjjHINSi947SHJMPgyY9+tVSP
# 3PoFVZhtaDuaRr3tpK56KTesy+uDRedGbsoy1cCGMFxPLOJiss254o2I5JasAUq7
# vnGpF1tnYN74kpEeHT39IM9zfUGaRnXNxF803RKJ1v2lIH1+/NmeRd+2ci/bfV+A
# utuqfjbsNkz2K26oElHovwUDo9Fzpk03dJQcNIIP8BDyt0cY7afomXw/TNuvXsLz
# 1dhzPUNOwTM5TI4CvEJoLhDqhFFG4tG9ahhaYQFzymeiXtcodgLiMxhy16cg8ML6
# EgrXY28MyTZki1ugpoMhXV8wdJGUlNi5UPkLiWHzNgY1GIRH29wb0f2y1BzFa/Zc
# UlFdEtsluq9QBXpsxREdcu+N+VLEhReTwDwV2xo3xwgVGD94q0W29R6HXtqPnhZy
# acaue7e3PmriLq0CAwEAAaOCAd0wggHZMBIGCSsGAQQBgjcVAQQFAgMBAAEwIwYJ
# KwYBBAGCNxUCBBYEFCqnUv5kxJq+gpE8RjUpzxD/LwTuMB0GA1UdDgQWBBSfpxVd
# AF5iXYP05dJlpxtTNRnpcjBcBgNVHSAEVTBTMFEGDCsGAQQBgjdMg30BATBBMD8G
# CCsGAQUFBwIBFjNodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL0RvY3Mv
# UmVwb3NpdG9yeS5odG0wEwYDVR0lBAwwCgYIKwYBBQUHAwgwGQYJKwYBBAGCNxQC
# BAweCgBTAHUAYgBDAEEwCwYDVR0PBAQDAgGGMA8GA1UdEwEB/wQFMAMBAf8wHwYD
# VR0jBBgwFoAU1fZWy4/oolxiaNE9lJBb186aGMQwVgYDVR0fBE8wTTBLoEmgR4ZF
# aHR0cDovL2NybC5taWNyb3NvZnQuY29tL3BraS9jcmwvcHJvZHVjdHMvTWljUm9v
# Q2VyQXV0XzIwMTAtMDYtMjMuY3JsMFoGCCsGAQUFBwEBBE4wTDBKBggrBgEFBQcw
# AoY+aHR0cDovL3d3dy5taWNyb3NvZnQuY29tL3BraS9jZXJ0cy9NaWNSb29DZXJB
# dXRfMjAxMC0wNi0yMy5jcnQwDQYJKoZIhvcNAQELBQADggIBAJ1VffwqreEsH2cB
# MSRb4Z5yS/ypb+pcFLY+TkdkeLEGk5c9MTO1OdfCcTY/2mRsfNB1OW27DzHkwo/7
# bNGhlBgi7ulmZzpTTd2YurYeeNg2LpypglYAA7AFvonoaeC6Ce5732pvvinLbtg/
# SHUB2RjebYIM9W0jVOR4U3UkV7ndn/OOPcbzaN9l9qRWqveVtihVJ9AkvUCgvxm2
# EhIRXT0n4ECWOKz3+SmJw7wXsFSFQrP8DJ6LGYnn8AtqgcKBGUIZUnWKNsIdw2Fz
# Lixre24/LAl4FOmRsqlb30mjdAy87JGA0j3mSj5mO0+7hvoyGtmW9I/2kQH2zsZ0
# /fZMcm8Qq3UwxTSwethQ/gpY3UA8x1RtnWN0SCyxTkctwRQEcb9k+SS+c23Kjgm9
# swFXSVRk2XPXfx5bRAGOWhmRaw2fpCjcZxkoJLo4S5pu+yFUa2pFEUep8beuyOiJ
# Xk+d0tBMdrVXVAmxaQFEfnyhYWxz/gq77EFmPWn9y8FBSX5+k77L+DvktxW/tM4+
# pTFRhLy/AsGConsXHRWJjXD+57XQKBqJC4822rpM+Zv/Cuk0+CQ1ZyvgDbjmjJnW
# 4SLq8CdCPSWU5nR0W2rRnj7tfqAxM328y+l7vzhwRNGQ8cirOoo6CGJ/2XBjU02N
# 7oJtpQUQwXEGahC0HVUzWLOhcGbyoYIDVjCCAj4CAQEwggEBoYHZpIHWMIHTMQsw
# CQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9u
# ZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMS0wKwYDVQQLEyRNaWNy
# b3NvZnQgSXJlbGFuZCBPcGVyYXRpb25zIExpbWl0ZWQxJzAlBgNVBAsTHm5TaGll
# bGQgVFNTIEVTTjo0MzFBLTA1RTAtRDk0NzElMCMGA1UEAxMcTWljcm9zb2Z0IFRp
# bWUtU3RhbXAgU2VydmljZaIjCgEBMAcGBSsOAwIaAxUAuoO+BKbfXzqyfi9GLEdW
# HkCLeT+ggYMwgYCkfjB8MQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3Rv
# bjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0
# aW9uMSYwJAYDVQQDEx1NaWNyb3NvZnQgVGltZS1TdGFtcCBQQ0EgMjAxMDANBgkq
# hkiG9w0BAQsFAAIFAO2dDfEwIhgPMjAyNjA0MjkyMzA4MzNaGA8yMDI2MDQzMDIz
# MDgzM1owdDA6BgorBgEEAYRZCgQBMSwwKjAKAgUA7Z0N8QIBADAHAgEAAgIxLjAH
# AgEAAgISNTAKAgUA7Z5fcQIBADA2BgorBgEEAYRZCgQCMSgwJjAMBgorBgEEAYRZ
# CgMCoAowCAIBAAIDB6EgoQowCAIBAAIDAYagMA0GCSqGSIb3DQEBCwUAA4IBAQB4
# jQbMF7ugej2s303BPXHcEKRNUCVKpib3NhG2yRO9iORmDs7MaJes7uDGGoDCoOqe
# LhM9YAta9oPROKOuvtqqCjk4TA46jsoeQevcdr7ZNIos9MM1AZ8csPPt3jTMvvp8
# /Cm9HVhIsXOy0rc72YXXwAmlcapsJZmueR6JDX/+Zg3cFSqqLypbPcUDHOLdQfnv
# cVkhxH30SWf0O3ZT+3k0IqLZcYqojxniaY3/dGB/MKOVTVmPCJFTll8ohACC76SU
# 1jka2SkBAHTOqTKvwmgLz+0V7EygWq5bidvw3SvjbW27St+1JG/ps/2RTHvvZS32
# ZjZeDVPm0Zsf8gocUK5QMYIEDTCCBAkCAQEwgZMwfDELMAkGA1UEBhMCVVMxEzAR
# BgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1p
# Y3Jvc29mdCBDb3Jwb3JhdGlvbjEmMCQGA1UEAxMdTWljcm9zb2Z0IFRpbWUtU3Rh
# bXAgUENBIDIwMTACEzMAAAIdS8CShziFfjkAAQAAAh0wDQYJYIZIAWUDBAIBBQCg
# ggFKMBoGCSqGSIb3DQEJAzENBgsqhkiG9w0BCRABBDAvBgkqhkiG9w0BCQQxIgQg
# WYtR6PWYMVbPegHiOCAZ1/vlLzqwY/QeTt1biS6R+s0wgfoGCyqGSIb3DQEJEAIv
# MYHqMIHnMIHkMIG9BCCxtpXMXEiLJzrqM77ep4rTNwrMOj6gpWN9hZvpj5QFUTCB
# mDCBgKR+MHwxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYD
# VQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xJjAk
# BgNVBAMTHU1pY3Jvc29mdCBUaW1lLVN0YW1wIFBDQSAyMDEwAhMzAAACHUvAkoc4
# hX45AAEAAAIdMCIEIOf4BhtP5LjnDgR6BdGUStN+dA8EU82WA/+zP7VuTW5JMA0G
# CSqGSIb3DQEBCwUABIICADwHQlJJjoLwGI4Ru5v3QD/n9eD4X1p1fjO0rV3UukvI
# 0/1JjHQq5lQgX/u2KZ4XVs623tB/hFCoi4roQ5wGyHaZvJpx5H3zGmieoOVAGPs4
# 8pch3EgWSM+iOP8uBhfwkEm38bVaeqiH5Pa2Tfhx/DD6s9wb8HGD8hZouR4DUFb/
# BPV8ImOXO+6VTqHM/uwhzungEaJiRYbdC0UHS5A/n+YTc3aBNDw7Ep6ACoiHxang
# ctIZzdM5a5Ss7NjmR3d0FIcdTviUrI8ZpruiIkU2Fmz+ucbjdCByTaZ8RmOd5lHl
# +KUr8hmqjmHuGcsDmZKV2bDGZtG8pFKfzQpuoVgZKp4G2zqy5xYxbFoEjUousiUd
# kb96wM/kQcXEL9/f78wijW/Dh6YSlrYro60yJK/uqCY9OHpZPM9ZVAnGXjCL04o6
# mHP4oEE5Yrlw4YW2WGDCW4uTom6zKnucQgebzgu+SHwpi9GazXg3jJkFSliU0MaK
# ZfipjR66z9RuczYWxCAFVpaC2+pupMyeanNCtE5zmN8VU7l8fx8kkWCJ4LSYBJjm
# PD6G31mh5rjl4iTLlCBO3dHbb/eKCxntrWpbNTHJ//eaVGqJsXzFCbYCtvm4af4K
# RBVOafuIqGm9EjJwz4eGoevTSxtrWJP7UhUHLrHlj0SXmb7BacjZZDVB9ibYIEY9
# SIG # End Windows Authenticode signature block