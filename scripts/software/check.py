"""Exercise the original compositor and verify pixels produced by a real client."""
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import argparse
import struct
import zlib
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'guest'))
from boot import command
from qemu_profile import software_command

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--opera', action='store_true')
parser.add_argument('--inspect-surface', action='store_true', help='After the normal capture, explicitly show the browser surface for a separate diagnostic capture')
parser.add_argument('--test-page', action='store_true')
parser.add_argument('--no-hw-accel', action='store_true', help='Use Opera CPU painting instead of its GLES painter; both use CPU Mesa')
parser.add_argument('--probe-player', action='store_true')
parser.add_argument('--inspect-buffer', action='store_true')
parser.add_argument('--debug-services', action='store_true', help='Enable vendor debug logging in the disposable guest')
parser.add_argument('--capture-sequence', action='store_true', help='Capture compositor frames every five seconds during startup')
parser.add_argument('--verify-video', action='store_true', help='Require decoded intro frames and MMUI completion, without claiming the interactive UI is ready')
parser.add_argument('--seconds', type=int, default=45)
args = parser.parse_args()
if not 5 <= args.seconds <= 180:
    parser.error('--seconds must be between 5 and 180')
if args.verify_video and (not args.opera or args.test_page or not args.capture_sequence or not args.debug_services):
    parser.error('--verify-video requires --opera --capture-sequence --debug-services and the original GUI')
home = Path(tempfile.mkdtemp(prefix='test-', dir='/software'))
disk = home / 'output.ext4'
with disk.open('wb') as stream:
    stream.truncate(128 * 1024**2)
subprocess.run(['mkfs.ext4', '-q', '-F', '-L', 'MAZDA_SOFTWARE', str(disk)], check=True)
settings = json.loads(Path('/software/guest/profile.json').read_text())
settings['disks'].append({'path': str(disk), 'read_only': False})
cmd = software_command(settings) if args.opera else command(settings)
process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, bufsize=1)
pending = queue.Queue()
def read():
    for line in process.stdout:
        pending.put(line)
    pending.put(None)
