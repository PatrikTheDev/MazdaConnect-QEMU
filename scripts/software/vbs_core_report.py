"""Inspect a retained original VBS crash without executing firmware or GDB autoloads."""
import argparse
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run', type=Path)
parser.add_argument('--core', default='compositor.core', help='Pre-browser core filename in the retained run')
parser.add_argument('--thread', type=int, help='Select a GDB thread number after listing backtraces')
parser.add_argument('--frame', type=int, default=5)
args = parser.parse_args()
core = args.run / args.core
if not core.is_file():
    raise SystemExit('No retained core: ' + str(core))
description = subprocess.check_output(['file', str(core)], text=True)
print(description, end='', flush=True)
if 'sm_svclauncher -l jciVBS ' not in description:
    raise SystemExit('This recipe requires an identified original VBS launcher core')
command = ['gdb-multiarch', '-batch', '-ex', 'set auto-load python-scripts off',
           '-ex', 'set sysroot /software/sysroot',
           '-ex', 'file /software/sysroot/jci/sm/sm_svclauncher',
           '-ex', 'core-file ' + str(core), '-ex', 'thread apply all bt 7']
if args.thread is not None:
    if args.thread < 1 or args.frame < 0:
        parser.error('Require positive --thread and nonnegative --frame')
    command += ['-ex', f'thread {args.thread}', '-ex', f'frame {args.frame}',
                '-ex', 'info frame', '-ex', 'x/18wx $sp']
subprocess.run(command, check=True)
