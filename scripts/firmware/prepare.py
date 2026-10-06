"""Prepare the supported local firmware input; never fetch firmware."""
from pathlib import Path
import subprocess
import sys

from manage import STORE, extract, install, manifest


def main():
    cfg_path = 'config/firmware/cmu150-eu-74.00.324A.json'
    cfg = manifest(cfg_path)
    package = install(sys.argv[1], cfg)
    outer = STORE / cfg['id'] / 'outer'
    if not outer.exists():
        extract(package, outer)
    else:
        print('Reusing the existing atomic outer extraction of the verified input.', flush=True)
    for script, args in (
        ('firmware/analyze.py', [cfg_path]),
        ('guest/kernel.py', []),
        ('firmware/resources.py', [cfg_path]),
        ('guest/resources_disk.py', [cfg['id']]),
        ('guest/build.py', [cfg_path]),
    ):
        subprocess.run([sys.executable, 'scripts/' + script, *args], check=True)


if __name__ == '__main__':
    main()
