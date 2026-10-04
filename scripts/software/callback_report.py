"""Measure original Opera frame callback waits and relative delivery lag."""
import argparse
from pathlib import Path
import re
import statistics

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run', type=Path)
args = parser.parse_args()
pending = {}
samples = []
previous = None
for line in (args.run / 'opera.log').read_text(errors='replace').splitlines():
    stamp = re.match(r'\[\s*(\d+\.\d+)\]', line)
    if not stamp:
        continue
    received = float(stamp[1])
    if previous is not None and received < previous:
        raise SystemExit('Wayland log clock moved backwards or wrapped; split the run before analysis')
    previous = received
    request = re.search(r' -> wl_surface@\d+\.frame\(new id wl_callback@(\d+)\)', line)
    if request:
        pending[request[1]] = received
    done = re.search(r'(?<! -> )wl_callback@(\d+)\.done\((\d+)\)', line)
    if done and done[1] in pending:
        requested = pending.pop(done[1])
        samples.append((received, int(done[2]), received-requested))
if not samples:
    raise SystemExit('No matched wl_surface.frame callbacks in retained Opera log')
if any(b[1] < a[1] for a, b in zip(samples, samples[1:])):
    raise SystemExit('Frame timestamp moved backwards or wrapped; cannot infer a stable clock offset')
offset = min(received-generated for received, generated, _ in samples)
lag = [received-generated-offset for received, generated, _ in samples]
waits = [wait for _, _, wait in samples]
print(f'{len(samples)} matched frame callbacks; {len(pending)} requests remain unmatched')
for name, values in [('request to delivery', waits), ('delivery lag above minimum', lag)]:
    ordered = sorted(values)
    print(f'{name}: median={statistics.median(values):.2f}ms p95={ordered[int((len(ordered)-1)*.95)]:.2f}ms max={max(values):.2f}ms')
print('Largest relative delivery lags (Opera log timestamp / original callback timestamp):')
for index in sorted(range(len(samples)), key=lambda i: lag[i], reverse=True)[:8]:
    received, generated, wait = samples[index]
    print(f'  {received:.3f} / {generated}: lag={lag[index]:.2f}ms request_wait={wait:.2f}ms')
print('Relative lag subtracts the minimum observed clock offset; it is not absolute latency.')
print('Assumes stable clock offset during the run. Includes server flush, scheduling and client dispatch delay.')
