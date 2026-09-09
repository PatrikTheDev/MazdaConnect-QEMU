"""Verify live VNC updates and exact browser pixels through the RFB protocol."""
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import time
from vnc_auth import challenge_response


def main():
    with Path('runs/software-vnc-test.log').open('w') as log:
        guest = subprocess.Popen([sys.executable, 'scripts/software/interactive.py',
                                  '--test-page', '--start-delay', '0', '--seconds', '100'],
                                 stdout=log, stderr=subprocess.STDOUT)
        connection = None
        try:
            deadline = time.monotonic()+90
            while time.monotonic() < deadline:
                if guest.poll() is not None:
                    raise RuntimeError('Live guest exited; inspect runs/software-vnc-test.log')
                try:
                    connection = socket.create_connection(('127.0.0.1', 5900), timeout=2)
                    break
                except ConnectionRefusedError:
                    time.sleep(0.2)
            if connection is None:
                raise RuntimeError('VNC did not start')
            connection.settimeout(15)
            def receive(size):
                data = bytearray()
                while len(data) < size:
                    part = connection.recv(size-len(data))
                    if not part:
                        raise RuntimeError('VNC disconnected')
                    data.extend(part)
                return data
            if receive(12) != b'RFB 003.008\n':
                raise RuntimeError('Unexpected VNC protocol')
            connection.sendall(b'RFB 003.008\n')
            methods = receive(receive(1)[0])
            if 2 not in methods or 1 in methods:
                raise RuntimeError('Expected password-authenticated VNC')
            connection.sendall(b'\2')
            connection.sendall(challenge_response(receive(16)))
            if receive(4) != b'\0'*4:
                raise RuntimeError('VNC handshake failed')
            connection.sendall(b'\1')
            init = receive(24)
            width, height = struct.unpack('>HH', init[:4])
            receive(struct.unpack('>I',init[20:24])[0])
            connection.sendall(b'\0\0\0\0'+struct.pack('>BBBBHHHBBBxxx',32,24,0,1,255,255,255,16,8,0))
            connection.sendall(struct.pack('>BBHii',2,0,2,0,-223))  # Raw + DesktopSize.
            pixels = bytearray(width*height*4)
            updates = 0
            while time.monotonic() < deadline:
                connection.sendall(struct.pack('>BBHHHH',3,0,0,0,width,height))
                message = receive(1)[0]
                if message != 0:
                    raise RuntimeError(f'Unexpected VNC message {message}')
                count = struct.unpack('>xH',receive(3))[0]
                for _ in range(count):
                    x,y,w,h,encoding = struct.unpack('>HHHHi',receive(12))
                    if encoding == -223:
                        width,height = w,h
                        pixels = bytearray(width*height*4)
                    elif encoding == 0:
                        data = receive(w*h*4)
                        if x+w>width or y+h>height:
                            raise RuntimeError('VNC rectangle exceeds desktop')
                        for row in range(h):
                            dest = ((y+row)*width+x)*4
                            pixels[dest:dest+w*4] = data[row*w*4:(row+1)*w*4]
                    else:
                        raise RuntimeError(f'Unexpected VNC encoding {encoding}')
                updates += 1
                def rgb(x,y):
                    offset = (y*width+x)*4
                    return tuple(pixels[offset:offset+3][::-1])
                if (width,height)==(800,480) and all(rgb(x,y)==color for x,y,color in (
                    (0,0,(22,50,79)), (100,150,(255,48,48)),
                    (400,150,(48,255,48)), (700,150,(48,48,255)))):
                    white = sum(pixels[i:i+3]==b'\xff\xff\xff' for i in range(0,800*100*4,4))
                    if white > 500 and updates > 1:
                        print(f'VNC verified: {updates} updates, 800x480 desktop, exact CSS colors and rendered text.')
                        break
                time.sleep(0.25)
            else:
                raise RuntimeError('VNC did not display the expected browser page')
        finally:
            if connection:
                connection.close()
            guest.send_signal(signal.SIGINT)
            try:
                guest.wait(timeout=25)
            except subprocess.TimeoutExpired:
                guest.kill()
                guest.wait()
        if guest.returncode:
            raise RuntimeError('Live guest did not stop cleanly')


if __name__ == '__main__':
    main()
