"""Exercise the recovered VIP protocol engine in the target ARM ABI."""
from pathlib import Path
import subprocess
import tempfile
with tempfile.TemporaryDirectory(prefix='vip-protocol-', dir='/software') as folder:
    binary = str(Path(folder) / 'check')
    subprocess.run(['arm-linux-gnueabi-gcc', '-static', '-O2', '-Wall', '-Wextra', '-Werror',
                    'src/software/vip-protocol.c', 'src/software/vip-protocol-check.c', '-o', binary], check=True)
    subprocess.run(['qemu-arm', binary], check=True)
