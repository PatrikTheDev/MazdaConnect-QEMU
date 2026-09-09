"""Shared QEMU devices for automated and live software-rendering runs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'guest'))
from boot import command


def software_command(profile, live=False):
    profile = dict(profile)
    profile['graphics'] = False
    if live:
        profile['append'] += ' video=Virtual-1:800x480@60'
    result = command(profile)
    result += ['-global', 'virtio-mmio.force-legacy=false',
               '-device', 'virtio-keyboard-device', '-device', 'virtio-tablet-device']
    if live:
        result += ['-device', 'virtio-gpu-device', '-vnc', '0.0.0.0:0']
    return result
