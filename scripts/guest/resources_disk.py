"""Build an ext4 resource disk from the verified resource archive without mounts."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile


def build(identifier):
    if not identifier or PurePosixPath(identifier).name != identifier or identifier in ('.', '..'):
        raise ValueError('Invalid firmware identifier')
    archive = Path('/lab/firmware') / identifier / 'analysis/resources.tar'
    report = json.loads((Path('artifacts') / f'{identifier}.resources.json').read_text())
    with archive.open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != report['archive_sha256']:
            raise ValueError('Resource archive hash mismatch')
    guest = Path('/lab/guests') / identifier
    guest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=guest) as tmp:
        staging = Path(tmp)
        tree = staging / 'tree'
        tree.mkdir()
        with tarfile.open(archive) as source:
            members = source.getmembers()
            for member in members:
                path = PurePosixPath(member.name)
                if (path.is_absolute() or '..' in path.parts or path.parts[0] != 'resources'
                        or not (member.isfile() or member.isdir())):
                    raise ValueError('Unsafe resource member: ' + member.name)
            # Only validated regular files/directories enter this fresh tree.
            source.extractall(tree, members=members)
        disk = staging / 'resources.ext4'
        with disk.open('wb') as out:
            out.truncate(3 * 1024**3)
        subprocess.run(['mkfs.ext4', '-q', '-F', '-m', '0', '-L', 'MAZDA_RESOURCES',
                        '-d', str(tree / 'resources'), str(disk)], check=True)
        subprocess.run(['e2fsck', '-fn', str(disk)], check=True)
        disk.replace(guest / disk.name)
    with (guest / 'resources.ext4').open('rb') as source:
        sha = hashlib.file_digest(source, 'sha256').hexdigest()
    (Path('artifacts') / f'{identifier}.resources-disk.json').write_text(json.dumps({
        'resource_archive_sha256': report['archive_sha256'], 'disk_sha256': sha,
        'size': 3 * 1024**3, 'mount': '/mnt/resources', 'read_only': True,
    }, indent=2) + '\n')
    print(guest / 'resources.ext4')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('identifier')
    build(parser.parse_args().identifier)
