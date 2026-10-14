"""Generate approved developer-only browser adaptations from verified firmware."""
import hashlib
import json
from pathlib import Path

SOURCE_HASH = 'd2ff7c0da76757d3aa211dcf99708976c1b0b34c9365664336a3618f77b6ab08'
WEBSOCKETS_HASH = '40e21c3e7e661174f06b65c234788b3f0a78445685e0d784677f3dabc460cbd2'
DECODER_SITE = 'var rcvData = (new Uint8Array([].map.call(e.data, function(c) { return c.charCodeAt(0); } ))).buffer;'


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


def websocket_variants(home, queue_source):
    source = Path('/software/sysroot/jci/gui/framework/js/Websockets.js').read_bytes()
    queue_report = json.loads((home / 'websockets-queue-fix.json').read_text())
    if queue_report['source_sha256'] != WEBSOCKETS_HASH:
        raise ValueError('Browser decoder requires the verified queue patch source')
    variants = {}
    reports = {}
    for name, base, expected in (
        ('Websockets-browser-compat.js', source, WEBSOCKETS_HASH),
        ('Websockets-queue-browser-compat.js', queue_source, queue_report['patched_sha256']),
    ):
        if hashlib.sha256(base).hexdigest() != expected:
            raise ValueError('Browser decoder source differs from its verified input: ' + name)
        text = base.decode('utf-8')
        if text.count(DECODER_SITE) != 1:
            raise ValueError('Unexpected browser decoder patch site')
        # ArrayBuffer has neither indexed bytes nor length in standards browsers.
        # Retain the typed view so the original decoder can read its sequence byte.
        result = text.replace(DECODER_SITE, DECODER_SITE.replace(').buffer;', ');')).encode('utf-8')
        variants[name] = result
        reports[name] = {'source_sha256': expected,
                         'patched_sha256': hashlib.sha256(result).hexdigest()}
    report_path = home / 'browser-compat.json'
    report = json.loads(report_path.read_text())
    report['websockets_original_sha256'] = WEBSOCKETS_HASH
    report['websockets_purpose'] = 'Keep the Uint8Array view for JSON length and trailing sequence-byte decoding'
    report['websockets_variants'] = reports
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    return variants
