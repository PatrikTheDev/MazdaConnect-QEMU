"""Decode the observed CMU150 TOOB container and inventory its newc initramfs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tarfile

from manage import STORE, manifest, verify


def split_boot(data):
    if len(data) < 512 or data[:4] != b'TOOB':
        raise ValueError('Not a supported TOOB image')
    count = struct.unpack_from('<I', data, 4)[0]
    if count != 3:
        raise ValueError('Only the observed three-entry TOOB layout is supported')
    entries, occupied, kinds = [], [], set()
    for index in range(count):
        kind, header_size, size, sector, sectors = struct.unpack_from('<5I', data, 0x40 + index * 20)
        start, end = sector * 512, sector * 512 + size
        if (header_size != 20 or kind not in (0, 1, 2) or kind in kinds or not size
                or start < 512 or end > len(data) or sectors != (size + 511) // 512
                or (sector + sectors) * 512 > len(data)):
            raise ValueError('Invalid TOOB table entry')
        if any(start < hi and (sector + sectors) * 512 > lo for lo, hi in occupied):
            raise ValueError('Overlapping TOOB table entries')
        occupied.append((start, (sector + sectors) * 512))
        kinds.add(kind)
        entries.append({'kind': kind, 'offset': start, 'size': size, 'sectors': sectors,
                        'sha256': hashlib.sha256(data[start:end]).hexdigest(), 'data': data[start:end]})
    by_kind = {e['kind']: e['data'] for e in entries}
    if len(by_kind[0]) < 48 or by_kind[0][36:40] != b'\x18\x28\x6f\x01':
        raise ValueError('Kernel entry is not an ARM zImage')
    if not by_kind[2].endswith(b'\0') or not by_kind[1].startswith(b'\x1f\x8b\x08'):
        raise ValueError('Invalid command line or initramfs entry')
    return entries


def parse_newc(data):
    offset, members = 0, []
    while offset + 110 <= len(data):
        if data[offset:offset+6] != b'070701':
            raise ValueError('Expected newc header')
        try:
            fields = [int(data[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
        except ValueError as error:
            raise ValueError('Invalid newc fields') from error
        size, namesize = fields[6], fields[11]
        name_end = offset + 110 + namesize
        start = (name_end + 3) & ~3
        end = start + size
        if not namesize or name_end > len(data) or data[name_end-1] != 0 or end > len(data):
            raise ValueError('Truncated newc member')
        name = data[offset+110:name_end-1].decode('utf-8')
        if name == 'TRAILER!!!':
            if size or any(data[(end+3)&~3:]):
                raise ValueError('Unexpected data after newc trailer')
            return members
        members.append({'path': name, 'mode': fields[1], 'uid': fields[2], 'gid': fields[3],
                        'size': size, 'data': data[start:end]})
        offset = (end + 3) & ~3
    raise ValueError('Missing newc trailer')


def inspect(data):
    home = STORE / data['id']
    verify(home / 'original.up', data)
    report = json.loads((Path('/workspace/artifacts') / f"{data['id']}.analysis.json").read_text())
    raw = (home / 'analysis/cmu-linux-rootfs.bin').read_bytes()
    if hashlib.sha256(raw).hexdigest() != report['kernel_payload']['sha256']:
        raise ValueError('Boot payload has changed since firmware analysis')
    output = home / 'boot'
    output.mkdir(exist_ok=True)
    entries = split_boot(raw)
    names = {0: 'zImage', 1: 'initramfs.cpio.gz', 2: 'cmdline.txt'}
    for entry in entries:
        (output / names[entry['kind']]).write_bytes(entry['data'])
    members = parse_newc(gzip.decompress(next(e['data'] for e in entries if e['kind'] == 1)))
    init = next(m['data'] for m in members if m['path'] == 'init')
    (output / 'initramfs-init.elf').write_bytes(init)
    result = {'entries': [{k: v for k, v in e.items() if k != 'data'} for e in entries],
              'cmdline': next(e['data'] for e in entries if e['kind'] == 2).rstrip(b'\0').decode(),
              'initramfs': [{k: v for k, v in m.items() if k != 'data'} for m in members]}
    with tarfile.open(home / 'analysis/rootfs.tar.gz') as archive:
        member = archive.getmember('./sbin/init_cmu')
        (output / 'init_cmu.elf').write_bytes(archive.extractfile(member).read())
        result['rootfs_init_links'] = {n: archive.getmember('./'+n).linkname
                                      for n in ('sbin/init', 'sbin/init_target')}
    for name in ('initramfs-init.elf', 'init_cmu.elf'):
        for tool, suffix in ((['strings'], 'strings.txt'), (['arm-linux-gnueabi-objdump', '-d'], 'disassembly.txt')):
            content = subprocess.check_output(tool + [str(output / name)])
            (output / (name + '.' + suffix)).write_bytes(content)
    dest = Path('/workspace/artifacts') / f"{data['id']}.boot.json"
    dest.write_text(json.dumps(result, indent=2) + '\n')
    print(f'Decoded kernel, command line, and {len(members)} initramfs entries: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    inspect(manifest(parser.parse_args().manifest))
