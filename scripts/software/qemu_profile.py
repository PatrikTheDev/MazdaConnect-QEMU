"""Shared QEMU devices for automated and live software-rendering runs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'guest'))
from boot import command
from vnc_auth import vnc_options


def software_command(profile, live=False, audio_dir=None, developer_mode=False):
    profile = dict(profile)
    profile['graphics'] = False
    if live:
        profile['append'] += ' video=Virtual-1:800x480@60'
    result = command(profile)
    if developer_mode:
        # Docker publishes these container listeners only on host loopback.
        # Keep native WebSocket ports: the firmware derives their host from the URL.
        forwards = ','.join(f'hostfwd=tcp:0.0.0.0:{host}-10.0.2.15:{guest}'
                            for host, guest in ((8080, 80), (2700, 2700),
                                                (2766, 2766), (2800, 2800)))
        result += ['-netdev', 'user,id=developer,net=10.0.2.0/24,restrict=on,ipv6=off,' + forwards,
                   '-device', 'virtio-net-device,netdev=developer,mac=52:54:00:12:34:56']
    result += ['-global', 'virtio-mmio.force-legacy=false',
               '-device', 'virtio-keyboard-device', '-device', 'virtio-tablet-device']
    if live:
        result += ['-device', 'virtio-gpu-device', *vnc_options('0.0.0.0:0')]
    if audio_dir is not None:
        for index in range(2):
            result += ['-audiodev', f'pa,id=audio{index},server=unix:{audio_dir}/pulse/socket,out.name=speaker{index},in.name=microphone',
                       '-device', f'intel-hda,id=hda{index}',
                       '-device', f'hda-duplex,bus=hda{index}.0,audiodev=audio{index}']
    return result
