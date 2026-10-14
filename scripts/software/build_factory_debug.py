"""Build opt-in factory debug outputs from exact, unmodified EU firmware."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

SOURCE_HASHES = {
    'jci/gui/index.html': 'b0e116b941f29078ced19b864a1b888cf76d8bc3e4974af081efca4693e5c420',
    'jci/sm/sm.conf': 'fa3484d7c644393ab6cb083990e483201129a207e7755459296dde8ec82a4d84',
    'jci/testdiag/svcjcitestdiag.so': '73581b472ba9c47b75130e6e7111179c7cd2c2ceaef013bc6edb430233290033',
}


def verified(relative):
    data = (Path('/software/sysroot') / relative).read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_HASHES[relative]:
        raise ValueError('Factory debug requires verified EU 74.00.324A: ' + relative)
    return data


def build(home):
    source = verified('jci/gui/index.html')
    verified('jci/testdiag/svcjcitestdiag.so')
    if source.count(b'</body>') != 1:
        raise ValueError('Unexpected original GUI entry point')
    result = source.replace(b'</body>', b'<script src="file:///lab-software/factory-debug.js"></script>\n    </body>')
    (home / 'factory-debug.json').write_text(json.dumps({
        'source_sha256': SOURCE_HASHES,
        'index_output_sha256': hashlib.sha256(result).hexdigest(),
        'adaptations': ['Append lab keyboard/event tracing script',
                        'Enable original jciTestDiag; disable board reset/retries; CPU 0'],
        'native_binaries_modified': False,
    }, indent=2) + '\n')
    return result


def service_config(base_xml):
    base = ET.fromstring(base_xml)
    stock = ET.fromstring(verified('jci/sm/sm.conf'))
    service = stock.find('.//service[@name="jciTestDiag"]')
    if service is None:
        raise ValueError('Original jciTestDiag service missing')
    service.set('reset_board', 'no')
    service.set('retry_count', '0')
    service.set('affinity_mask', '0x01')
    base.find('services').append(service)
    return ET.tostring(base, encoding='utf-8', xml_declaration=True)
