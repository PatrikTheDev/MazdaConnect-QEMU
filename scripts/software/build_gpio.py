"""Build the lab signal module against the exact pinned guest kernel headers."""
from pathlib import Path
import shutil
import subprocess


def build(home, version, headers=None):
    home.mkdir(parents=True, exist_ok=True)
    target = home / 'gpio-build'
    target.mkdir(exist_ok=True)
    for name in ('Makefile', 'mazda_gpio.c', 'mazda_vip.c', 'vip-transport.h'):
        shutil.copyfile(Path('src/software/gpio') / name, target / name)
    headers = Path(headers) if headers else Path('/usr/src') / ('linux-headers-' + version)
    if not headers.exists():
        raise RuntimeError('Matching GPIO build headers are missing. Run just software-image.')
    subprocess.run(['make', '-C', str(headers), 'ARCH=arm',
                    'CROSS_COMPILE=arm-linux-gnueabi-', 'M=' + str(target), 'modules'], check=True)
    return target / 'mazda_gpio.ko'


if __name__ == '__main__':
    import json
    version = json.loads(Path('config/kernel/debian-armmp.json').read_text())['version']
    print(build(Path('/software/gpio-only'), version))
