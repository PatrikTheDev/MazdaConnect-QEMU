"""Add original time services to an opt-in diagnostic service profile."""
import hashlib
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET


def service_config(base_xml):
    base = ET.fromstring(base_xml)
    stock = ET.parse('/software/sysroot/jci/sm/sm.conf')
    destination = base.find('services')
    for name in ('stage_2', 'jciTime', 'jciBLMTIME'):
        service = stock.find(f'.//service[@name="{name}"]')
        if service is None:
            raise ValueError('Missing original time dependency: ' + name)
        service.set('affinity_mask', '0x01')
        service.set('reset_board', 'no')
        service.set('retry_count', '0')
        destination.append(service)
    return ET.tostring(base, encoding='utf-8', xml_declaration=True)


SOURCE_HASH = 'f06789afd378aa164aa9f6322be2c0ddff3fd893768e858088f9676c7e9e8a2f'
DEADLINE_CLOCK_OFFSET = 0xd594


def build(home):
    """Correct the clock domain of the original sem_timedwait deadline only."""
    source = Path('/software/sysroot/jci/time/svcjciblmtime.so').read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_HASH:
        raise ValueError('Time deadline patch requires the verified EU 74.00.324A BLM binary')
    if struct.unpack_from('<I', source, DEADLINE_CLOCK_OFFSET)[0] != 0xe3a00001:
        raise ValueError('Unexpected BLM_TIME_SemTimedWait clock instruction')
    result = bytearray(source)
    # ARM mov r0, #1 (MONOTONIC) -> mov r0, #0 (REALTIME).
    # Stock glibc 2.11.1 sem_timedwait subtracts gettimeofday from this deadline.
    struct.pack_into('<I', result, DEADLINE_CLOCK_OFFSET, 0xe3a00000)
    report = {'source_sha256': SOURCE_HASH,
              'patched_sha256': hashlib.sha256(result).hexdigest(),
              'file_offset': hex(DEADLINE_CLOCK_OFFSET),
              'virtual_address': hex(DEADLINE_CLOCK_OFFSET),
              'original_instruction': '0xe3a00001', 'patched_instruction': '0xe3a00000',
              'purpose': 'Use CLOCK_REALTIME for the stock sem_timedwait absolute deadline; preserve timeout and readiness checks'}
    (home / 'time-deadline-fix.json').write_text(json.dumps(report, indent=2) + '\n')
    return bytes(result)
