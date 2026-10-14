"""Serialize builds and runs that share the software lab's writable artifacts."""
import fcntl
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from runtime import instance_name, snapshot

mode, *args = sys.argv[1:]
jobs = {
    'boot': ('interactive.py', []), 'run': ('interactive.py', []),
    'test': ('check.py', []), 'opera': ('check.py', ['--opera']),
    'vnc': ('check_vnc.py', []),
}
if mode not in (*jobs, 'build', 'build-ui', 'kernel'):
    raise SystemExit('Unknown software task: ' + mode)
Path('/software').mkdir(exist_ok=True)
if mode in ('boot', 'run'):
    instance = instance_name(os.environ.get('MAZDA_INSTANCE', 'live'))
    Path('/software/instances').mkdir(exist_ok=True)
    run_lock = open('/software/instances/' + instance + '.lock', 'w')
    try:
        fcntl.flock(run_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('Software instance is already running: ' + instance)
    os.set_inheritable(run_lock.fileno(), True)
lock = open('/software/active.lock', 'w')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit('Another software build or probe is active. Wait for it before running this recipe. Legacy live guests also hold this lock.')
os.set_inheritable(lock.fileno(), True)
if mode == 'kernel':
    os.execv(sys.executable,[sys.executable,'scripts/software/build_kernel.py',*args])
selection = argparse.ArgumentParser(add_help=False,allow_abbrev=False)
selection.add_argument('--kernel-profile',choices=('stock','vmsplit2g'))
options,args = selection.parse_known_args(args)
kernel_profile = options.kernel_profile
if mode == 'run' and kernel_profile is not None:
    built = json.loads(Path('/software/guest/profile.json').read_text())
    if built.get('kernel_profile','stock') != kernel_profile:
        raise SystemExit('Built profile differs; use just start with the requested --kernel-profile')
if mode != 'run':
    build = [sys.executable, 'scripts/software/build.py']
    if kernel_profile is not None:
        build += ['--kernel-profile',kernel_profile]
    if mode not in ('test', 'build'):
        build.append('--opera')
    subprocess.run(build, check=True)
if mode in jobs:
    script, defaults = jobs[mode]
    if mode == 'vnc':
        os.environ['MAZDA_INSTANCE'] = 'vnc-test'
    if mode in ('boot', 'run'):
        profile_path = snapshot(instance)
        lock.close()
        args += ['--profile', str(profile_path)]
    os.execv(sys.executable, [sys.executable, 'scripts/software/' + script, *defaults, *args])
