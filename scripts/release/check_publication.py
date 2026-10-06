"""Reject tracked binary payloads, private keys, and generated lab data."""
from pathlib import Path
import re
import subprocess


def main():
    paths = subprocess.check_output(
        ['git', '-c', 'safe.directory=/workspace', 'ls-files', '-z']
    ).decode().split('\0')
    failures = []
    for name in filter(None, paths):
        path = Path(name)
        if not path.is_file():
            continue
        data = path.read_bytes()
        try:
            data.decode('utf-8')
            binary = b'\0' in data
        except UnicodeDecodeError:
            binary = True
        if binary:
            failures.append(name + ': binary content')
        if re.search(rb'-----BEGIN (?:[A-Z ]*PRIVATE KEY)-----', data):
            failures.append(name + ': private key')
        if (name.startswith(('artifacts/', 'runs/')) and path.name != '.gitkeep') or path.suffix in {
            '.up', '.ext4', '.qcow2', '.img', '.core', '.elf', '.deb', '.pem', '.key'
        }:
            failures.append(name + ': generated or private payload')
    if failures:
        raise SystemExit('\n'.join(failures))
    print('Tracked-file publication check passed (not a complete provenance or secret audit).')


if __name__ == '__main__':
    main()
