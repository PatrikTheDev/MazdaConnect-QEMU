"""Inspect or capture the active software guest through its local QMP socket."""
import argparse
import json
import os
from pathlib import Path
import socket
import struct
import zlib
from runtime import instance_name, state_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('status', 'capture', 'key'))
    parser.add_argument('key', nargs='?', choices=('left', 'right', 'up', 'down', 'ret', 'esc', 'backspace', 'm', 'n'))
    args = parser.parse_args()
    if (args.action == 'key') != (args.key is not None):
        parser.error('The key action requires a supported key name')
    try:
        instance = instance_name(os.environ.get('MAZDA_INSTANCE', 'live'))
        state = json.loads(state_path(instance).read_text())
    except FileNotFoundError:
        raise SystemExit('No live software guest. Start it with just start.')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(10)
        try:
            connection.connect(state['qmp'])
        except (FileNotFoundError, ConnectionRefusedError):
            raise SystemExit('The software guest is stopped. Start it with just start.')
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
        elif args.action == 'key':
            call('send-key', {'keys': [{'type': 'qcode', 'data': args.key}], 'hold-time': 100})
            print('Sent ' + args.key)
        else:
            path = Path(f'/workspace/artifacts/software-{instance}.ppm')
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
            print(f'Saved artifacts/software-{instance}.png')


if __name__ == '__main__':
    main()
