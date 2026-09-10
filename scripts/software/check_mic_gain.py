"""Verify the approved HDA mixer mapping changes actual captured samples."""
import array
import argparse
import ctypes
from pathlib import Path
import math
import sys
import wave


def verify_gain(home, diagnostic):
    for operation in ('MIC_LEVEL', 'MIC_HALF_MIXER', 'MIC_HALF_CAPTURE'):
        if f'AUDIO_{operation}_RC=0' not in diagnostic.splitlines():
            raise SystemExit('Microphone gain operation failed: ' + operation)
    def levels(name):
        with wave.open(str(home / name)) as stream:
            if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (2, 2, 48000):
                raise SystemExit('Unexpected microphone format')
            samples = array.array('h', stream.readframes(stream.getnframes()))
        if sys.byteorder != 'little':
            samples.byteswap()
        if len(samples) < 48000:
            raise SystemExit('Insufficient microphone capture')
        # Discard opening/closing transients equally, retaining the middle half.
        samples = samples[len(samples)//4:3*len(samples)//4]
        return [math.sqrt(sum(x*x for x in samples[c::2]) / len(samples[c::2])) for c in (0,1)]
    # Pinned QEMU 7.2 scales raw HDA 37/74 to 127/255, then its PA backend
    # scales that into pa_volume_t. Ask the installed PulseAudio library for
    # the resulting amplitude: its UI volume scale is nonlinear.
    if "Capture 74 [100%] [0.00dB]" not in diagnostic or "Capture 37 [50%] [-37.00dB]" not in diagnostic:
        raise SystemExit('Unexpected HDA range/readback; re-audit backend gain mapping')
    pulse = ctypes.CDLL('libpulse.so.0')
    pulse.pa_sw_volume_to_linear.argtypes = [ctypes.c_uint32]
    pulse.pa_sw_volume_to_linear.restype = ctypes.c_double
    expected = pulse.pa_sw_volume_to_linear((65536 * (37 * 255 // 74)) // 255)
    print(f'QEMU/PulseAudio expected half-control amplitude ratio: {expected:.3f}')
    full, half = levels('mic.wav'), levels('mic-half.wav')
    for channel in (0,1):
        if full[channel] < 100:
            raise SystemExit('Microphone reference is silent')
        ratio = half[channel]/full[channel]
        print(f'MIC Level channel {channel}: RMS full={full[channel]:.1f} half={half[channel]:.1f} ratio={ratio:.3f}')
        if not expected * 0.9 < ratio < expected * 1.1:
            raise SystemExit('HDA capture attenuation did not follow the requested gain')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    verify_gain(args.run, (args.run / 'audio-check.log').read_text())
