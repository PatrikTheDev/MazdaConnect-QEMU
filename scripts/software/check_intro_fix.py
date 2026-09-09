"""Exercise the actual intro patch assembly under ARM emulation."""
from pathlib import Path
import subprocess
import tempfile

with tempfile.TemporaryDirectory(prefix='intro-fix-check-') as directory:
    binary = Path(directory) / 'check'
    subprocess.run(['arm-linux-gnueabi-gcc', '-static', '-march=armv7-a', '-O2',
                    '-Wall', '-Wextra', '-Werror', '-o', str(binary),
                    'src/software/intro-race-check.c', 'src/software/intro-race-fix.S'], check=True)
    subprocess.run(['qemu-arm', str(binary)], check=True)
