"""Summarize observed service states and errors; this is not a completion gate."""
import argparse
from collections import Counter
import csv
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run', type=Path, help='Retained /software/test-* or /software/live-* directory')
parser.add_argument('--limit', type=int, default=20)
args = parser.parse_args()
if not 1 <= args.limit <= 100:
    parser.error('--limit must be between 1 and 100')
print('Observed service lifecycle (does not include absent services):')
states = {}
with (args.run / 'smevents.txt').open() as stream:
    for row in csv.DictReader(stream):
        if row['Event'].startswith('SM_SVC_CMD_'):
            states[row['Component']] = (row['Event'], row['Timestamp'])
for name, (state, timestamp) in sorted(states.items()):
    print(f'  {name}: {state} at {timestamp}s')

# Live capture currently retains one unrotated syslog; include rotated output
# where the bounded harness has retained it too.
counts = Counter()
markers = Counter()
for path in sorted(args.run.glob('syslog.log*')):
    for line in path.read_text(errors='replace').splitlines():
        for token in ('Uncaught exception', 'Unable to parse incoming MMUI',
                      'OnHeartbeatMissed', 'Transitions watchdog timer fired',
                      'Failed to create semaphore', 'SMDB handle not available'):
            if token in line:
                markers[token] += 1
        if ', Error,' in line or ', Warn,' in line:
            parts = line.split(', ')
            if len(parts) > 8:
                counts[', '.join([parts[1], *parts[6:]])] += 1
print('\nSelected failure markers:')
for token in ('Uncaught exception', 'Unable to parse incoming MMUI',
              'OnHeartbeatMissed', 'Transitions watchdog timer fired',
              'Failed to create semaphore', 'SMDB handle not available'):
    print(f'  {token}: {markers[token]}')
print('\nMost frequent logged warnings/errors (firmware severity is not a verdict):')
for message, count in counts.most_common(args.limit):
    print(f'  {count}: {message}')
