"""Run the verified EU 74.00.324A BusyBox in a minimal, disposable library prefix."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from manage import STORE, manifest, verify


def probe(data):
    home = STORE / data['id']
    verify(home / 'original.up', data)
    report_path = Path('/workspace/artifacts') / f"{data['id']}.analysis.json"
    analysis = json.loads(report_path.read_text())
    archive_path = home / 'analysis/rootfs.tar.gz'
    with archive_path.open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != analysis['rootfs']['archive_sha256']:
            raise ValueError('Derived rootfs archive changed since analysis')
    files = ['bin/busybox', 'lib/ld-2.11.1.so', 'lib/libc-2.11.1.so', 'lib/libm-2.11.1.so']
    links = {'lib/ld-linux.so.3': 'ld-2.11.1.so',
             'lib/libc.so.6': 'libc-2.11.1.so', 'lib/libm.so.6': 'libm-2.11.1.so'}
    with tempfile.TemporaryDirectory(dir=home) as tmp, tarfile.open(archive_path, 'r:gz') as archive:
        root = Path(tmp)
        for member in archive:
            name = member.name.removeprefix('./')
            if name in files:
                if not member.isfile():
                    raise ValueError(f'Expected regular file: {name}')
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as src, destination.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
                destination.chmod(member.mode & 0o777)
            elif name in links:
                if not member.issym() or member.linkname != links[name]:
                    raise ValueError(f'Unexpected library link: {name}')
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(member.linkname)
        if not all((root / name).is_file() for name in files + list(links)):
            raise ValueError('Required BusyBox/libc files were not found')
        command = ['qemu-arm', '-L', str(root), str(root / 'bin/busybox')]
        echo = subprocess.run(command + ['echo', 'Mazda BusyBox runs under QEMU'],
                              capture_output=True, text=True, timeout=20, check=True)
        if echo.stdout != 'Mazda BusyBox runs under QEMU\n':
            raise ValueError('Unexpected BusyBox output')
        help_result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        report = {'package_sha256': data['sha256'], 'echo': echo.stdout.strip(),
                  'busybox_help': help_result.stdout + help_result.stderr,
                  'scope': 'Original BusyBox, loader, libc and libm only. No Mazda services or full-system boot.'}
        output = Path('/workspace/artifacts') / f"{data['id']}.probe.json"
        output.write_text(json.dumps(report, indent=2) + '\n')
        print(echo.stdout.strip())
        print(report['busybox_help'].splitlines()[0])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    probe(manifest(parser.parse_args().manifest))
