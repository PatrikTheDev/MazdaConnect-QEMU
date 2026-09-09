"""Resolve matching lab kernel modules in dependency order."""
import json
from pathlib import Path
import subprocess


def entries():
    cfg = json.loads(Path('config/kernel/debian-armmp.json').read_text())
    root = Path('/lab/kernels') / cfg['version'] / 'package'
    subprocess.run(['depmod', '-b', str(root), cfg['version']], check=True)
    modules = {}
    def field(target, key):
        return subprocess.check_output(['modinfo', '-b', str(root), '-k', cfg['version'],
                                        '-F', key, target], text=True).strip()
    def add(target):
        filename = field(target, 'filename')
        if filename == '(builtin)':
            return
        source = Path(filename)
        name = 'lab-modules/' + source.name
        if name in modules:
            if modules[name] != source:
                raise ValueError('Duplicate module filename')
            return
        for dependency in filter(None, field(target, 'depends').split(',')):
            add(dependency)
        modules[name] = source
    # ext4/jbd2 request crypto-crc32c as a soft dependency. Select the portable
    # implementation explicitly: Cortex-A15 does not have ARMv8 CRC extensions.
    for target in ('virtio_mmio', 'virtio_blk', 'crc32c_generic', 'ext4'):
        add(target)
    result = [(name, source.read_bytes(), 0o644) for name, source in modules.items()]
    script = '#!/bin/sh\nset -eu\n' + ''.join('/bin/busybox insmod /' + name + '\n' for name in modules)
    result.append(('lab-modules/load.sh', script.encode(), 0o755))
    return result
