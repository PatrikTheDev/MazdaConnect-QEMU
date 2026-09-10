"""Report compositor stage durations; excludes idle gaps between frames."""
import argparse
from collections import defaultdict
from pathlib import Path
import re
import statistics

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run', type=Path)
args = parser.parse_args()
expected = ['begin', 'updated', 'painted', 'displayed', 'saved', 'callbacks']
frames = []
current = {}
for line in (args.run / 'compositor.log').read_text(errors='replace').splitlines():
    match = re.fullmatch(r'RENDER (\d+\.\d+) (\w+)', line)
    if not match:
        continue
    stamp, stage = float(match[1]), match[2]
    if stage == 'begin':
        current = {}
    if stage in expected:
        current[stage] = stamp
    if stage == 'callbacks' and all(key in current for key in expected):
        if all(current[b] >= current[a] for a, b in zip(expected, expected[1:])):
            frames.append(current)
        current = {}
if not frames:
    raise SystemExit('No complete timed frames in retained compositor.log')
samples = defaultdict(list)
for frame in frames:
    for a, b in zip(expected, expected[1:]):
        samples[a + ' -> ' + b].append(1000*(frame[b]-frame[a]))
    samples['total'].append(1000*(frame['callbacks']-frame['begin']))
print(f'{len(frames)} complete frames; durations in ms, excluding idle intervals')
for label, values in samples.items():
    ordered = sorted(values)
    print(f'{label:23s} median={statistics.median(values):8.2f} p95={ordered[int((len(ordered)-1)*.95)]:8.2f} max={max(values):8.2f}')
