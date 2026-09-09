"""Inventory this verified CMU150 package without executing its update instructions."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import tarfile
import xml.etree.ElementTree as ET

from manage import STORE, manifest, verify, digest


def analyze(data):
    home = STORE / data['id']
    verify(home / 'original.up', data)
    outer = home / 'outer'
    if not outer.is_dir():
        raise ValueError('Run firmware-extract first')
    analysis = home / 'analysis'
    analysis.mkdir(exist_ok=True)
    report = {'package': data, 'payloads': [], 'rootfs': {}, 'samples': {}}
    cert = outer / 'publisher_cert.pem'
    public_key = analysis / 'publisher-public.pem'
    signature = analysis / 'package-signature.bin'
    public_key.write_bytes(subprocess.check_output(['openssl', 'x509', '-in', str(cert), '-pubkey', '-noout']))
    package = home / 'original.up'
    with package.open('rb') as source:
        source.seek(-256, 2)
        signature.write_bytes(source.read())
    verifier = subprocess.Popen(['openssl', 'dgst', '-sha256', '-verify', str(public_key),
                                 '-signature', str(signature)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with package.open('rb') as source:
        remaining = package.stat().st_size - 256
        while remaining:
            chunk = source.read(min(1024 * 1024, remaining))
            verifier.stdin.write(chunk)
            remaining -= len(chunk)
    verifier.stdin.close()
    result = verifier.stdout.read().decode() + verifier.stderr.read().decode()
    report['signature'] = {'valid_with_bundled_publisher_key': verifier.wait() == 0,
                           'output': result.strip(), 'trusted_vendor_chain_validated': False,
                           'certificate': subprocess.check_output(['openssl', 'x509', '-in', str(cert),
                               '-noout', '-subject', '-issuer', '-dates', '-fingerprint', '-sha256'], text=True)}
    for source in sorted(outer.rglob('*')):
        if not source.is_file():
            continue
        rel = source.relative_to(outer).as_posix()
        info = {'path': rel, 'size': source.stat().st_size}
        if source.suffix == '.gz':
            with gzip.open(source, 'rb') as stream:
                first = stream.read(512)
            info['decompressed_prefix_type'] = subprocess.check_output(
                ['file', '-b', '-'], input=first).decode().strip()
        report['payloads'].append(info)
        if source.name.endswith('.ini.gz') or source.name == 'main_instructions.ini':
            content = gzip.decompress(source.read_bytes()) if source.suffix == '.gz' else source.read_bytes()
            dest = analysis / 'instructions' / rel.removesuffix('.gz')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)

    # Mapping established by rootfs1upd/execute.ini.gz, not guessed by file magic.
    root_payload = outer / 'rootfs1upd/e0000000001.dat.gz'
    archive_path = analysis / 'rootfs.tar.gz'
    with gzip.open(root_payload, 'rb') as src, archive_path.open('wb') as dst:
        shutil.copyfileobj(src, dst)
    report['rootfs']['archive_sha256'] = digest(archive_path)
    checksum_text = gzip.decompress((outer / 'rootfs1upd/e0000000002.dat.gz').read_bytes()).decode()
    expected = {}
    for line in checksum_text.splitlines():
        value, name = line.split(None, 1)
        expected[name.removeprefix('/tmp/rootfs/')] = value
    checked, mismatches = set(), []
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        report['rootfs']['members'] = [
            {'path': m.name, 'size': m.size, 'mode': oct(m.mode), 'uid': m.uid,
             'gid': m.gid, 'type': m.type.decode('ascii', errors='replace'), 'link': m.linkname}
            for m in members]
        report['rootfs']['member_count'] = len(members)
        report['rootfs']['regular_bytes'] = sum(m.size for m in members if m.isfile())
        report['rootfs']['top_level_counts'] = dict(Counter(m.name.removeprefix('./').split('/')[0] for m in members))
        wanted = {'bin/busybox', 'etc/inittab', 'etc/fstab', 'etc/init.d/rcS',
                  'jci/sm/sm.conf', 'jci/sm/sm.xml'}
        sample_root = analysis / 'samples'
        sample_root.mkdir(exist_ok=True)
        for member in members:
            name = member.name.removeprefix('./')
            # Samples have generated filenames: no tar paths, links, ownership or
            # device nodes are materialized in the host/container filesystem.
            if not member.isfile():
                continue
            selected = name in wanted or any(t in name for t in ('libc-', 'ld-', '/opera', 'libEGL', 'libGAL', 'libwayland'))
            destination = sample_root / f'{len(report["samples"]):04d}.bin'
            md5 = hashlib.md5()
            if name in expected or selected:
                with archive.extractfile(member) as src:
                    dst = destination.open('wb') if selected else None
                    try:
                        while chunk := src.read(1024 * 1024):
                            md5.update(chunk)
                            if dst:
                                dst.write(chunk)
                    finally:
                        if dst:
                            dst.close()
            if name in expected:
                checked.add(name)
                if md5.hexdigest() != expected[name]:
                    mismatches.append(name)
            if not selected:
                continue
            record = {'sample': str(destination), 'sha256': digest(destination),
                      'file': subprocess.check_output(['file', '-b', str(destination)], text=True).strip()}
            with destination.open('rb') as stream:
                elf = stream.read(4) == b'\x7fELF'
            if elf:
                record['elf'] = subprocess.check_output(['arm-linux-gnueabi-readelf', '-h', '-l', '-A', '-d',
                                                        str(destination)], text=True)
            report['samples'][name] = record
    report['rootfs']['vendor_md5'] = {'expected_records': len(expected), 'checked_regular_files': len(checked),
                                    'mismatches': mismatches, 'unchecked_paths': sorted(set(expected) - checked)}
    kernel = gzip.decompress((outer / 'linux1/e0000000001.dat.gz').read_bytes())
    (analysis / 'cmu-linux-rootfs.bin').write_bytes(kernel)
    report['kernel_payload'] = {'size': len(kernel), 'sha256': hashlib.sha256(kernel).hexdigest(),
                               'prefix_hex': kernel[:16].hex(),
                               'linux_version_markers': [m.decode(errors='replace') for m in
                                   re.findall(rb'Linux version [\x20-\x7e]{1,100}', kernel)]}
    sm = report['samples'].get('jci/sm/sm.conf')
    if sm:
        tree = ET.fromstring(Path(sm['sample']).read_text())
        report['opera_service'] = [{'attributes': service.attrib,
                                   'dependencies': [item.attrib for item in service.findall('dependency')]}
                                  for service in tree.iter('service') if service.get('name') == 'Opera']
    output = Path('/workspace/artifacts') / f"{data['id']}.analysis.json"
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"Rootfs: {report['rootfs']['member_count']} members; report: {output}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    args = parser.parse_args()
    analyze(manifest(args.manifest))
