"""Report compositor stage durations; excludes idle gaps between frames."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re
import statistics

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run', type=Path)
parser.add_argument('--timeline', action='store_true', help='Print UTC frame intervals and stage durations for comparison with transition logs')
args = parser.parse_args()
expected = ['begin', 'updated', 'painted', 'displayed', 'saved', 'callbacks']
frames = []
current = {}
scheduled = None
for line in (args.run / 'compositor.log').read_text(errors='replace').splitlines():
    match = re.fullmatch(r'RENDER (\d+\.\d+) (\w+)', line)
    if not match:
        continue
    stamp, stage = float(match[1]), match[2]
    if stage == 'schedule':
        scheduled = stamp
    if stage == 'begin':
        current = {}
        if scheduled is not None and scheduled <= stamp:
            current['schedule'] = scheduled
        scheduled = None
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
if args.timeline:
    print('UTC frame intervals; paint / display / save / total in ms; scheduled timer wait in ms:')
    for frame in frames:
        def utc(stage):
            return datetime.fromtimestamp(frame[stage], timezone.utc).isoformat(timespec='milliseconds')
        durations = [1000*(frame[b]-frame[a]) for a,b in (
            ('updated','painted'), ('painted','displayed'),
            ('displayed','saved'), ('begin','callbacks'))]
        timer = f'{1000*(frame["begin"]-frame["schedule"]):.2f}' if 'schedule' in frame else 'unpaired'
        print(f'{utc("begin")} -> {utc("callbacks")} ' + ' / '.join(f'{value:.2f}' for value in durations) + f'; timer={timer}')
    print('Wall-clock timestamps include tracing overhead; intervals do not measure browser rendering or client dispatch.')
