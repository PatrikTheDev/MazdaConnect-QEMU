"""Private, clocked PCM backend for QEMU HDA; no host audio devices required."""
import array
import math
import os
from pathlib import Path
import subprocess
import threading
import time
import wave


class AudioBackend:
    def __init__(self, home, tone=0, record=True):
        self.home = Path(home)
        self.tone = tone
        self.record = record
        self.processes = []
        self.files = []
        self.stop = threading.Event()
        self.thread = None

    def start(self):
        runtime = self.home / 'pulse'
        runtime.mkdir(mode=0o700)
        self.env = dict(os.environ, PULSE_RUNTIME_PATH=str(runtime),
                        PULSE_SERVER='unix:' + str(runtime / 'socket'))
        config = runtime / 'server.pa'
        config.write_text(
            f'load-module module-native-protocol-unix socket={runtime}/socket auth-anonymous=1\n'
            'load-module module-null-sink sink_name=speaker0 rate=48000 channels=2\n'
            'load-module module-null-sink sink_name=speaker1 rate=48000 channels=2\n'
            f'load-module module-pipe-source source_name=microphone file={runtime}/microphone.pcm format=s16le rate=48000 channels=2\n')
        log = (self.home / 'audio-backend.log').open('wb')
        self.files.append(log)
        try:
            server = subprocess.Popen(['pulseaudio', '--daemonize=no', '--use-pid-file=no',
                '--exit-idle-time=-1', '--disable-shm=yes', '-n', '-F', str(config)],
                env=self.env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            self.processes.append(server)
            deadline = time.monotonic() + 5
            while not (runtime / 'socket').exists() or not (runtime / 'microphone.pcm').exists():
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Private audio server failed; inspect audio-backend.log')
                time.sleep(0.05)
            self.thread = threading.Thread(target=self.feed, args=(runtime / 'microphone.pcm',), daemon=True)
            self.thread.start()
            for index in range(2) if self.record else ():
                output = (self.home / f'audio{index}.raw').open('wb')
                self.files.append(output)
                recorder = subprocess.Popen(['parec', '--raw', '--format=s16le', '--rate=48000',
                    '--channels=2', f'--device=speaker{index}.monitor'], env=self.env,
                    stdin=subprocess.DEVNULL, stdout=output, stderr=log)
                self.processes.append(recorder)
            return self
        except BaseException:
            self.close()
            raise

    def feed(self, path):
        fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        try:
            position = 0
            deadline = time.monotonic()
            while not self.stop.is_set():
                data = array.array('h')
                for frame in range(960):
                    sample = int(8000 * math.sin(2 * math.pi * self.tone * (position + frame) / 48000)) if self.tone else 0
                    data.extend((sample, sample))
                position += 960
                pending = memoryview(data.tobytes())
                while pending and not self.stop.is_set():
                    try:
                        pending = pending[os.write(fd, pending):]
                    except BlockingIOError:
                        self.stop.wait(0.005)
                deadline = max(deadline + 0.02, time.monotonic())
                self.stop.wait(max(0, deadline - time.monotonic()))
        finally:
            os.close(fd)

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=2)
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for stream in self.files:
            stream.close()
        for index in range(2):
            raw = self.home / f'audio{index}.raw'
            if raw.exists():
                with wave.open(str(self.home / f'audio{index}.wav'), 'wb') as output:
                    output.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
                    with raw.open('rb') as source:
                        while chunk := source.read(65536):
                            output.writeframes(chunk)
