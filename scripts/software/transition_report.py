"""Print transition events and watchdog evidence from a retained UI probe."""
import argparse
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run', type=Path)
args = parser.parse_args()
manifest = args.run / 'transition-trace.json'
if manifest.exists():
    print(manifest.read_text().strip())
count = 0
for name in ('syslog.log.0', 'syslog.log'):
    path = args.run / name
    if not path.exists():
        continue
    for line in path.read_text(errors='replace').splitlines():
        if not any(marker in line for marker in (
                'LAB_TRANSITION', 'Transitions watchdog timer fired',
                "' transition. ")):
            continue
        stamp = re.search(r'\[([^]]+)\]', line)
        message = line.split('LAB_TRANSITION', 1)
        detail = 'LAB_TRANSITION' + message[1] if len(message) == 2 else line
        print((stamp.group(1) + ' ' if stamp else '') + detail)
        count += 1
if not count:
    raise SystemExit('No transition evidence found; run just dev software task opera --audio-devices --audio-services --probe-vip-service --live-output --seconds 90 --debug-services --capture-sequence --renderer llvmpipe --intro-race-fix --time-services --time-deadline-fix --websockets-queue-fix --trace-transitions.')
print('Event timestamps include diagnostic logging overhead; this is not a performance benchmark.')