threading.Thread(target=read, daemon=True).start()
lines, sent = [], False
commands = '''mkdir -p /tmp/software /tmp/lab-wayland
mount -t ext4 $(/bin/busybox findfs LABEL=MAZDA_SOFTWARE) /tmp/software
ulimit -c unlimited
echo /tmp/software/compositor.core > /proc/sys/kernel/core_pattern
chmod 700 /tmp/lab-wayland
export XDG_RUNTIME_DIR=/tmp/lab-wayland
export LD_LIBRARY_PATH=/lab-software:/jci/lib:/usr/lib:/lib
export WL_COMPOSITOR_CONFIG=/lab-software/compositor.conf
export MAZDA_SOFTWARE_FRAME=/tmp/software/frame.ppm
/usr/bin/wayland-viv-compositor -l 7 > /tmp/software/compositor.log 2>&1 &
lab_compositor_pid=$!
sleep 2
/lab-modules/wayland-check /tmp/lab-wayland/wayland-0
/lab-software/shm-pattern /tmp/lab-wayland/wayland-0 &
lab_client_pid=$!
sleep 2
cp /tmp/software/frame.ppm /tmp/software/pattern.ppm
wait $lab_client_pid
echo CLIENT_RC=$?
kill $lab_compositor_pid
wait $lab_compositor_pid
cat /tmp/software/compositor.log
sync
poweroff -f
'''
if args.opera:
    if args.inspect_buffer:
        commands = commands.replace('export MAZDA_SOFTWARE_FRAME=', 'export MAZDA_SOFTWARE_BUFFER=/tmp/software/buffer.ppm\nexport MAZDA_SOFTWARE_FRAME=')
    commands = commands.replace('/usr/bin/wayland-viv-compositor -l 7', '/lab-software/load-input\n/usr/bin/wayland-viv-compositor -l 7')
    start = commands.index('/lab-software/shm-pattern')
    end = commands.index('kill $lab_compositor_pid')
    commands = commands[:start] + '''export LAB_LOG_DIR=/tmp/software
. /lab-software/start-services
DBUS_SYSTEM_BUS_ADDRESS=unix:path=/tmp/dbus_hmi_socket /usr/bin/dbus-send --system --print-reply --type=method_call --dest=org.freedesktop.DBus / org.freedesktop.DBus.ListNames
sleep 5
echo /tmp/software/opera.core > /proc/sys/kernel/core_pattern
/lab-software/run-opera -u /jci/gui/index.html > /tmp/software/opera.log 2>&1 &
lab_opera_pid=$!
sleep 25
kill -0 $lab_opera_pid; echo OPERA_ALIVE_RC=$?
cp /tmp/software/frame.ppm /tmp/software/pattern.ppm
kill $lab_opera_pid
wait $lab_opera_pid
cat /tmp/software/opera.log
ps
''' + commands[end:]
    if args.inspect_surface:
        commands = commands.replace('kill $lab_opera_pid\n', '''/bin/busybox timeout -t 5 /usr/bin/ivi-shell -a JCI_OPERA_PRIMARY:255
sleep 3
cp /tmp/software/frame.ppm /tmp/software/visible.ppm
kill $lab_opera_pid
''')
    if args.test_page:
        commands = commands.replace('-u /jci/gui/index.html', '-u /lab-software/render-test.html')
    if args.no_hw_accel:
        commands = commands.replace('/lab-software/run-opera -u', '/lab-software/run-opera --noHWAccel -u')
    commands = commands.replace('sleep 25\n', 'sleep ' + str(args.seconds) + '\n')
    if args.debug_services:
        commands = commands.replace('. /lab-software/start-services', '''mkdir -p /tmp/common/log
echo COMMON_LOG_LEVEL=Debug > /tmp/common/log/settings.txt
export COMMON_LOG_LEVEL=Debug
. /lab-software/start-services''')
    if args.capture_sequence:
        samples = ''.join(f'sleep 5\ncp /tmp/software/frame.ppm /tmp/software/sequence-{i:02d}.ppm\n' for i in range(args.seconds // 5))
        samples += f'sleep {args.seconds % 5}\n'
        commands = commands.replace('sleep ' + str(args.seconds) + '\n', samples)
    if args.probe_player:
        commands = commands.replace('echo /tmp/software/opera.core', '''/bin/busybox timeout -t 5 /lab-modules/trace-driver /lab-software/splashplayer-vendor -q -t LAB_PLAYER_PROBE /jci/resources/TranLogo.ivf > /tmp/software/player.log 2>&1
echo PLAYER_RC=$?
echo /tmp/software/opera.core''')
try:
    deadline = time.monotonic() + args.seconds + 120
    while time.monotonic() < deadline:
        try:
            line = pending.get(timeout=1)
        except queue.Empty:
            continue
        if line is None:
            break
        lines.append(line)
        if 'Initramfs unpacking failed' in line:
            raise RuntimeError('Guest initramfs could not be unpacked')
        if 'MAZDA_LAB_READY' in line and not sent:
            process.stdin.write(commands)
            process.stdin.flush()
            sent = True
    if process.poll() is None:
        process.terminate()
    process.wait(timeout=10)
finally:
    if process.poll() is None:
        process.kill()
        process.wait()
    Path('runs/software-test.log').write_text(''.join(lines))
    print('Retained software test disk: ' + str(disk))
for name in ('pattern.ppm', 'visible.ppm', 'buffer.ppm', 'compositor.log', 'compositor.core', 'opera.log', 'opera.core', 'syslog.log', 'syslog.log.0', 'nativegui.log', 'sm.log', 'smevents.txt', 'player.log'):
    subprocess.run(['debugfs', '-R', f'dump /{name} {home / name}', str(disk)],
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
if args.capture_sequence:
    for i in range(args.seconds // 5):
        name = f'sequence-{i:02d}.ppm'
        subprocess.run(['debugfs', '-R', f'dump /{name} {home / name}', str(disk)],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
if (home / 'compositor.log').exists():
    Path('runs/software-compositor.log').write_bytes((home / 'compositor.log').read_bytes())
if args.opera and (home / 'opera.log').exists():
    Path('runs/software-opera.log').write_bytes((home / 'opera.log').read_bytes())
    print('Opera log saved to runs/software-opera.log')
if (home / 'visible.ppm').exists():
    Path('artifacts/software-visible.ppm').write_bytes((home / 'visible.ppm').read_bytes())
if (home / 'buffer.ppm').exists():
    Path('artifacts/software-buffer.ppm').write_bytes((home / 'buffer.ppm').read_bytes())
if (home / 'player.log').exists():
    print((home / 'player.log').read_text())
image = home / 'pattern.ppm'
if not image.exists():
    raise SystemExit('No software frame; inspect runs/software-test.log')
data = image.read_bytes()
Path('artifacts/software-opera.ppm' if args.opera else 'artifacts/software-pattern.ppm').write_bytes(data)
header = b'P6\n800 480\n255\n'
def png(ppm, path):
    if not ppm.startswith(header) or len(ppm) != len(header) + 800*480*3:
        raise ValueError('Incomplete framebuffer capture')
    rgb = ppm[len(header):]
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload))
    rows = b''.join(b'\0' + rgb[y*2400:(y+1)*2400] for y in range(480))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 800, 480, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))
png(data, Path('artifacts/software-opera.png' if args.opera else 'artifacts/software-pattern.png'))
if args.capture_sequence:
    for source in home.glob('sequence-*.ppm'):
        png(source.read_bytes(), Path('artifacts/software-' + source.stem + '.png'))
for kind in ('visible', 'buffer'):
    source = home / (kind + '.ppm')
    if source.exists():
        png(source.read_bytes(), Path('artifacts/software-' + kind + '.png'))
if args.opera and args.test_page and args.inspect_surface:
    pixels = (home / 'visible.ppm').read_bytes()[len(header):]
    def pixel(x, y):
        return tuple(pixels[(y*800+x)*3:(y*800+x)*3+3])
    if pixel(10, 10) != (22, 50, 79) or pixel(100, 150) != (255, 48, 48) or pixel(400, 150) != (48, 255, 48) or pixel(700, 150) != (48, 48, 255):
        raise SystemExit('Browser test-page colors differ from expected pixels')
    white = sum(pixels[i:i+3] == b'\xff\xff\xff' for i in range(0, 800*100*3, 3))
    if white < 500 or not any(line.strip() == 'OPERA_ALIVE_RC=0' for line in lines):
        raise SystemExit('Browser text or liveness check failed')
    if process.returncode or not any('Power down' in line for line in lines):
        raise SystemExit('Guest did not shut down cleanly')
    print('Original Opera rendered HTML text and exact CSS color samples through CPU Mesa and the original compositor.')
    raise SystemExit(0)
if args.opera:
    if args.verify_video:
        service_log = (home / 'sm.log').read_text(errors='replace')
        native_log = (home / 'syslog.log').read_text(errors='replace')
        done = re.search(r'SOFTWARE_VIDEO_DONE decoded=120 presented=(\d+)', service_log)
        if not done or int(done[1]) < 2 or 'SOFTWARE_VIDEO_READY TRANLOGO_SURFACE' not in service_log:
            raise SystemExit('Intro did not decode and present the complete original movie')
        if 'UIA_SYSTEM_OnFinishIntroAnimation' not in native_log or 'TranLogo Started' not in native_log:
            raise SystemExit('MMUI did not acknowledge the video service lifecycle')
        visible = {source.read_bytes() for source in home.glob('sequence-*.ppm') if any(source.read_bytes()[len(header):])}
        if len(visible) < 2:
            raise SystemExit('Fewer than two distinct visible compositor frames during playback')
        if process.returncode or not any('Power down' in line for line in lines):
            raise SystemExit('Guest did not shut down cleanly')
        print(f'Original intro: 120 frames decoded, {done[1]} presented; visible animation and MMUI completion verified. Interactive UI readiness is not asserted.')
        raise SystemExit(0)
    raise SystemExit('Opera diagnostic captured; inspect pixels and logs before declaring UI success.')
row = b'\xff\0\0' * 200 + b'\0\xff\0' * 200 + b'\0\0\xff' * 200 + b'\xff\xff\xff' * 200
if data != header + row * 480:
    raise SystemExit('Software pixels differ from expected color bars')
if not any(line.strip() == 'SOFTWARE_CLIENT_FRAME_OK' for line in lines):
    raise SystemExit('Missing Wayland frame callback')
if process.returncode or not any('Power down' in line for line in lines):
    raise SystemExit('Guest did not shut down cleanly')
print('Original compositor: wl_shm color bars, frame callback and exact pixels verified.')
