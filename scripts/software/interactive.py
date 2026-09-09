"""Run a persistent software-rendered guest with native QEMU VNC output."""
import argparse
import json
from pathlib import Path
import queue
import signal
import subprocess
import tempfile
import threading
import time

from qemu_profile import software_command
from vnc_auth import VNC_PASSWORD
from audio_backend import AudioBackend


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, help='Stop after this many seconds; useful for reproducible diagnostics')
    parser.add_argument('--test-page', action='store_true', help='Show the controlled browser color/text page')
    parser.add_argument('--renderer', choices=('softpipe', 'llvmpipe'), default='softpipe')
    parser.add_argument('--intro-race-fix', action='store_true', help='Apply the documented opt-in MMUI intro race patch')
    parser.add_argument('--start-delay', type=int, default=5, help='Time to connect a VNC client before starting services')
    parser.add_argument('--temperature', type=int, default=25000, help='Initial simulated temperature in millidegrees Celsius')
    parser.add_argument('--trip-temperature', type=int, default=95000, help='Lab thermal trip in millidegrees Celsius; fixed until reboot')
    parser.add_argument('--microphone-tone', type=int, default=0, help='Simulated microphone frequency, 0 for silence')
    parser.add_argument('--record-audio', action='store_true', help='Record speaker PCM alongside live diagnostics')
    args = parser.parse_args()
    if args.intro_race_fix and args.test_page:
        parser.error('--intro-race-fix requires the original GUI')
    if not all(-40000 <= value <= 150000 for value in (args.temperature, args.trip_temperature)):
        parser.error('Temperature values must be between -40000 and 150000 millidegrees Celsius')
    if args.start_delay < 0 or (args.seconds is not None and args.seconds < 10):
        parser.error('Use a nonnegative start delay and at least 10 seconds when bounded')
    if not 0 <= args.microphone_tone <= 3000:
        parser.error('Microphone frequency must be between 0 and 3000 Hz')
    home = Path(tempfile.mkdtemp(prefix='live-', dir='/software'))
    disk = home / 'output.ext4'
    with disk.open('wb') as stream:
        stream.truncate(128 * 1024**2)
    subprocess.run(['mkfs.ext4', '-q', '-F', '-L', 'MAZDA_SOFTWARE', str(disk)], check=True)
    profile = json.loads(Path('/software/guest/profile.json').read_text())
    if not profile.get('software_opera'):
        raise SystemExit('The current guest lacks the Opera overlay. Run just software-boot to build it.')
    profile['disks'].append({'path': str(disk), 'read_only': False})
    cmd = software_command(profile, live=True, audio_dir=home if not args.test_page else None)
    cmd += ['-qmp', 'unix:' + str(home / 'qmp.sock') + ',server=on,wait=off']
    Path('/software/live.json').write_text(json.dumps({'directory': str(home), 'qmp': str(home / 'qmp.sock')}))
    audio = AudioBackend(home, args.microphone_tone, args.record_audio).start() if not args.test_page else None
    try:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, bufsize=1)
    except BaseException:
        if audio:
            audio.close()
        raise
    pending = queue.Queue()
    def reader():
        for line in process.stdout:
            pending.put(line)
        pending.put(None)
    threading.Thread(target=reader, daemon=True).start()
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print('VNC: vnc://127.0.0.1:5901 — run just software-view in another terminal.', flush=True)
    print('VNC password: ' + VNC_PASSWORD, flush=True)
    print('Ctrl-C stops the guest and saves its logs. Retained disk: ' + str(disk), flush=True)
    startup = f'''mkdir -p /tmp/software /tmp/lab-wayland
mount -t ext4 $(/bin/busybox findfs LABEL=MAZDA_SOFTWARE) /tmp/software
export LAB_LOG_DIR=/tmp/software
export LAB_GALLIUM_DRIVER={args.renderer}
export LAB_INTRO_RACE_FIX={int(args.intro_race_fix)}
chmod 700 /tmp/lab-wayland
export XDG_RUNTIME_DIR=/tmp/lab-wayland
export LD_LIBRARY_PATH=/lab-software:/jci/lib:/usr/lib:/lib
export WL_COMPOSITOR_CONFIG=/lab-software/compositor.conf
export MAZDA_SOFTWARE_FRAME=/tmp/software/frame.ppm
export MAZDA_SOFTWARE_FB=/dev/fb0
/lab-software/load-input temperature={args.temperature} trip_temperature={args.trip_temperature}
sleep {args.start_delay}
/usr/bin/wayland-viv-compositor -l 7 > /tmp/software/compositor.log 2>&1 &
sleep 2
mkdir -p /tmp/common/log
echo COMMON_LOG_LEVEL=Debug > /tmp/common/log/settings.txt
export COMMON_LOG_LEVEL=Debug
. /lab-software/start-services
sleep 5
/lab-software/run-opera -u {'/lab-software/render-test.html' if args.test_page else '/jci/gui/index.html'} > /tmp/software/opera.log 2>&1 &
echo SOFTWARE_LIVE_STARTED
'''
    if args.test_page:
        startup += 'sleep 15\n/bin/busybox timeout -t 5 /usr/bin/ivi-shell -a JCI_OPERA_PRIMARY:255\n'
    else:
        startup = startup.replace('sleep ' + str(args.start_delay) + '\n', '/lab-software/load-audio\nsleep ' + str(args.start_delay) + '\n', 1)
        startup = startup.replace('. /lab-software/start-services', 'export LAB_VIP_SERVICE=1 LAB_TAU_STATE=connected LAB_AUDIO_SERVICES=1\n. /lab-software/start-services')
    started = time.monotonic()
    sent = False
    shutdown_at = None
    try:
        with Path('runs/software-live.log').open('w') as log:
            while True:
                if args.seconds is not None and time.monotonic()-started >= args.seconds:
                    stopping = True
                if stopping and shutdown_at is None:
                    process.stdin.write('sync\npoweroff -f\n')
                    process.stdin.flush()
                    shutdown_at = time.monotonic()
                if shutdown_at is not None and time.monotonic()-shutdown_at > 15:
                    process.terminate()
                    break
                try:
                    line = pending.get(timeout=0.5)
                except queue.Empty:
                    continue
                if line is None:
                    break
                log.write(line)
                log.flush()
                print(line, end='', flush=True)
                if 'MAZDA_LAB_READY' in line and not sent and not stopping:
                    process.stdin.write(startup)
                    process.stdin.flush()
                    sent = True
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if audio:
            audio.close()
        subprocess.run(['e2fsck', '-p', '-E', 'journal_only', str(disk)], check=True)
        for name in ('intro-race-fix.json', 'compositor.log', 'opera.log', 'sm.log', 'syslog.log', 'smevents.txt', 'nativegui.log', 'frame.ppm', 'vip-service.log', 'vim.log', 'audio-config.log', 'display.log'):
            subprocess.run(['debugfs', '-R', f'dump /{name} {home / name}', str(disk)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if (home / name).exists() and name.endswith('.log'):
                Path('runs/software-live-' + name).write_bytes((home / name).read_bytes())
        print('Saved live guest diagnostics: ' + str(home), flush=True)
    if process.returncode:
        raise SystemExit(process.returncode)


if __name__ == '__main__':
    main()
