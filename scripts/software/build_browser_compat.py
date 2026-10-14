"""Generate the approved developer-mode legacy Opera version-check adaptation."""
import hashlib
import json
from pathlib import Path

SOURCE_HASH = 'd2ff7c0da76757d3aa211dcf99708976c1b0b34c9365664336a3618f77b6ab08'


def build(home):
    source = Path('/software/sysroot/jci/gui/common/transitions/js/Transitions.js').read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_HASH:
        raise ValueError('Browser compatibility requires verified EU 74.00.324A Transitions.js')
    text = source.decode('utf-8')
    replacements = (
        ('log.debug("browser version " + window.opera.version());',
         'log.debug("browser version " + (window.opera && typeof window.opera.version === "function" ? window.opera.version() : "non-Opera"));'),
        ('if (window.opera)', 'if (window.opera && typeof window.opera.version === "function")'),
        ('log.fatal("The GUI can only run in the Opera Browser. Please re-open the GUI using Opera 12.10+");',
         'log.warn("LAB_BROWSER_COMPAT: continuing without the legacy Opera version API");'),
    )
    for before, after in replacements:
        if text.count(before) != 1:
            raise ValueError('Unexpected browser compatibility patch site: ' + before)
        text = text.replace(before, after)
    result = text.encode('utf-8')
    report = {'source_sha256': SOURCE_HASH,
              'patched_sha256': hashlib.sha256(result).hexdigest(),
              'purpose': 'Guard the legacy Opera version API and allow non-Opera transition initialization',
              'wire_format_changed': False}
    (home / 'browser-compat.json').write_text(json.dumps(report, indent=2) + '\n')
    return result
