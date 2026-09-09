"""Launch an explicitly supplied lab kernel/initramfs, with optional VNC and GDB."""
import argparse
import json
import os
from pathlib import Path
import shlex


def command(profile, debug=False):
    for field in ('kernel', 'initrd'):
        if not Path(profile[field]).is_file():
            raise ValueError(f"Missing {field}: {profile[field]}. Supply a compatible ARM lab build; see docs/guest.md.")
    result = ['qemu-system-arm', '-machine', profile['machine'], '-cpu', profile['cpu'],
              '-accel', 'tcg', '-m', str(profile['memory_mb']), '-nic', 'none',
              '-kernel', profile['kernel'], '-initrd', profile['initrd'],
              '-append', profile['append'], '-serial', 'stdio', '-monitor', 'none', '-no-reboot']
    for index, disk in enumerate(profile.get('disks', [])):
        if not Path(disk['path']).is_file():
            raise ValueError('Missing disk: ' + disk['path'])
        result += ['-drive', f"file={disk['path']},format=raw,if=none,id=disk{index},readonly={'on' if disk.get('read_only', True) else 'off'}",
                   '-device', f'virtio-blk-device,drive=disk{index}']
    if profile.get('graphics'):
        result += ['-device', 'virtio-gpu-pci', '-device', 'qemu-xhci',
                   '-device', 'usb-kbd', '-device', 'usb-tablet', '-vnc', '0.0.0.0:0']
    else:
        result += ['-display', 'none']
    if debug:
        result += ['-S', '-gdb', 'tcp:0.0.0.0:1234']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--compositor', action='store_true', help='Start the original compositor with the lab headless configuration')
    args = parser.parse_args()
    try:
        profile = json.loads(Path(args.profile).read_text())
        if args.compositor:
            profile['append'] += ' lab.compositor=headless'
        cmd = command(profile, args.debug)
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(str(error)) from error
    print(shlex.join(cmd), flush=True)
    os.execvp(cmd[0], cmd)
