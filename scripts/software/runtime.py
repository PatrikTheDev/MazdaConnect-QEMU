"""Snapshot build outputs so live guests can run independently of later builds."""
import json
import re
import shutil
import tempfile
from pathlib import Path


def instance_name(value):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', value):
        raise ValueError('MAZDA_INSTANCE must be 1..32 lowercase letters, digits or hyphens, starting with a letter')
    return value


def state_path(instance, root=Path('/software')):
    return root / ('live.json' if instance == 'live' else f'instances/{instance}.json')


def snapshot(instance, root=Path('/software')):
    """Caller holds the build lock until all writable-volume inputs are copied."""
    profile = json.loads((root / 'guest/profile.json').read_text())
    (root / 'instances').mkdir(exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix=f'live-{instance}-', dir=root))
    try:
        for field in ('kernel', 'initrd'):
            target = home / field
            shutil.copyfile(profile[field], target)
            profile[field] = str(target)
        for index, disk in enumerate(profile.get('disks', [])):
            source = Path(disk['path'])
            # Reference-volume disks are immutable. Software build disks are not.
            if source.is_relative_to(root):
                target = home / f'disk{index}.ext4'
                shutil.copyfile(source, target)
                disk['path'] = str(target)
        target = home / 'profile.json'
        target.write_text(json.dumps(profile, indent=2) + '\n')
        return target
    except BaseException:
        shutil.rmtree(home)
        raise
