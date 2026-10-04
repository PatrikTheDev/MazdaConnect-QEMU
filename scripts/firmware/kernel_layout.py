"""Inspect the verified EU v74 kernel's linked address boundary without executing it."""
import ctypes
import ctypes.util
import hashlib
import json
from pathlib import Path
import struct
import zlib

source = Path('/lab/firmware/cmu150-eu-74.00.324A/boot/zImage')
image = source.read_bytes()
expected = '57fe0cda7c1f994a6ca6b3cce7d9cf247f3b5607ebf1ddc12f02598662d5e240'
if hashlib.sha256(image).hexdigest() != expected:
    raise SystemExit('Kernel layout inspection requires the verified EU 74.00.324A zImage')
# The earlier magic at 5792 belongs to the decompressor's constant table.
# The actual stream at 6116 uses the kernel's single Adler32 block-checksum form.
stream = image[6116:]
if stream[:9] != b'\x89LZO\x00\r\n\x1a\n' or struct.unpack_from('>I', stream, 17)[0] != 0x0300000d:
    raise SystemExit('Unexpected observed LZO header')
cursor = 34 + stream[33]
header_checksum = struct.unpack_from('>I', stream, cursor)[0]
if zlib.adler32(stream[9:cursor]) != header_checksum:
    raise SystemExit('Invalid LZO header checksum')
cursor += 4
library = ctypes.util.find_library('lzo2')
if not library:
    raise SystemExit('Install liblzo2 before inspecting the kernel')
decode = ctypes.CDLL(library).lzo1x_decompress_safe
decode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                   ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p]
decode.restype = ctypes.c_int
blocks = []
while True:
    size = struct.unpack_from('>I', stream, cursor)[0]
    cursor += 4
    if not size:
        break
    if size > 256*1024 or sum(map(len, blocks))+size > 8*1024*1024:
        raise SystemExit('Unexpected kernel block size')
    packed, checksum = struct.unpack_from('>II', stream, cursor)
    cursor += 8
    if not 0 < packed <= size or cursor+packed > len(stream):
        raise SystemExit('Invalid LZO block bounds')
    data = stream[cursor:cursor+packed]
    cursor += packed
    if packed != size:
        output = ctypes.create_string_buffer(size)
        count = ctypes.c_size_t(size)
        if decode(ctypes.create_string_buffer(data), packed, output, ctypes.byref(count), None) or count.value != size:
            raise SystemExit('LZO block decompression failed')
        data = output.raw
    if zlib.adler32(data) != checksum:
        raise SystemExit('LZO block checksum mismatch')
    blocks.append(data)
decoded = b''.join(blocks)
if hashlib.sha256(decoded).hexdigest() != 'b45da4c4e862f8261656ae74443a8a36582a861d9dfa42d8fdadee7a72a0cb85':
    raise SystemExit('Decoded kernel differs from the audited image')
self_address, boundary = struct.unpack_from('<II', decoded, 0x48)
if self_address != 0x80008048 or boundary != 0x80000000:
    raise SystemExit('Unexpected original kernel head literals')
print(json.dumps({
    'source_sha256': expected, 'decoded_sha256': hashlib.sha256(decoded).hexdigest(),
    'decoded_bytes': len(decoded), 'lzo_stream_offset': 6116,
    'linked_head_self_address': hex(self_address), 'kernel_virtual_base': hex(boundary),
    'embedded_ikconfig_present': b'IKCFG_ST' in decoded,
    'evidence': 'Head literal at 0x4c; page-table setup adds 0x80000000 at 0xec',
    'scope': 'Observed original kernel only; no kernel execution or profile change'
}, indent=2))
