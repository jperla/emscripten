#!/usr/bin/env python

'''
emmaken - the emscripten make proxy tool
========================================

Tell your build system to use this instead of the compiler, linker, ar and
ranlib. All the normal build commands will be sent to this script, which
will proxy them to the appropriate LLVM build commands, in order to
generate proper code for Emscripten to later process.

For example, compilation will be translated into calls to llvm-gcc
with -emit-llvm, and linking will be translated into calls to llvm-link,
and so forth.

Example uses:

 * With configure, do something like

    RANLIB=PATH/emmaken.py AR=PATH/emmaken.py CXX=PATH/emmaken.py CC=PATH/emmaken.py ./configure [options]

   where PATH is the path to this file.

 * With CMake, do something like

    SET(CMAKE_C_COMPILER "PATH/emmaken.py")
    SET(CMAKE_CXX_COMPILER "PATH/emmaken.py")
    SET(CMAKE_LINKER "PATH/emmaken.py")
    SET(CMAKE_CXX_LINKER "PATH/emmaken.py")
    SET(CMAKE_C_LINK_EXECUTABLE "PATH/emmaken.py")
    SET(CMAKE_CXX_LINK_EXECUTABLE "PATH/emmaken.py")
    SET(CMAKE_AR "PATH/emmaken.py")
    SET(CMAKE_RANLIB "PATH/emmaken.py")

After setting that up, run your build system normally. It should generate
LLVM instead of the normal output, and end up with .ll files that you can
give to Emscripten. Note that this tool doesn't run Emscripten itself. Note
also that you may need to do some manual fiddling later, for example to
link files that weren't linked, and them llvm-dis them.
'''

import sys
import os
import subprocess

abspath = os.path.abspath(os.path.dirname(__file__))
def path_from_root(*pathelems):
  return os.path.join(os.path.sep, *(abspath.split(os.sep)[:-1] + list(pathelems)))
exec(open(path_from_root('tools', 'shared.py'), 'r').read())

try:
  print >> sys.stderr, 'emmaken.py: ', ' '.join(sys.argv)

  CXX = os.environ.get('EMMAKEN_COMPILER') or LLVM_GCC
  CC = to_cc(CXX)

  CC_ARG_SKIP = ['-O1', '-O2', '-O3']
  CC_ADDITIONAL_ARGS = ['-m32', '-U__i386__', '-U__x86_64__', '-UX87_DOUBLE_ROUNDING', '-UHAVE_GCC_ASM_FOR_X87']
  ALLOWED_LINK_ARGS = ['-f', '-help', '-o', '-print-after', '-print-after-all', '-print-before',
                       '-print-before-all', '-time-passes', '-v', '-verify-dom-info', '-version' ]  
  DISALLOWED_LINK_ARGS = []#['rc']

  # ----------------  End configs -------------

  if len(sys.argv) == 2 and 'conftest' not in ' '.join(sys.argv): # Avoid messing with configure, see below too
    # ranlib
    os.execvp(LLVM_DIS, ['-show-annotations', sys.argv[1]])
    sys.exit(0)
  if sys.argv[1] in ['x', 't']:
    # noop ar
    sys.exit(0)

  use_cxx = True
  use_linker = True

  opts = []
  files = []
  for arg in sys.argv[1:]:
      if arg.startswith('-'):
          opts.append(arg)
      else:
          files.append(arg)
          if arg.endswith('.c'):
              use_cxx = False
          if arg.endswith(('.c', '.cc', '.cpp')):
              use_linker = False
              
  if '--version' in opts:
      use_linker = False

  if sys.argv[1] in ['cru', 'rc']: # ar
    sys.argv = sys.argv[:1] + sys.argv[3:] + ['-o='+sys.argv[2]]
    assert use_linker, 'Linker should be used in this case'

  if use_linker:
      call = LLVM_LINK
      newargs = []
      found_o = False
      for arg in sys.argv[1:]:
          if found_o:
              newargs.append('-o=%s' % arg)
              found_o = False
              continue
          if arg.startswith('-'):
              if arg == '-o':
                  found_o = True
                  continue
              prefix = arg.split('=')[0]
              if prefix in ALLOWED_LINK_ARGS:
                  newargs.append(arg)
          elif arg.endswith('.so'):
              continue # .so's do not exist yet, in many cases
          else:
              # not option, so just append
              if arg not in DISALLOWED_LINK_ARGS:
                  newargs.append(arg)
  else:
      call = CXX if use_cxx else CC
      newargs = [ arg for arg in sys.argv[1:] if arg not in CC_ARG_SKIP ] + CC_ADDITIONAL_ARGS
      if 'conftest.c' not in files:
          newargs.append('-emit-llvm')
          if not use_linker:
              newargs.append('-c') 

  print >> sys.stderr, "Running:", call, ' '.join(newargs)

  os.execvp(call, [call] + newargs)
except:
  print 'Error in emmaken.py. Is the config file ~/.emscripten set up properly?'
  raise
