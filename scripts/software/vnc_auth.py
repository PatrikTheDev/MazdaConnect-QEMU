"""Password authentication for the loopback-only development VNC viewer."""
import subprocess

# Deliberately public lab credential; the viewer is published only on loopback.
VNC_PASSWORD = 'mazda'


def vnc_options(display):
    return ['-object', f'secret,id=software-vnc-password,data={VNC_PASSWORD}',
            '-vnc', display + ',password-secret=software-vnc-password']


def challenge_response(challenge, password=VNC_PASSWORD):
    # RFB VNC authentication uses DES with each password byte's bits reversed.
    key = bytes(int(f'{byte:08b}'[::-1], 2) for byte in password.encode('ascii')[:8].ljust(8, b'\0'))
    return subprocess.run(['openssl', 'enc', '-des-ecb', '-provider', 'legacy',
                           '-K', key.hex(), '-nopad'], input=challenge,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
