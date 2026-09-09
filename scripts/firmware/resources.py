"""Reconstruct /resources as a tar archive; never execute updater instructions."""
import argparse
import configparser
import csv
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import tempfile
import zlib

from manage import STORE, manifest, verify


def instructions(text):
    ini = configparser.ConfigParser(interpolation=None)
    ini.read_string(text)
    section = ini['Instructions']
    count = int(section['Count'])
    if set(section) != {'count'} | {str(i) for i in range(1, count + 1)}:
        raise ValueError('Instruction count mismatch')
    entries, seen = [], set()
    for i in range(1, count + 1):
        row = next(csv.reader([section[str(i)]], strict=True))
        if i == 1 and row == ['Execute', 'echo ========== Start updating /resources ==========']:
            continue
        if i == 2 and row == ['RemoveFolderContent', '/resources/']:
            continue
        if not row or (row[0], len(row)) not in [('Create', 3), ('Copy', 5)]:
            raise ValueError('Unsupported instruction: ' + repr(row))
        dest = row[1] if row[0] == 'Create' else row[2]
        path = PurePosixPath(dest)
        if not dest.startswith('/resources/') or '..' in path.parts or len(path.parts) < 3:
            raise ValueError('Unsafe resource path: ' + dest)
        name = str(path.relative_to('/'))
        if name in seen:
            raise ValueError('Duplicate resource path: ' + name)
        seen.add(name)
        mode = int(row[-1] if row[0] == 'Create' else row[3], 8)
        if not 0 <= mode <= 0o777:
            raise ValueError('Unsupported resource permissions')
        entry = {'name': name, 'kind': row[0], 'mode': mode}
        if row[0] == 'Copy':
            if not re.fullmatch(r'resources/f[0-9]{10}\.dat', row[1]):
                raise ValueError('Unsafe payload path')
            if not re.fullmatch(r'0x[0-9a-fA-F]{8}', row[4]):
                raise ValueError('Invalid CRC32')
            entry.update(source=row[1] + '.gz', crc32=int(row[4], 16))
        entries.append(entry)
    files = {e['name'] for e in entries if e['kind'] == 'Copy'}
    for entry in entries:
        if any(str(parent) in files for parent in PurePosixPath(entry['name']).parents):
            raise ValueError('File used as directory')
    return entries


def assemble(cfg):
    home = STORE / cfg['id']
    verify(home / 'original.up', cfg)
    # Read the actual gzip-wrapped instruction payload, not a manually edited copy.
    entries = instructions(gzip.decompress((home / 'outer/resources/files.ini.gz').read_bytes()).decode())
    target = home / 'analysis/resources.tar'
    total = 0
    with tempfile.TemporaryDirectory(dir=home) as tmp:
        output = Path(tmp) / 'resources.tar'
        with tarfile.open(output, 'w', format=tarfile.USTAR_FORMAT) as archive:
            for entry in entries:
                info = tarfile.TarInfo(entry['name'])
                info.mode = entry['mode']
                # Updater specifies permissions only. Root ownership is a lab assumption.
                info.uid = info.gid = info.mtime = 0
                if entry['kind'] == 'Create':
                    info.type = tarfile.DIRTYPE
                    archive.addfile(info)
                    continue
                crc, sha, size = 0, hashlib.sha256(), 0
                with tempfile.TemporaryFile(dir=tmp) as decoded:
                    with gzip.open(home / 'outer' / entry['source'], 'rb') as source:
                        while chunk := source.read(1024 * 1024):
                            decoded.write(chunk)
                            crc = zlib.crc32(chunk, crc)
                            sha.update(chunk)
                            size += len(chunk)
                    if crc != entry['crc32']:
                        raise ValueError('CRC32 mismatch: ' + entry['source'])
                    entry.update(size=size, sha256=sha.hexdigest())
                    info.size = size
                    decoded.seek(0)
                    archive.addfile(info, decoded)
                    total += size
        output.replace(target)
    with target.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'firmware_sha256': cfg['sha256'], 'archive_sha256': sha,
              'decoded_bytes': total, 'files': sum(e['kind'] == 'Copy' for e in entries),
              'directories': sum(e['kind'] == 'Create' for e in entries),
              'ownership': 'uid/gid 0 is a lab assumption; updater supplies modes only',
              'entries': entries}
    (Path('artifacts') / f"{cfg['id']}.resources.json").write_text(json.dumps(report, indent=2) + '\n')
    print(f"Verified {report['files']} CRC32 values; {total} decoded bytes; {target}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    assemble(manifest(parser.parse_args().manifest))
