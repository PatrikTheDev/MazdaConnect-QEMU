"""Resolve stock or explicitly selected, completed software-lab kernel builds."""
import hashlib
import json
from pathlib import Path


def selected(name):
    if name == 'stock':
        cfg = json.loads(Path('config/kernel/debian-armmp.json').read_text())
        cfg['package'] = '/lab/kernels/' + cfg['version'] + '/package'
        cfg['headers'] = '/usr/src/linux-headers-' + cfg['version']
        return cfg
    if name != 'vmsplit2g':
        raise ValueError('Unknown kernel profile: ' + name)
    manifest = Path('/software/kernels/vmsplit2g/manifest.json')
    if not manifest.exists():
        raise RuntimeError('Build the opt-in kernel first: just dev software task kernel')
    cfg = json.loads(manifest.read_text())
    with Path(cfg['kernel']).open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=cfg['kernel_sha256']:
            raise RuntimeError('Custom kernel differs from its completed build manifest')
    config = (Path(cfg['headers']) / '.config').read_bytes()
    if hashlib.sha256(config).hexdigest()!=cfg['config_sha256']:
        raise RuntimeError('Custom kernel config differs from its completed build manifest')
    return cfg
