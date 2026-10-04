"""Disassemble a retained raster-worker instruction window, without executing it."""
import argparse
from pathlib import Path
import re
import struct
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run', type=Path)
parser.add_argument('sample', type=int)
parser.add_argument('tid', type=int)
args = parser.parse_args()
registers = None
words = {}
for line in (args.run / 'opera-samples.log').read_text(errors='replace').splitlines():
    match = re.fullmatch(r'WORKER sample=(\d+) tid=(\d+) .* pc=([0-9a-f]+) lr=([0-9a-f]+) sp=([0-9a-f]+) cpsr=([0-9a-f]+)', line)
    if match and (int(match[1]),int(match[2])) == (args.sample,args.tid):
        registers = tuple(int(match[index],16) for index in (3,4,5,6))
    match = re.fullmatch(r'WORKER_CODE sample=(\d+) tid=(\d+) address=([0-9a-f]+) value=([0-9a-f]+)', line)
    if match and (int(match[1]),int(match[2])) == (args.sample,args.tid):
        words[int(match[3],16)] = int(match[4],16)
if registers is None or not words:
    raise SystemExit('No retained instruction window for this sample/TID; use the updated software-worker-probe')
pc,lr,sp,cpsr = registers
addresses = sorted(words)
if len(words)>32 or addresses != list(range(addresses[0],addresses[-1]+4,4)):
    raise SystemExit('Invalid instruction window: require at most 32 contiguous words')
instruction_pc = pc & ~1
if not addresses[0] <= instruction_pc < addresses[-1]+4:
    raise SystemExit('Sampled PC is outside retained instruction window')
thumb = bool(cpsr & 0x20)
print(f'Sample {args.sample}, TID {args.tid}: PC=0x{pc:x} LR=0x{lr:x} SP=0x{sp:x} CPSR=0x{cpsr:x}, {"Thumb" if thumb else "ARM"}', flush=True)
print('Bounded bytes read while stopped; this is not a function boundary or an unwound caller.', flush=True)
with tempfile.TemporaryDirectory(prefix='mazda-worker-code-') as directory:
    path = Path(directory) / 'window.bin'
    data = b''.join(struct.pack('<I',words[address]) for address in addresses)
    base = addresses[0]
    if thumb:
        # Start at the sampled instruction boundary, not a guessed preceding
        # halfword which might be the second half of a Thumb-2 instruction.
        data = data[instruction_pc-base:]
        base = instruction_pc
    path.write_bytes(data)
    command = ['arm-linux-gnueabi-objdump','-D','-b','binary','-m','arm',
               '--adjust-vma=' + str(base)]
    if thumb:
        command += ['-M','force-thumb']
    subprocess.run([*command,str(path)],check=True)
