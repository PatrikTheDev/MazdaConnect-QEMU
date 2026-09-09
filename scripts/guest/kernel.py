"""Fetch and unpack the pinned lab kernel; never install Debian package scripts."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request


def fetch():
    cfg = json.loads(Path('config/kernel/debian-armmp.json').read_text())
    root = Path('/lab/kernels') / cfg['version']
    root.mkdir(parents=True, exist_ok=True)
    target = root / 'kernel.deb'
    with tempfile.TemporaryDirectory(dir=root) as tmp:
        if not target.exists():
            staged = Path(tmp) / 'kernel.deb'
            with urllib.request.urlopen(cfg['url'], timeout=60) as source, staged.open('wb') as out:
                shutil.copyfileobj(source, out)
        else:
            staged = target
        with staged.open('rb') as source:
            actual = hashlib.file_digest(source, 'sha256').hexdigest()
        if actual != cfg['sha256'] or staged.stat().st_size != cfg['size']:
            raise ValueError('Kernel package hash or size mismatch')
        if staged != target:
            staged.replace(target)
        extracted = root / 'package'
        if not extracted.exists():
            staging = Path(tmp) / 'package'
            subprocess.run(['dpkg-deb', '-x', str(target), str(staging)], check=True)
            staging.rename(extracted)
    print(extracted / 'boot' / ('vmlinuz-' + cfg['version']))


if __name__ == '__main__':
    fetch()
