"""Build a hash-checked, opt-in patch without changing reference firmware."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

SOURCE_HASH = '32431c6b74c8ba531fcc10c50748075416e0f7dc1a3f903f182d816a0f3f5fc2'


def build(home):
    source = Path('/software/sysroot/jci/mmui/uia/libjciuiasystem.so').read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_HASH:
        raise ValueError('Intro race patch requires the verified EU 74.00.324A MMUI binary')
    phoff, = struct.unpack_from('<I', source, 28)
    shoff, = struct.unpack_from('<I', source, 32)
    phsize, phnum, shsize, shnum = struct.unpack_from('<HHHH', source, 42)
    headers = [list(struct.unpack_from('<8I', source, phoff + i * phsize)) for i in range(phnum)]
    loads = [p for p in headers if p[0] == 1]
    if phsize != 32 or shsize != 40 or len(loads) != 2:
        raise ValueError('Unexpected ELF layout')
    text, data = loads
    boundary = text[4]
    if text[1:3] != [0, 0] or boundary != data[1] or data[2] - boundary != 0x8000:
        raise ValueError('Expected the original 32 KiB virtual gap between LOAD segments')
    code_address = (boundary + 3) & ~3
    state_address = data[2] + data[5]
    if state_address % 4:
        raise ValueError('Unaligned patch state storage')
    obj, elf, raw = (home / name for name in ('intro-fix.o', 'intro-fix.elf', 'intro-fix.bin'))
    subprocess.run(['arm-linux-gnueabi-as', '-march=armv7-a', '-o', str(obj),
                    'src/software/intro-race-fix.S'], check=True)
    symbols = {'state_storage': state_address, 'state_continue': 0x2a4d4,
               'set_app_context': 0xc38c, 'send_event': 0x8d8c}
    subprocess.run(['arm-linux-gnueabi-ld', '-Ttext=' + hex(code_address), '-e', 'state_hook',
                    *['--defsym=' + key + '=' + hex(value) for key, value in symbols.items()],
                    '-o', str(elf), str(obj)], check=True)
    subprocess.run(['arm-linux-gnueabi-objcopy', '-O', 'binary', '-j', '.text', str(elf), str(raw)], check=True)
    labels = {line.split()[2]: int(line.split()[0], 16) for line in
              subprocess.check_output(['arm-linux-gnueabi-nm', str(elf)], text=True).splitlines()
              if len(line.split()) == 3}
    code = raw.read_bytes()
    if code_address + len(code) > data[2]:
        raise ValueError('Patch exceeds the original virtual gap')
    # Insert file space to match the existing virtual gap. All original virtual
    # addresses, relocations, symbols and section indices stay unchanged.
    result = bytearray(source[:boundary] + bytes(0x8000) + source[boundary:])
    result[code_address:code_address + len(code)] = code
    text[4] = text[5] = code_address + len(code)
    data[5] += 4  # zero-initialized state, in the existing writable LOAD
    for i, header in enumerate(headers):
        if header[1] >= boundary:
            header[1] += 0x8000
        struct.pack_into('<8I', result, phoff + i * phsize, *header)
    new_shoff = shoff + 0x8000
    struct.pack_into('<I', result, 32, new_shoff)
    for i in range(shnum):
        section = list(struct.unpack_from('<10I', source, shoff + i * shsize))
        if section[4] >= boundary:
            section[4] += 0x8000
        if section[1] == 8 and section[3] + section[5] == state_address:
            section[5] += 4
        struct.pack_into('<10I', result, new_shoff + i * shsize, *section)
    for address, expected, target, link in ((0x2a4d0, 0xe92d4030, labels['state_hook'], False),
                                            (0x1982c, 0xebffcad6, labels['finish_hook'], True)):
        if struct.unpack_from('<I', source, address)[0] != expected:
            raise ValueError('Unexpected original instruction at ' + hex(address))
        displacement = target - address - 8
        if displacement % 4 or not -(1 << 25) <= displacement < (1 << 25):
            raise ValueError('ARM branch target out of range')
        struct.pack_into('<I', result, address, (0xeb000000 if link else 0xea000000) | ((displacement >> 2) & 0xffffff))
    report = {'source_sha256': SOURCE_HASH, 'patched_sha256': hashlib.sha256(result).hexdigest(),
              'code_address': hex(code_address), 'state_address': hex(state_address),
              'purpose': 'Resume original Disclaimer after completed intro when system is already Normal'}
    (home / 'intro-race-fix.json').write_text(json.dumps(report, indent=2) + '\n')
    return bytes(result)
