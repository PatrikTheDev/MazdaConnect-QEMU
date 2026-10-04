"""Serialize builds and runs that share the software lab's writable artifacts."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

mode, *args = sys.argv[1:]
jobs = {
    'boot': ('interactive.py', []), 'run': ('interactive.py', []),
    'test': ('check.py', []), 'opera': ('check.py', ['--opera']),
    'vnc': ('check_vnc.py', []),
}
if mode not in (*jobs, 'build', 'kernel'):
    raise SystemExit('Unknown software task: ' + mode)
Path('/software').mkdir(exist_ok=True)
lock = open('/software/active.lock', 'w')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit('Another software build or guest is active. Stop it before running this recipe.')
os.set_inheritable(lock.fileno(), True)
if mode == 'kernel':
    os.execv(sys.executable,[sys.executable,'scripts/software/build_kernel.py',*args])
kernel_profile = None
if '--kernel-profile' in args:
    index = args.index('--kernel-profile')
    if index+1 >= len(args) or args[index+1] not in ('stock','vmsplit2g'):
        raise SystemExit('--kernel-profile requires stock or vmsplit2g')
    kernel_profile = args[index+1]
    del args[index:index+2]
if mode == 'run' and kernel_profile is not None:
    built = json.loads(Path('/software/guest/profile.json').read_text())
    if built.get('kernel_profile','stock') != kernel_profile:
        raise SystemExit('Built profile differs; use just software-boot with the requested --kernel-profile')
if mode != 'run':
    build = [sys.executable, 'scripts/software/build.py']
    if kernel_profile is not None:
        build += ['--kernel-profile',kernel_profile]
    if mode not in ('test', 'build'):
        build.append('--opera')
    subprocess.run(build, check=True)
if mode in jobs:
    script, defaults = jobs[mode]
    os.execv(sys.executable, [sys.executable, 'scripts/software/' + script, *defaults, *args])
