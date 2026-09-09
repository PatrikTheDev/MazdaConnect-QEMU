"""Inspect ABI function ranges and pointer tables in the original compositor."""
import argparse
from pathlib import Path
import struct
import re
import subprocess
from elftools.elf.elffile import ELFFile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('binary')
parser.add_argument('start', type=lambda x: int(x, 0))
parser.add_argument('end', type=lambda x: int(x, 0))
parser.add_argument('--table', action='store_true')
parser.add_argument('--pc-strings', action='store_true', help='Resolve ARM PC-relative literal strings in this function range')
args = parser.parse_args()
binary = Path('/software/sysroot') / args.binary
if args.pc_strings:
    with binary.open('rb') as stream:
        elf = ELFFile(stream)
        def read(address, size):
            for segment in elf.iter_segments():
                offset = address - segment['p_vaddr']
                if 0 <= offset < segment['p_filesz']:
                    return segment.data()[offset:offset+size]
            return b''
        disassembly = subprocess.check_output(['arm-linux-gnueabi-objdump', '-d',
            '--start-address=' + str(args.start), '--stop-address=' + str(args.end), str(binary)], text=True).splitlines()
        for index, line in enumerate(disassembly[:-1]):
            match = re.search(r'^\s*([0-9a-f]+):.*ldr\s+(\w+), \[pc,.*@ ([0-9a-f]+)', line)
            if not match:
                continue
            register = match[2]
            if not re.search(r'add\s+' + register + r', pc, ' + register, disassembly[index+1]):
                continue
            literal = read(int(match[3], 16), 4)
            if len(literal) != 4:
                continue
            address = (int(match[1], 16) + 12 + struct.unpack('<i', literal)[0]) & 0xffffffff
            raw = read(address, 256).split(b'\0')[0]
            if raw and all(32 <= c < 127 or c in (9,10,13) for c in raw):
                print(f'{match[1]} -> {address:08x}: {raw.decode()!r}')
    raise SystemExit(0)
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
