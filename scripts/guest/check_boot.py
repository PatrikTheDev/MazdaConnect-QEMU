"""Bounded full-system boot check: wait for the lab shell, query it, then power off."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import threading
import time

from boot import command
import diagnostics


def check(profile, probe=False, compositor=False):
    settings = json.loads(Path(profile).read_text())
    if compositor:
        settings['append'] += ' lab.compositor=headless'
    disk = diagnostics.prepare_disk() if probe else None
    if disk:
        settings.setdefault('disks', []).append({'path': str(disk), 'read_only': False})
    process = subprocess.Popen(command(settings),
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines, pending = [], queue.Queue()
    def read():
        for line in process.stdout:
            pending.put(line)
        pending.put(None)
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    deadline = time.monotonic() + 120
    sent, verified = False, False
    try:
        while time.monotonic() < deadline:
            try:
                line = pending.get(timeout=1)
            except queue.Empty:
                continue
            if line is None:
                break
            lines.append(line)
            if 'MAZDA_LAB_READY' in line and not sent:
                # printf uses two arguments so command echo alone cannot satisfy
                # the output marker. Exercise both BusyBox and the guest kernel.
                commands = "/bin/busybox printf '%s%s\\n' MAZDA_ GUEST_EXEC_OK\n/bin/busybox uname -r\n"
                resources = json.loads(Path('artifacts/cmu150-eu-74.00.324A.resources.json').read_text())
                sample = next(e for e in resources['entries'] if e['kind'] == 'Copy')
                data = gzip.decompress((Path('/lab/firmware/cmu150-eu-74.00.324A/outer') / sample['source']).read_bytes())
                if hashlib.sha256(data).hexdigest() != sample['sha256']:
                    raise ValueError('Resource sample changed')
                # This BusyBox has md5sum, but no sha256sum applet. Its expected
                # MD5 is calculated from the SHA-256-verified source sample.
                md5 = hashlib.md5(data).hexdigest()
                commands += f"echo '{md5}  /{sample['name']}' | /bin/busybox md5sum -c - && /bin/busybox printf '%s%s\\n' MAZDA_ RESOURCE_HASH_OK\n"
                if compositor:
                    commands += "sleep 1; /lab-modules/wayland-check /tmp/lab-wayland/wayland-0\n"
                if probe:
                    commands += (
                        "mkdir -p /tmp/lab-debug; mount -t ext4 $(/bin/busybox findfs LABEL=MAZDA_DEBUG) /tmp/lab-debug\n"
                        "ulimit -c unlimited; echo /tmp/lab-debug/compositor.core > /proc/sys/kernel/core_pattern\n"
                        "mount; /bin/busybox md5sum /resources/vui/emnavi/poi_dictionary_mnc.txt\n"
                        "export LD_LIBRARY_PATH=/jci/lib:/usr/lib:/lib\n"
                        "mkdir -p /tmp/lab-wayland; chmod 700 /tmp/lab-wayland\n"
                        "export XDG_RUNTIME_DIR=/tmp/lab-wayland\n"
                        "export WL_COMPOSITOR_CONFIG=/etc/wayland/compositor_jci_display.conf\n"
                        "ls -l /dev/fb0 /dev/galcore /usr/bin/winston\n"
                        "/bin/busybox timeout -t 10 /usr/bin/wayland-viv-compositor --help; echo COMPOSITOR_HELP_RC=$?\n"
                        "/bin/busybox timeout -t 10 /lab-modules/trace-driver /usr/bin/wayland-viv-compositor -l 7; echo COMPOSITOR_START_RC=$?\n"
                        "echo /tmp/lab-debug/headless.core > /proc/sys/kernel/core_pattern\n"
                        "/lab-modules/run-compositor > /tmp/lab-headless.log 2>&1 &\n"
                        "lab_compositor_pid=$!; sleep 2; kill -0 $lab_compositor_pid; echo HEADLESS_ALIVE_RC=$?\n"
                        "/lab-modules/wayland-check /tmp/lab-wayland/wayland-0\n"
                        "ls -l /tmp/lab-wayland; cat /tmp/lab-headless.log\n"
                        "kill $lab_compositor_pid; wait $lab_compositor_pid; echo HEADLESS_STOP_RC=$?\n"
                        "/bin/busybox printf '%s%s\\n' MAZDA_ PROBE_COMPLETE\n"
                    )
                process.stdin.write(commands + "/bin/busybox sync\n/bin/busybox poweroff -f\n")
                process.stdin.flush()
                sent = True
            if line.strip() == 'MAZDA_GUEST_EXEC_OK':
                verified = True
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        Path('runs').mkdir(exist_ok=True)
        log = Path('runs/eu-v74-graphics-probe.log' if probe else
                   'runs/eu-v74-compositor-boot.log' if compositor else 'runs/eu-v74-boot.log')
        log.write_text(''.join(lines))
    if not (sent and verified and process.returncode == 0 and any('Power down' in line for line in lines)):
        raise SystemExit(f'Guest boot check failed; inspect {log}')
    if probe and not any(line.strip() == 'MAZDA_PROBE_COMPLETE' for line in lines):
        raise SystemExit(f'Probe incomplete; inspect {log}')
    if not any(line.strip() == 'MAZDA_RESOURCE_HASH_OK' for line in lines):
        raise SystemExit(f'Mounted resource verification failed; inspect {log}')
    if disk:
        diagnostics.analyze(disk, 'cmu150-eu-74.00.324A')
    if probe or compositor:
        if not any(line.strip() == 'WAYLAND_ROUNDTRIP_OK outputs=0' for line in lines):
            raise SystemExit(f'Headless compositor protocol check failed; inspect {log}')
    print('Full-system boot, original Mazda BusyBox command, and guest poweroff passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--probe', action='store_true')
    mode.add_argument('--compositor', action='store_true')
    args = parser.parse_args()
    check(args.profile, args.probe, args.compositor)
