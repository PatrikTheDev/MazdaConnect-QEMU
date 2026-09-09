"""Build a metadata-preserving newc archive directly from Mazda's rootfs tar."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'firmware'))
from manage import STORE, manifest, verify
from modules import entries as module_entries


def write_entry(out, name, mode, uid, gid, mtime, size, source, inode, major=0, minor=0):
    encoded = name.encode() + b'\0'
    fields = [inode, mode, uid, gid, 2 if stat.S_ISDIR(mode) else 1, mtime,
              size, 0, 0, major, minor, len(encoded), 0]
    if any(not 0 <= n <= 0xffffffff for n in fields):
        raise ValueError('newc field out of range')
    header = b'070701' + ''.join(f'{n:08x}' for n in fields).encode()
    out.write(header + encoded)
    out.write(b'\0' * (-(110 + len(encoded)) % 4))
    remaining = size
    while remaining:
        chunk = source.read(min(1024 * 1024, remaining))
        if not chunk:
            raise ValueError('Truncated archive member')
        out.write(chunk)
        remaining -= len(chunk)
    out.write(b'\0' * (-size % 4))


def build(cfg):
    home = STORE / cfg['id']
    verify(home / 'original.up', cfg)
    analysis = json.loads((Path('/workspace/artifacts') / f"{cfg['id']}.analysis.json").read_text())
    source = home / 'analysis/rootfs.tar.gz'
    with source.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != analysis['rootfs']['archive_sha256']:
            raise ValueError('Rootfs archive changed since analysis')
    guest = Path('/lab/guests') / cfg['id']
    guest.mkdir(parents=True, exist_ok=True)
    extras = module_entries()
    for tool in ('trace-driver', 'wayland-check'):
        binary = guest / tool
        subprocess.run(['arm-linux-gnueabi-gcc', '-static', '-O2', '-Wall', '-Wextra', '-Werror',
                        f'src/tools/{tool}.c', '-o', str(binary)], check=True)
        extras.append(('lab-modules/' + tool, binary.read_bytes(), 0o755))
    for name, mode in [('run-compositor', 0o755), ('compositor-headless.conf', 0o644)]:
        extras.append(('lab-modules/' + name, (Path('overlays/lab') / name).read_bytes(), mode))
    known, links = set(), set()
    # Validate paths before producing a guest artifact. Absolute symlink targets
    # are retained as guest paths; no archive paths are extracted on the host.
    with tarfile.open(source, 'r:gz') as archive:
        members = archive.getmembers()
        for member in members:
            name = member.name.removeprefix('./')
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or name in known:
                raise ValueError('Unsafe or duplicate tar path: ' + name)
            if not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError('Unsupported tar member type: ' + name)
            if member.pax_headers:
                raise ValueError('PAX metadata needs explicit handling: ' + name)
            known.add(name)
            if member.issym():
                links.add(name)
        for name in known:
            if any(str(parent) in links for parent in PurePosixPath(name).parents):
                raise ValueError('Tar writes through a symlink: ' + name)
        if ({'lab-init', 'dev/console', 'lab-modules'} | {e[0] for e in extras}) & known:
            raise ValueError('Lab overlay conflicts with vendor files')
        with tempfile.TemporaryDirectory(dir=guest) as tmp:
            target = Path(tmp) / 'initramfs.cpio.gz'
            with target.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=1) as out:
                for inode, member in enumerate(members, 1):
                    name = member.name.removeprefix('./')
                    if member.isfile():
                        mode = stat.S_IFREG | member.mode
                        payload = archive.extractfile(member)
                        size = member.size
                    elif member.issym():
                        mode = stat.S_IFLNK | member.mode
                        data = member.linkname.encode()
                        payload, size = io.BytesIO(data), len(data)
                    else:
                        mode = stat.S_IFDIR | member.mode
                        payload, size = io.BytesIO(), 0
                    with payload:
                        write_entry(out, name, mode, member.uid, member.gid, int(member.mtime), size, payload, inode)
                init = Path('overlays/lab/lab-init').read_bytes()
                write_entry(out, 'lab-init', stat.S_IFREG | 0o755, 0, 0, 0, len(init), io.BytesIO(init), len(members)+1)
                write_entry(out, 'dev/console', stat.S_IFCHR | 0o600, 0, 0, 0, 0, io.BytesIO(), len(members)+2, 5, 1)
                write_entry(out, 'lab-modules', stat.S_IFDIR | 0o755, 0, 0, 0, 0, io.BytesIO(), len(members)+3)
                for inode, (name, data, mode) in enumerate(extras, len(members)+4):
                    write_entry(out, name, stat.S_IFREG | mode, 0, 0, 0, len(data), io.BytesIO(data), inode)
                write_entry(out, 'TRAILER!!!', 0, 0, 0, 0, 0, io.BytesIO(), 0)
            target.replace(guest / 'initramfs.cpio.gz')
    with (guest / 'initramfs.cpio.gz').open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'firmware_sha256': cfg['sha256'], 'rootfs_sha256': analysis['rootfs']['archive_sha256'],
              'initramfs_sha256': sha, 'vendor_members': len(members),
              'overlay_sha256': hashlib.sha256(init).hexdigest(),
              'added': ['lab-init', 'dev/console', 'lab-modules'] + [name for name, _, _ in extras],
              'lab_extras': {name: hashlib.sha256(data).hexdigest() for name, data, _ in extras},
              'scope': 'Original rootfs plus lab init and generic kernel disk modules. Resources mounted from separate read-only disk. Original hardware services do not start.'}
    (Path('/workspace/artifacts') / f"{cfg['id']}.guest.json").write_text(json.dumps(report, indent=2)+'\n')
    print(guest / 'initramfs.cpio.gz')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    build(manifest(parser.parse_args().manifest))
