"""Serialize builds and runs that share the software lab's writable artifacts."""
import fcntl
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
if mode not in (*jobs, 'build'):
    raise SystemExit('Unknown software task: ' + mode)
Path('/software').mkdir(exist_ok=True)
lock = open('/software/active.lock', 'w')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit('Another software build or guest is active. Stop it before running this recipe.')
os.set_inheritable(lock.fileno(), True)
if mode != 'run':
    build = [sys.executable, 'scripts/software/build.py']
    if mode not in ('test', 'build'):
        build.append('--opera')
    subprocess.run(build, check=True)
if mode in jobs:
    script, defaults = jobs[mode]
    os.execv(sys.executable, [sys.executable, 'scripts/software/' + script, *defaults, *args])
