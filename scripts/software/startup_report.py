"""Print original startup milestones from a retained software probe's syslog."""
import argparse
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run', type=Path, help='Retained /software/test-* or /software/live-* directory')
args = parser.parse_args()
patterns = [
    ('system Normal', re.compile(r'system_smm_StateEnter .*SYSTEM_NormalState$')),
    ('SM boot finished', re.compile(r'system_smm_TopStateHandler .*Bootup finished!')),
    ('MMUI event', re.compile(r'UIA_SYSTEM_EventCallback .*event = (ShowDisclaimer|StartIntroAnimation|FinishIntroAnimation|DisposeIntroVideo)$')),
    ('intro launched', re.compile(r'UIA_SYSTEM_GetStartUpSettings .*tranlogo is started')),
    ('intro finished', re.compile(r'UIA_SYSTEM_OnFinishIntroAnimation .*Intro Animation is finished')),
    ('HMI ready', re.compile(r'UIA_SYSTEM_SYSTEM_sendHMIReady .*Tell BLM_SYTEM')),
    ('GUI context', re.compile(r'GUI_FRAMEWORK.*Recv ctxtChg:')),
    ('GUI exception', re.compile(r'GUI_FRAMEWORK.*Uncaught exception:')),
    ('browser watchdog', re.compile(r'OnHeartbeatMissed')),
]
count = 0
with (args.run / 'syslog.log').open(errors='replace') as stream:
    for number, line in enumerate(stream, 1):
        for label, pattern in patterns:
            if pattern.search(line):
                # Retain firmware timestamps and exact evidence instead of inferring readiness.
                print(f'{number:6d} [{label}] {line.rstrip()}')
                count += 1
                break
if not count:
    raise SystemExit('No startup milestones found; use a probe with --debug-services.')
print(f'\n{count} milestones from {args.run / "syslog.log"}; this report does not verify UI rendering.')
