"""Check a running developer GUI's HTTP assets and native WebSocket handshakes."""
import argparse
import base64
import hashlib
import http.client
import os
import socket


def verify(host, http_port=8080):
    for path, expected in (('/', b'<title>HMI GUI</title>'),
                           ('/common/transitions/js/Transitions.js', b'LAB_BROWSER_COMPAT'),
                           ('/framework/js/Websockets.js', b'var rcvData = (new Uint8Array([].map.call(e.data, function(c) { return c.charCodeAt(0); } )));')):
        connection = http.client.HTTPConnection(host, http_port, timeout=10)
        try:
            connection.request('GET', path)
            response = connection.getresponse()
            if response.status != 200 or expected not in response.read():
                raise RuntimeError('Unexpected developer HTTP response: ' + path)
        finally:
            connection.close()
    for port, protocol in ((2700, 'ihu-guiifm-protocol'), (2766, 'ihu-dbapi-protocol'),
                           (2800, 'ihu-appsdk-protocol')):
        key = base64.b64encode(os.urandom(16)).decode()
        with socket.create_connection((host, port), timeout=10) as connection:
            connection.sendall((f'GET / HTTP/1.1\r\nHost: {host}:{port}\r\n'
                                'Upgrade: websocket\r\nConnection: Upgrade\r\n'
                                f'Origin: http://{host}:{http_port}\r\n'
                                f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n'
                                f'Sec-WebSocket-Protocol: {protocol}\r\n\r\n').encode())
            header = bytearray()
            while b'\r\n\r\n' not in header:
                part = connection.recv(4096)
                if not part or len(header) + len(part) > 65536:
                    raise RuntimeError(f'Incomplete WebSocket handshake on {port}')
                header.extend(part)
            lines = header.split(b'\r\n\r\n', 1)[0].decode().split('\r\n')
            fields = {name.lower(): value.strip() for name, value in
                      (line.split(':', 1) for line in lines[1:])}
            accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
            if (lines[0].split()[1] != '101' or fields.get('sec-websocket-accept') != accept
                    or fields.get('sec-websocket-protocol') != protocol):
                raise RuntimeError(f'Invalid WebSocket handshake on {port}')
        print(f'WebSocket {port}: upgrade and {protocol} verified')
    print('Developer HTTP assets and all three WebSocket endpoints verified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='mazda-software-' + os.environ.get('MAZDA_INSTANCE', 'live'))
    parser.add_argument('--http-port', type=int, default=8080)
    args = parser.parse_args()
    verify(args.host, args.http_port)
