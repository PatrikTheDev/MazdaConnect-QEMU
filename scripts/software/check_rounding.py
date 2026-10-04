"""Check nearbyintf in the exact modern ARMEL runtime under Cortex-A15 TCG."""
from pathlib import Path
import argparse
import hashlib
import re
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run',type=Path,nargs='?',help='Read the retained full-guest rounding log instead of executing a user-mode check')
args = parser.parse_args()
if args.run:
    data = (args.run / 'rounding.log').read_text()
    print(data,end='',flush=True)
    status = re.findall(r'^ROUNDING_RC=(\d+)$',data,re.MULTILINE)
    if len(status)!=1:
        raise SystemExit('Missing or ambiguous full-guest rounding exit status')
    raise SystemExit(int(status[0]))

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
