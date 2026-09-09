"""Verify the patch against original firmware without modifying shared build output."""
import hashlib
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from build_time import build, service_config, SOURCE_HASH, DEADLINE_CLOCK_OFFSET

source_path = Path('/software/sysroot/jci/time/svcjciblmtime.so')
source = source_path.read_bytes()
with tempfile.TemporaryDirectory(prefix='time-fix-check-') as directory:
    home = Path(directory)
    patched = build(home)
    changes = [i for i, (before, after) in enumerate(zip(source, patched)) if before != after]
    assert len(source) == len(patched)
    assert changes == [DEADLINE_CLOCK_OFFSET], changes
    assert patched[DEADLINE_CLOCK_OFFSET:DEADLINE_CLOCK_OFFSET + 4] == bytes.fromhex('0000a0e3')
    report = json.loads((home / 'time-deadline-fix.json').read_text())
    assert report['patched_sha256'] == hashlib.sha256(patched).hexdigest()
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == SOURCE_HASH
    profile = ET.fromstring(service_config(Path('overlays/software/sm.conf').read_bytes()))
    for name in ('stage_2', 'jciTime', 'jciBLMTIME'):
        assert len(profile.findall(f'.//service[@name="{name}"]')) == 1
    print(json.dumps(report, indent=2))
    print('Verified one-byte instruction change, unchanged reference and original time-service profile.')
