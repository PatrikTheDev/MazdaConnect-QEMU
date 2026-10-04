"""Verify retained full-guest userspace mappings against the approved boundary."""
import argparse
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run',type=Path)
args = parser.parse_args()
manifest = json.loads((args.run / 'kernel-build.json').read_text())
lines = (args.run / 'kernel-layout.log').read_text().splitlines()
if not lines or lines[0] != 'KERNEL_RELEASE='+manifest['version']:
    raise SystemExit('Observed kernel release does not match the completed 2 GiB build')
processes, regions, helpers = set(), 0, 0
current = None
for line in lines[1:]:
    marker = re.fullmatch(r'MAPS:/proc/(\d+)/maps',line)
    if marker:
        current = int(marker[1])
        continue
    region = re.match(r'^([0-9a-f]+)-([0-9a-f]+)\s+(\S+)\s+',line)
    if not region:
        raise SystemExit('Missing or malformed mapping record: '+line)
    if current is None:
        raise SystemExit('Mapping has no process marker')
    first,last = int(region[1],16),int(region[2],16)
    if first>=last:
        raise SystemExit('Invalid mapping bounds')
    # ARM's fixed user helper page is above TASK_SIZE, but is not an allocation.
    if first==0xffff0000 and last==0xffff1000 and line.endswith('[vectors]') and 'w' not in region[3]:
        helpers += 1
    elif last>0x80000000:
        raise SystemExit(f'Process {current} has a mapping above the monitor tag boundary: '+line)
    processes.add(current)
    regions += 1
if not processes or not regions:
    raise SystemExit('No userspace mapping evidence retained')
print(f'Kernel {manifest["version"]}: {regions} regions across {len(processes)} processes satisfy the 0x80000000 boundary; {helpers} fixed ARM helper pages excluded.')
print('Sequential /proc snapshots verify observed mappings, not every past/future allocation or monitor contention.')
