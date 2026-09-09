"""Verified firmware storage and outer ZIP extraction; never executes update scripts."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import urllib.parse
import zipfile

STORE = Path('/lab/firmware')


def manifest(path):
    data = json.loads(Path(path).read_text())
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', data.get('id', '')):
        raise ValueError('Manifest requires a safe, unique id')
    if not re.fullmatch(r'[a-fA-F0-9]{64}', data.get('sha256') or ''):
        raise ValueError('Set the expected SHA-256 in the manifest first')
    if type(data.get('size')) is not int or data['size'] <= 0:
        raise ValueError('Set the expected package size in bytes first')
    return data


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify(path, data):
    if Path(path).stat().st_size != data['size'] or digest(path) != data['sha256'].lower():
        raise ValueError('Package size or SHA-256 does not match the manifest')


def install(source, data):
    destination = STORE / data['id']
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / 'original.up'
    if target.exists():
        verify(target, data)
        verify(source, data)
        return target
    with tempfile.TemporaryDirectory(dir=destination) as tmp:
        staged = Path(tmp) / 'original.up'
        shutil.copyfile(source, staged)
        verify(staged, data)
        staged.chmod(0o444)
        staged.replace(target)
    (destination / 'manifest.json').write_text(json.dumps(data, indent=2) + '\n')
    return target


def extract(package, target):
    if target.exists():
        raise ValueError(f'Extraction already exists: {target}; use a new package id for new input')
    with zipfile.ZipFile(package) as archive:
        names = set()
        for item in archive.infolist():
            path = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (path.is_absolute() or '..' in path.parts or '\\' in item.filename
                    or not path.parts or path.as_posix() in names):
                raise ValueError(f'Unsafe or duplicate archive path: {item.filename}')
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError('Outer ZIP has links or special files; needs a format-specific extractor')
            names.add(path.as_posix())
        password = os.environ.get('FIRMWARE_ZIP_PASSWORD')
        with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
            staged = Path(tmp) / 'outer'
            staged.mkdir()
            # Native ZipCrypto is much faster than Python for multi-GB packages.
            # Validate every member above before giving the archive to 7z.
            if any(item.flag_bits & 1 for item in archive.infolist()) and not password:
                raise ValueError('Encrypted ZIP: set FIRMWARE_ZIP_PASSWORD')
            result = subprocess.run(['7z', 'x', '-y', '-bd', '-bso0',
                                     '-p' + (password or ''), '-o' + str(staged),
                                     str(package.resolve())], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode:
                raise ValueError('Outer ZIP extraction failed: ' + result.stderr.strip())
            for item in archive.infolist():
                if not item.is_dir():
                    (staged / item.filename).chmod(((item.external_attr >> 16) & 0o777) or 0o644)
            staged.rename(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['import', 'fetch', 'inspect', 'extract'])
    parser.add_argument('manifest')
    parser.add_argument('package', nargs='?')
    args = parser.parse_args()
    data = manifest(args.manifest)
    home = STORE / data['id']
    package = home / 'original.up'
    if args.action == 'import':
        if not args.package:
            parser.error('import requires a local package path')
        install(args.package, data)
    elif args.action == 'fetch':
        url = data.get('url')
        if data.get('yandex_public_key'):
            query = urllib.parse.urlencode({'public_key': data['yandex_public_key'],
                                           'path': data['yandex_path']})
            with urllib.request.urlopen('https://cloud-api.yandex.net/v1/disk/public/resources/download?' + query,
                                        timeout=60) as response:
                url = json.load(response)['href']
        if not (url or '').startswith('https://'):
            raise ValueError('fetch requires an HTTPS source URL in the manifest')
        with tempfile.TemporaryDirectory() as tmp:
            download = Path(tmp) / 'download.up'
            with urllib.request.urlopen(url, timeout=60) as response:
                if not response.url.startswith('https://'):
                    raise ValueError('Refusing redirect to non-HTTPS source')
                with download.open('wb') as out:
                    shutil.copyfileobj(response, out)
            install(download, data)
    else:
        verify(package, data)
        if args.action == 'extract':
            extract(package, home / 'outer')
        else:
            report = {'manifest': data, 'sha256_verified': True}
            report['file'] = subprocess.check_output(['file', '-b', str(package)], text=True).strip()
            if zipfile.is_zipfile(package):
                with zipfile.ZipFile(package) as archive:
                    report['members'] = [{'path': i.filename, 'size': i.file_size,
                                          'encrypted': bool(i.flag_bits & 1)} for i in archive.infolist()]
            output = Path('/workspace/artifacts') / f"{data['id']}.inventory.json"
            output.write_text(json.dumps(report, indent=2) + '\n')
            print(output)
    print(f"{args.action}: {home}")


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise SystemExit(str(error)) from error
