"""Inspect ABI function ranges and pointer tables in the original compositor."""
import argparse
from pathlib import Path
import struct
import subprocess
from elftools.elf.elffile import ELFFile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('binary')
parser.add_argument('start', type=lambda x: int(x, 0))
parser.add_argument('end', type=lambda x: int(x, 0))
parser.add_argument('--table', action='store_true')
args = parser.parse_args()
binary = Path('/software/sysroot') / args.binary
if not args.table:
    subprocess.run(['arm-linux-gnueabi-objdump', '-d', '--start-address=' + str(args.start),
                    '--stop-address=' + str(args.end), str(binary)], check=True)
else:
    with binary.open('rb') as stream:
        elf = ELFFile(stream)
        def data(address, size):
            for segment in elf.iter_segments():
                if segment['p_vaddr'] <= address < segment['p_vaddr'] + segment['p_filesz']:
                    offset = address - segment['p_vaddr']
                    return segment.data()[offset:offset+size]
            return b''
        for address in range(args.start, args.end, 4):
            value, = struct.unpack('<I', data(address, 4))
            raw = data(value, 120).split(b'\0')[0]
            label = raw.decode() if raw and all(32 <= c < 127 or c == 10 for c in raw) else ''
            print(f'{address:08x}: {value:08x} {label}')
