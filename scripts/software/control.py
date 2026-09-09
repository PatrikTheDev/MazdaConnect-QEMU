"""Inspect or capture the active software guest through its local QMP socket."""
import argparse
import json
from pathlib import Path
import socket
import struct
import zlib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('status', 'capture'))
    args = parser.parse_args()
    try:
        state = json.loads(Path('/software/live.json').read_text())
    except FileNotFoundError:
        raise SystemExit('No live software guest. Start it with just software-boot.')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(10)
        try:
            connection.connect(state['qmp'])
        except (FileNotFoundError, ConnectionRefusedError):
            raise SystemExit('The software guest is stopped. Start it with just software-boot.')
        stream = connection.makefile('rwb')
        json.loads(stream.readline())
        def call(name, arguments=None):
            request = {'execute': name}
            if arguments:
                request['arguments'] = arguments
            stream.write(json.dumps(request).encode() + b'\n')
            stream.flush()
            while True:
                response = json.loads(stream.readline())
                if 'error' in response:
                    raise RuntimeError(response['error'])
                if 'return' in response:
                    return response['return']
        call('qmp_capabilities')
        if args.action == 'status':
            print(json.dumps({'guest': call('query-status'), 'vnc': call('query-vnc'), 'diagnostics': state['directory']}, indent=2))
        else:
            path = Path('/workspace/artifacts/software-live.ppm')
            call('screendump', {'filename': str(path)})
            with path.open('rb') as source:
                if source.readline() != b'P6\n':
                    raise ValueError('Unexpected screenshot format')
                width, height = map(int, source.readline().split())
                if source.readline() != b'255\n':
                    raise ValueError('Unexpected screenshot color depth')
                rgb = source.read()
            if len(rgb) != width*height*3:
                raise ValueError('Incomplete screenshot')
            def chunk(kind, payload):
                return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind+payload))
            rows = b''.join(b'\0'+rgb[y*width*3:(y+1)*width*3] for y in range(height))
            path.with_suffix('.png').write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',width,height,8,2,0,0,0)) + chunk(b'IDAT',zlib.compress(rows)) + chunk(b'IEND',b''))
            print('Saved artifacts/software-live.png')


if __name__ == '__main__':
    main()
