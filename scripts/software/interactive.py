"""Open the software guest's serial shell with the same input devices as Opera tests."""
import json
import os
from pathlib import Path
import shlex
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'guest'))
from boot import command


def main():
    profile = json.loads(Path('/software/guest/profile.json').read_text())
    cmd = command(profile)
    cmd += ['-global', 'virtio-mmio.force-legacy=false',
            '-device', 'virtio-keyboard-device', '-device', 'virtio-tablet-device']
    print('Opening Mazda serial shell. UI services do not start automatically.', flush=True)
    print('Shut down the guest with: sync; poweroff -f', flush=True)
    print(shlex.join(cmd), flush=True)
    os.execvp(cmd[0], cmd)


if __name__ == '__main__':
    main()
