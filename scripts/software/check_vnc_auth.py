"""Test VNC authentication without booting or rebuilding the shared Mazda guest."""
import socket
import subprocess
import time

from vnc_auth import VNC_PASSWORD, challenge_response, vnc_options


def main():
    process = subprocess.Popen(['qemu-system-arm', '-machine', 'none', '-S',
                                '-nodefaults', '-display', 'none',
                                *vnc_options('127.0.0.1:96')],
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for password, expected_success in (('incorrect', False), (VNC_PASSWORD, True)):
            deadline = time.monotonic()+10
            while True:
                try:
                    connection = socket.create_connection(('127.0.0.1', 5996), timeout=2)
                    break
                except ConnectionRefusedError:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError('Isolated VNC test server failed to start')
                    time.sleep(0.1)
            with connection:
                def receive(size):
                    data = bytearray()
                    while len(data) < size:
                        part = connection.recv(size-len(data))
                        if not part:
                            raise RuntimeError('VNC disconnected')
                        data.extend(part)
                    return bytes(data)
                assert receive(12) == b'RFB 003.008\n'
                connection.sendall(b'RFB 003.008\n')
                methods = receive(receive(1)[0])
                assert 2 in methods and 1 not in methods, methods
                connection.sendall(b'\2')
                connection.sendall(challenge_response(receive(16), password))
                success = receive(4) == b'\0'*4
                assert success == expected_success
        print('VNC password authentication verified: correct password accepted; incorrect password rejected.')
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == '__main__':
    main()
