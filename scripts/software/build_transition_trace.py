"""Generate logging-only instrumentation for original transition completion."""
import hashlib
import json
from pathlib import Path

SOURCE_HASH = 'd2ff7c0da76757d3aa211dcf99708976c1b0b34c9365664336a3618f77b6ab08'


def build(home):
    source = Path('/software/sysroot/jci/gui/common/transitions/js/Transitions.js').read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_HASH:
        raise ValueError('Transition trace requires verified EU 74.00.324A source')
    text = source.decode()
    hooks = {
        'Transitions.prototype._setCleanupByEventListener = function(domElement) {':
            'log.info("LAB_TRANSITION listen " + domElement.id + " classes=" + domElement.className);',
        'Transitions.prototype._animationEndEventCallback = function(evt) {':
            'log.info("LAB_TRANSITION template event " + evt.type + " target=" + evt.target.id + " name=" + evt.animationName + " elapsed=" + evt.elapsedTime);',
        'Transitions.prototype._animateGlobalCtrlComplete = function(evt) {':
            'log.info("LAB_TRANSITION global event " + evt.type + " target=" + evt.target.id + " name=" + evt.animationName + " elapsed=" + evt.elapsedTime);',
        'Transitions.prototype._watchdogTimerCallback = function() {':
            'this._labTracePending();',
    }
    for before, log in hooks.items():
        if text.count(before) != 1:
            raise ValueError('Unexpected transition trace site: ' + before)
        text = text.replace(before, before + '\n    ' + log)
    text += Path('src/software/transition-trace.js').read_text()
    result = text.encode()
    (home / 'transition-trace.json').write_text(json.dumps({
        'source_sha256': SOURCE_HASH, 'traced_sha256': hashlib.sha256(result).hexdigest(),
        'purpose': 'Logging only; original callbacks, timers and animation classes unchanged'
    }, indent=2) + '\n')
    return result
