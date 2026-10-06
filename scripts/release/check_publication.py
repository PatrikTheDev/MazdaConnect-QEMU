"""Reject tracked binary payloads, private keys, and generated lab data."""
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    git = ['git', '-c', 'safe.directory=/workspace']
    paths = subprocess.check_output([*git, 'ls-files', '-z']).decode().split('\0')
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
    # Also catch payloads deleted from the current tree but retained in history.
    objects = subprocess.check_output([*git, 'rev-list', '--objects', '--all']).splitlines()
    with tempfile.TemporaryFile() as requests:
        requests.write(b'\n'.join(line.split(b' ', 1)[0] for line in objects) + b'\n')
        requests.seek(0)
        process = subprocess.Popen([*git, 'cat-file', '--batch'], stdin=requests,
                                   stdout=subprocess.PIPE)
        count = 0
        for item in objects:
            header = process.stdout.readline().split()
            data = process.stdout.read(int(header[2]))
            process.stdout.read(1)
            if header[1] != b'blob':
                continue
            count += 1
            label = item.decode(errors='replace')
            try:
                data.decode('utf-8')
                binary = b'\0' in data
            except UnicodeDecodeError:
                binary = True
            if binary:
                failures.append(label + ': binary retained in reachable history')
            if re.search(rb'-----BEGIN (?:[A-Z ]*PRIVATE KEY)-----', data):
                failures.append(label + ': private key retained in reachable history')
        if process.wait():
            raise SystemExit('Git history inspection failed')
    if failures:
        raise SystemExit('\n'.join(failures))
    print(f'Publication check passed: working tree and {count} reachable blob versions '
          '(not a complete provenance or secret audit).')


if __name__ == '__main__':
    main()
