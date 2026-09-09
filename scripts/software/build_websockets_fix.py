"""Generate the approved, opt-in transition queue correction from verified firmware."""
import hashlib
import json
from pathlib import Path

SOURCE_HASH = '40e21c3e7e661174f06b65c234788b3f0a78445685e0d784677f3dabc460cbd2'


def build(home):
    source = Path('/software/sysroot/jci/gui/framework/js/Websockets.js').read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_HASH:
        raise ValueError('Queue patch requires the verified EU 74.00.324A Websockets.js')
    text = source.decode('utf-8')
    replacements = (
        ('this._doRouteMmuiMsg(this._waitMsgArray[index]);',
         'this._doRouteMmuiMsg(this._waitMsgArray[index][0]);'),
        ('this._waitMsgArray.push(jsonStr);',
         'this._waitMsgArray.push([jsonStr, mMmuiWebsocketSeqCounter]);'),
        ('this._doRouteMmuiMsg(mStackOutput);  // send current msg   //★',
         'this._doRouteMmuiMsg(mStackOutput);\n                           this._delStack("transition", mMmuiWebsocketWaitSeqCounter);'),
    )
    for before, after in replacements:
        if text.count(before) != 1:
            raise ValueError('Unexpected queue patch site: ' + before)
        text = text.replace(before, after)
    start = text.index('function _isStack(')
    # These two helpers are the original file's final definitions.
    if text[start:].count('function ') != 2 or not text.rstrip().endswith('}'):
        raise ValueError('Unexpected queue helper layout')
    text = text[:start] + Path('src/software/websockets-queue-helpers.js').read_text()
    result = text.encode('utf-8')
    report = {'source_sha256': SOURCE_HASH,
              'patched_sha256': hashlib.sha256(result).hexdigest(),
              'purpose': 'Bind queue helpers, match parsed type and sequence, keep tuple entries and remove delivered transitions',
              'wire_format_changed': False}
    (home / 'websockets-queue-fix.json').write_text(json.dumps(report, indent=2) + '\n')
    return result
