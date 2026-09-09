"""Disposable guest core disk and offline GDB analysis using original binaries."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile


def prepare_disk():
    directory = Path(tempfile.mkdtemp(prefix='graphics-', dir='/lab/guests'))
    disk = directory / 'debug.ext4'
    with disk.open('wb') as stream:
        stream.truncate(256 * 1024**2)
    subprocess.run(['mkfs.ext4', '-q', '-F', '-L', 'MAZDA_DEBUG', str(disk)], check=True)
    return disk


def sysroot(identifier, parent='/lab/guests'):
    home = Path('/lab/firmware') / identifier
    report = json.loads((Path('artifacts') / f'{identifier}.analysis.json').read_text())
    source = home / 'analysis/rootfs.tar.gz'
    with source.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != report['rootfs']['archive_sha256']:
            raise ValueError('Rootfs archive hash mismatch')
    directory = Path(tempfile.mkdtemp(prefix='symbols-', dir=parent))
    with tarfile.open(source) as archive:
        members = archive.getmembers()
        names = {m.name.removeprefix('./') for m in members}
        links = {m.name.removeprefix('./') for m in members if m.issym()}
        if len(names) != len(members):
            raise ValueError('Duplicate rootfs member')
        for member in members:
            name = member.name.removeprefix('./')
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or any(str(p) in links for p in path.parents):
                raise ValueError('Unsafe rootfs member')
            if not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError('Unsupported rootfs member')
        for member in members:
            dest = directory / member.name.removeprefix('./')
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as stream, dest.open('wb') as out:
                    shutil.copyfileobj(stream, out)
        # Analysis-only links stay within this prefix even for absolute guest targets.
        for member in members:
            if member.issym():
                dest = directory / member.name.removeprefix('./')
                target = os.path.normpath('/' + str(dest.parent.relative_to(directory)) + '/' + member.linkname)
                if member.linkname.startswith('/'):
                    target = os.path.normpath(member.linkname)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(os.path.relpath(directory / target.lstrip('/'), dest.parent))
    return directory


def analyze(disk, identifier):
    core = disk.parent / 'compositor.core'
    subprocess.run(['debugfs', '-R', f'dump /compositor.core {core}', str(disk)], check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if not core.exists():
        print('No compositor core dump was produced; retained diagnostic disk: ' + str(disk))
        return
    root = sysroot(identifier)
    commands = ['set pagination off', 'set auto-load safe-path /nonexistent',
                f'set sysroot {root}', f'file {root}/usr/bin/wayland-viv-compositor', f'core-file {core}',
                'info sharedlibrary', 'thread apply all bt', 'info registers',
                'x/12i $pc-20', 'info proc mappings']
    args = ['gdb-multiarch', '-nx', '-batch']
    for command in commands:
        args.extend(['-ex', command])
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    Path('runs/eu-v74-compositor-gdb.log').write_text(result.stdout)
    Path('artifacts/cmu150-eu-74.00.324A.graphics-debug.json').write_text(json.dumps({
        'core': str(core), 'debug_disk': str(disk), 'analysis_sysroot': str(root),
        'core_sha256': hashlib.sha256(core.read_bytes()).hexdigest(),
        'gdb_exit_code': result.returncode,
        'executable_sha256': hashlib.sha256((root / 'usr/bin/winston').read_bytes()).hexdigest(),
    }, indent=2) + '\n')
    print('Core and analysis sysroot retained at ' + str(disk.parent) + ' and ' + str(root))
