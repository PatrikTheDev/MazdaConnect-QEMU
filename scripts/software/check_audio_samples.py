"""Verify original 1 kHz left / 2 kHz right test audio reached QEMU's output."""
import array
import argparse
import math
from pathlib import Path
import sys
import wave

def verify(path, frequencies):
    with wave.open(str(path)) as stream:
        if stream.getnchannels() != len(frequencies) or stream.getsampwidth() != 2:
            raise SystemExit(f'{path.name}: unexpected channel count or sample format')
        rate = stream.getframerate()
        samples = array.array('h', stream.readframes(stream.getnframes()))
    if sys.byteorder != 'little':
        samples.byteswap()
    for channel, frequency in enumerate(frequencies):
        data = samples[channel::len(frequencies)]
        active = [i for i, x in enumerate(data) if abs(x) > 64]
        if not active:
            raise SystemExit(f'{path.name}: silent samples')
        data = data[active[0]:active[-1]+1]
        energy = sum(x*x for x in data)
        if len(data) < rate // 2 or energy == 0:
            raise SystemExit(f'{path.name}: missing samples')
        real = sum(x * math.cos(2*math.pi*frequency*i/rate) for i, x in enumerate(data))
        imag = sum(x * math.sin(2*math.pi*frequency*i/rate) for i, x in enumerate(data))
        fraction = 2*(real*real + imag*imag)/(len(data)*energy)
        print(f'{path.name} channel {channel}: {frequency} Hz energy fraction {fraction:.3f}')
        if fraction < 0.2:
            raise SystemExit(f'{path.name}: expected test tone missing')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--capture-tone', type=int)
    args = parser.parse_args()
    verify(args.directory / 'audio0.wav', (1000, 2000))
    if args.capture_tone:
        verify(args.directory / 'mic.wav', (args.capture_tone, args.capture_tone))
        verify(args.directory / 'bluetooth.wav', (args.capture_tone,))
    print('PCM test tones verified; audio-service readiness remains a separate requirement.')
