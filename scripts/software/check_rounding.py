"""Check nearbyintf in the exact modern ARMEL runtime under Cortex-A15 TCG."""
from pathlib import Path
import hashlib
import subprocess
import tempfile

runtime = Path('/software/runtime-tree')
if not (runtime / 'ld-linux.so.3').exists():
    raise SystemExit('Build the software runtime first with just software-build')
with tempfile.TemporaryDirectory(prefix='mazda-rounding-') as directory:
    binary = Path(directory) / 'rounding-check'
    subprocess.run(['arm-linux-gnueabi-gcc','-O2','-Wall','-Wextra',
                    '-fno-builtin','-frounding-math','src/tools/rounding-check.c',
                    '-o',str(binary),'-lm'],check=True)
    print('QEMU user-mode Cortex-A15 with /software/runtime-tree loader/libm; not a full guest startup or timing benchmark.',flush=True)
    print('libm SHA256: ' + hashlib.sha256((runtime / 'libm.so.6').read_bytes()).hexdigest(),flush=True)
    result = subprocess.run(['qemu-arm','-cpu','cortex-a15',
        str(runtime / 'ld-linux.so.3'),'--library-path',str(runtime),str(binary)])
    raise SystemExit(result.returncode)
