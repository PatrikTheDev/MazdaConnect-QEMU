"""Report sampled Opera PCs and per-thread CPU ticks without stopping workers."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run', type=Path)
parser.add_argument('--first', type=int, default=0)
parser.add_argument('--last', type=int, default=69)
args = parser.parse_args()
times, pcs, threads = {}, {}, defaultdict(dict)
workers, worker_maps = defaultdict(list), {}
for line in (args.run / 'opera-samples.log').read_text(errors='replace').splitlines():
    match = re.fullmatch(r'TIME sample=(\d+) wall=([\d.]+) mono=([\d.]+)', line)
    if match:
        times[int(match[1])] = (float(match[2]), float(match[3]))
    match = re.match(r'SAMPLE (\d+) .* r15=([0-9a-f]+)', line)
    if match:
        pcs[int(match[1])] = match[2]
    match = re.fullmatch(r'WORKER sample=(\d+) tid=(\d+) wall=([\d.]+) mono=([\d.]+) pc=([0-9a-f]+) lr=([0-9a-f]+) sp=([0-9a-f]+)', line)
    if match:
        workers[int(match[1])].append((int(match[2]), match[3], match[4], match[5]))
    match = re.fullmatch(r'WORKER_MAP sample=(\d+) tid=(\d+) ([0-9a-f]+)-([0-9a-f]+) (\S+) ([0-9a-f]+) \S+ \d+\s*(.*)', line)
    if match:
        worker_maps[(int(match[1]), int(match[2]))] = (int(match[3],16), int(match[6],16), match[5], match[7])
    match = re.fullmatch(r'THREAD sample=(\d+) (\d+) \((.*)\) (.*)', line)
    if match:
        fields = match[4].split()  # fields begin with state (proc stat field 3).
        if len(fields) < 20:
            raise SystemExit('Truncated thread stat record')
        key = (int(match[2]), int(fields[19]))  # Include start time for TID reuse.
        threads[int(match[1])][key] = (match[3], fields[0], int(fields[11])+int(fields[12]))
if not times or not threads:
    raise SystemExit('No timestamped thread data; use --sample-render with the updated sampler')
if args.first < 0 or args.last < args.first:
    parser.error('Require 0 <= --first <= --last')
selected = [sample for sample in times if args.first <= sample <= args.last]
if not selected:
    raise SystemExit(f'No samples in requested interval; retained range is {min(times)}..{max(times)}')
print(f'{len(selected)} samples selected; retained range {min(times)}..{max(times)}')
totals = defaultdict(int)
previous = {}
for sample in sorted(times):
    current = threads[sample]
    deltas = []
    for key, (name, state, ticks) in current.items():
        if key in previous:
            delta = ticks-previous[key][2]
            if delta < 0:
                raise SystemExit('Thread CPU counter moved backwards')
            if args.first <= sample <= args.last:
                totals[(key[0], name)] += delta
                deltas.append((delta, key[0], name, state))
    if args.first <= sample <= args.last:
        wall, mono = times[sample]
        stamp = datetime.fromtimestamp(wall, timezone.utc).strftime('%H:%M:%S.%f')[:-3]
        active = sorted(deltas, reverse=True)[:3]
        detail = ', '.join(f'{tid}:{name} +{delta}ticks {state}' for delta,tid,name,state in active if delta)
        print(f'{sample:2d} {stamp} mono={mono:.3f} pc={pcs.get(sample,"unknown")} {detail or "no observed CPU increment"}')
        for tid,wall,mono,pc in workers[sample]:
            mapped = worker_maps.get((sample,tid))
            location = 'mapping unavailable'
            if mapped:
                base,offset,permissions,path = mapped
                kind = 'file_offset' if path.startswith('/') else 'mapping_offset'
                location = f'{path or "anonymous"} {permissions} {kind}=0x{int(pc,16)-base+offset:x}'
            stamp = datetime.fromtimestamp(float(wall),timezone.utc).isoformat(timespec='milliseconds')
            print(f'   worker {tid} {stamp} mono={mono} pc={pc} {location}')
    previous = current
print('Observed CPU tick increments by thread (first observation and missing intervals excluded):')
for (tid,name),ticks in sorted(totals.items(), key=lambda pair: pair[1], reverse=True)[:12]:
    print(f'  {tid} {name}: {ticks} ticks')
print('Worker stat reads follow main-thread detach; snapshots are not simultaneous. Ptrace perturbs scheduling.')
if workers:
    print('Opt-in worker PCs were sampled with ptrace after their stat reads. A PC/mapping is not an unwound call stack or shader identity.')
