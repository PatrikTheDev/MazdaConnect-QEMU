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
from audio_backend import AudioBackend

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--opera', action='store_true')
parser.add_argument('--websockets-queue-fix', action='store_true', help='Apply the documented opt-in original GUI queue correction')
parser.add_argument('--time-deadline-fix', action='store_true', help='Enable original time services with the documented deadline clock patch')
parser.add_argument('--intro-race-fix', action='store_true', help='Opt in to the documented MMUI intro completion race patch')
parser.add_argument('--time-services', action='store_true', help='Probe the original CPP and BLM time services')
parser.add_argument('--renderer', choices=('softpipe', 'llvmpipe'), default='softpipe')
parser.add_argument('--browser-delay', type=int, default=5, help='Seconds between service launch and Opera launch for startup-order diagnostics')
parser.add_argument('--live-output', action='store_true', help='Exercise the real VNC framebuffer in the bounded diagnostic')
parser.add_argument('--verify-mic-gain', action='store_true', help='Verify real HDA capture attenuation through the Mazda MIC Level control')
parser.add_argument('--profile-frames', action='store_true', help='Time compositor stages without attaching to Opera')
parser.add_argument('--trace-render', action='store_true', help='Trace Opera waits and software compositor frame stages')
parser.add_argument('--sample-render', action='store_true', help='Sample Opera main-thread registers during startup')
parser.add_argument('--sample-workers', action='store_true', help='With --sample-render, also briefly stop llvmpipe workers to record their PCs and current mappings')
parser.add_argument('--probe-rounding', action='store_true', help='Run the independent ARMEL rounding-contract check after normal runtime setup and before launching Opera')
parser.add_argument('--verify-kernel-layout', action='store_true', help='Retain all process mappings before browser shutdown for the opt-in 2 GiB profile')
parser.add_argument('--inspect-surface', action='store_true', help='After the normal capture, explicitly show the browser surface for a separate diagnostic capture')
parser.add_argument('--test-page', action='store_true')
parser.add_argument('--trace-transitions', action='store_true', help='Log original UI animation callbacks and pending targets without changing timing rules')
parser.add_argument('--probe-animations', action='store_true', help='Probe CSS animation support in original Opera without modifying firmware')
parser.add_argument('--animation-lifecycle', action='store_true', help='Use the isolated template attachment diagnostic with --probe-animations')
parser.add_argument('--probe-websockets', action='store_true', help='Run an isolated diagnostic against the stock websocket JavaScript in original Opera')
parser.add_argument('--no-hw-accel', action='store_true', help='Use Opera CPU painting instead of its GLES painter; both use CPU Mesa')
parser.add_argument('--tau-state', choices=('standby', 'connected', 'disconnected'), default='connected')
parser.add_argument('--verify-tau', action='store_true')
parser.add_argument('--verify-vbs', action='store_true')
parser.add_argument('--probe-vip-service', action='store_true')
parser.add_argument('--probe-vim', action='store_true', help='Trace the original vehicle-interface daemon')
parser.add_argument('--probe-audio', action='store_true', help='Trace original aopen startup in the disposable guest')
parser.add_argument('--audio-devices', action='store_true', help='Attach two HDA cards and original ALSA loopbacks for audio diagnostics')
parser.add_argument('--microphone-tone', type=int, default=0, help='Simulated microphone frequency in Hz; zero supplies silence')
parser.add_argument('--audio-services', action='store_true', help='Start original audio services with the lab HDA adapter')
parser.add_argument('--verify-audio', action='store_true', help='Verify actual speaker and captured microphone samples')
parser.add_argument('--probe-player', action='store_true')
parser.add_argument('--inspect-buffer', action='store_true')
parser.add_argument('--debug-services', action='store_true', help='Enable vendor debug logging in the disposable guest')
parser.add_argument('--capture-sequence', action='store_true', help='Capture compositor frames every five seconds during startup')
parser.add_argument('--verify-video', action='store_true', help='Require decoded intro frames and MMUI completion, without claiming the interactive UI is ready')
parser.add_argument('--verify-display', action='store_true')
parser.add_argument('--verify-thermal', action='store_true')
parser.add_argument('--verify-vip', action='store_true')
parser.add_argument('--verify-gpio', action='store_true', help='Check GPIO edge notifications and original system-service startup')
parser.add_argument('--probe-lvds', action='store_true', help='Trace the stock display service with a real VirtIO framebuffer')
parser.add_argument('--seconds', type=int, default=45)
args = parser.parse_args()
if args.sample_workers and not args.sample_render:
    parser.error('--sample-workers requires --sample-render')
if args.probe_rounding and not args.opera:
    parser.error('--probe-rounding requires --opera for the modern runtime')
if args.verify_kernel_layout and not args.opera:
    parser.error('--verify-kernel-layout requires --opera')
if args.animation_lifecycle and not args.probe_animations:
    parser.error('--animation-lifecycle requires --probe-animations')
if args.verify_mic_gain and not (args.verify_audio and args.probe_audio and args.audio_devices):
    parser.error('--verify-mic-gain requires --verify-audio --probe-audio --audio-devices')
if args.trace_transitions and (not args.opera or args.test_page or args.probe_websockets or args.probe_animations):
    parser.error('--trace-transitions requires the original GUI')
if args.probe_animations and (not args.opera or args.test_page or args.probe_websockets):
    parser.error('--probe-animations requires Opera and cannot combine with another test page')
if args.websockets_queue_fix and (not args.opera or args.test_page):
    parser.error('--websockets-queue-fix requires Opera and the original websocket code')
if (args.time_deadline_fix or args.time_services) and (not args.opera or args.test_page or args.probe_websockets or args.probe_animations):
    parser.error('Time services require the original GUI')
if args.intro_race_fix and (not args.opera or args.test_page or args.probe_websockets or args.probe_animations):
    parser.error('--intro-race-fix requires the original GUI')
if args.probe_websockets and (not args.opera or args.test_page):
    parser.error('--probe-websockets requires --opera and cannot use --test-page')
if not 0 <= args.browser_delay <= 30:
    parser.error('--browser-delay must be between 0 and 30')
if not 5 <= args.seconds <= 180:
    parser.error('--seconds must be between 5 and 180')
if (args.live_output or args.trace_render or args.sample_render or args.profile_frames) and not args.opera:
    parser.error('Live output and render tracing require --opera')
if args.trace_render and args.sample_render:
    parser.error('Syscall tracing and register sampling cannot attach to the same process')
if (args.verify_vbs or args.verify_tau) and not (args.probe_vip_service and args.debug_services):
    parser.error('--verify-vbs requires --probe-vip-service --debug-services')
if args.verify_video and (not args.opera or args.test_page or args.probe_websockets or not args.capture_sequence or not args.debug_services):
    parser.error('--verify-video requires --opera --capture-sequence --debug-services and the original GUI')
if args.verify_display and not (args.opera and args.test_page and args.inspect_surface):
    parser.error('--verify-display requires --opera --test-page --inspect-surface')
if (args.probe_audio or args.probe_vim or args.probe_vip_service) and not args.opera:
    parser.error('--probe-audio and --probe-vim require --opera')
if args.verify_thermal and not (args.opera and args.debug_services and args.verify_gpio):
    parser.error('--verify-thermal requires --opera --debug-services --verify-gpio')
if args.verify_vip and not args.opera:
    parser.error('--verify-vip requires --opera')
if args.audio_devices and not (args.opera and (args.probe_audio or args.audio_services)):
    parser.error('--audio-devices requires --opera and an audio probe or service run')
if args.audio_services and not (args.audio_devices and args.probe_vip_service):
    parser.error('--audio-services requires audio devices and the VIP peer')
if args.verify_audio and not (args.audio_devices and args.probe_audio and args.microphone_tone):
    parser.error('--verify-audio requires an audio-device probe and a nonzero microphone tone')
if not 0 <= args.microphone_tone <= 3000 or (args.microphone_tone and not args.audio_devices):
    parser.error('--microphone-tone requires audio devices and must be between 0 and 3000 Hz')
if args.verify_gpio and not args.opera:
    parser.error('--verify-gpio requires --opera')
home = Path(tempfile.mkdtemp(prefix='test-', dir='/software'))
disk = home / 'output.ext4'
with disk.open('wb') as stream:
    stream.truncate(128 * 1024**2)
subprocess.run(['mkfs.ext4', '-q', '-F', '-L', 'MAZDA_SOFTWARE', str(disk)], check=True)
settings = json.loads(Path('/software/guest/profile.json').read_text())
if args.verify_kernel_layout:
    if settings.get('kernel_profile') != 'vmsplit2g':
        parser.error('--verify-kernel-layout requires --kernel-profile vmsplit2g')
    (home / 'kernel-build.json').write_bytes(Path('/software/kernels/vmsplit2g/manifest.json').read_bytes())
settings['disks'].append({'path': str(disk), 'read_only': False})
cmd = software_command(settings, live=args.probe_lvds or args.verify_display or args.live_output,
                       audio_dir=home if args.audio_devices else None) if args.opera else command(settings)
audio = AudioBackend(home, args.microphone_tone).start() if args.audio_devices else None
try:
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1)
except BaseException:
    if audio:
        audio.close()
    raise
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
    commands = commands.replace('export XDG_RUNTIME_DIR=', f'export LAB_GALLIUM_DRIVER={args.renderer}\nexport XDG_RUNTIME_DIR=')
    if args.probe_lvds or args.verify_display or args.live_output:
        commands = commands.replace('export MAZDA_SOFTWARE_FRAME=', 'export MAZDA_SOFTWARE_FB=/dev/fb0\nexport MAZDA_SOFTWARE_FRAME=')
    if args.trace_render or args.sample_render or args.profile_frames:
        commands = commands.replace('export MAZDA_SOFTWARE_FRAME=', 'export MAZDA_RENDER_TRACE=1\nexport MAZDA_SOFTWARE_FRAME=')
    if args.inspect_buffer:
        commands = commands.replace('export MAZDA_SOFTWARE_FRAME=', 'export MAZDA_SOFTWARE_BUFFER=/tmp/software/buffer.ppm\nexport MAZDA_SOFTWARE_FRAME=')
    commands = commands.replace('/usr/bin/wayland-viv-compositor -l 7', '/lab-software/load-input\n/usr/bin/wayland-viv-compositor -l 7')
    if args.audio_devices:
        commands = commands.replace('/lab-software/load-input\n', '/lab-software/load-input\n/lab-software/load-audio\n')
    if args.verify_vip:
        commands = commands.replace('/lab-software/load-input\n', '/lab-software/load-input\n/lab-software/vip-check\n/bin/busybox rmmod mazda_vip && /bin/busybox insmod /lab-software/mazda_vip.ko && /lab-software/vip-check && echo VIP_LIFECYCLE_OK\n')
    if args.verify_gpio:
        commands = commands.replace('/lab-software/load-input\n', '/lab-software/load-input\n/lab-software/gpio-check\n/bin/busybox rmmod mazda_gpio && /bin/busybox insmod /lab-software/mazda_gpio.ko && /lab-software/gpio-check && echo GPIO_LIFECYCLE_OK\n')
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
    if args.verify_display:
        commands = commands.replace('cp /tmp/software/frame.ppm /tmp/software/visible.ppm', '/lab-software/runtime/ld-linux.so.3 --library-path /lab-software/runtime /lab-software/display-check\ncp /tmp/software/frame.ppm /tmp/software/visible.ppm')
    if args.test_page:
        commands = commands.replace('-u /jci/gui/index.html', '-u /lab-software/render-test.html')
    if args.probe_animations:
        page = 'animation-lifecycle.html' if args.animation_lifecycle else 'animations-probe.html'
        commands = commands.replace('-u /jci/gui/index.html', '-u /lab-software/' + page)
    if args.probe_websockets:
        commands = commands.replace('-u /jci/gui/index.html', '-u /lab-software/websockets-probe.html')
    if args.no_hw_accel:
        commands = commands.replace('/lab-software/run-opera -u', '/lab-software/run-opera --noHWAccel -u')
    if args.trace_render:
        commands = commands.replace('/lab-software/run-opera ', '/usr/bin/strace -f -tt -T -e trace=poll,select,epoll_wait,futex,recvmsg,sendmsg -o /tmp/software/opera-strace.log /lab-software/run-opera ')
    if args.sample_render:
        worker_option = ' --workers' if args.sample_workers else ''
        commands = commands.replace('lab_opera_pid=$!\n', 'lab_opera_pid=$!\n/lab-software/sample-process "$lab_opera_pid"' + worker_option + ' > /tmp/software/opera-samples.log 2>&1 &\n')
    if args.probe_rounding:
        commands = commands.replace('. /lab-software/start-services\n',
            '. /lab-software/start-services\n'
            '/lab-software/runtime/ld-linux.so.3 --library-path /lab-software/runtime /lab-software/rounding-check > /tmp/software/rounding.log 2>&1\n'
            'echo ROUNDING_RC=$? >> /tmp/software/rounding.log\n')
    if args.verify_kernel_layout:
        commands = commands.replace('kill -0 $lab_opera_pid; echo OPERA_ALIVE_RC=$?\n',
            'kill -0 $lab_opera_pid; echo OPERA_ALIVE_RC=$?\n'
            '{ echo KERNEL_RELEASE=$(/bin/busybox uname -r); '
            'for lab_maps in /proc/[0-9]*/maps; do '
            'if test -s "$lab_maps" || test -r "$lab_maps"; then '
            'lab_content=$(/bin/busybox cat "$lab_maps" 2>&1); '
            'if test -n "$lab_content"; then echo MAPS:$lab_maps; echo "$lab_content"; fi; '
            'fi; done; } > /tmp/software/kernel-layout.log\n')
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
    if args.verify_thermal:
        commands = commands.replace('kill -0 $lab_opera_pid;', '/bin/busybox logger THERMAL_HOT_INJECT\necho 105000 > /sys/module/mazda_gpio/parameters/temperature\nsleep 8\ncat /sys/devices/virtual/thermal/thermal_zone0/temp\necho 25000 > /sys/module/mazda_gpio/parameters/temperature\nsleep 6\nkill -0 $lab_opera_pid;')
    if args.probe_vip_service:
        commands = commands.replace('. /lab-software/start-services', f'export LAB_VIP_SERVICE=1 LAB_TAU_STATE={args.tau_state}\n. /lab-software/start-services')
    if args.audio_services:
        commands = commands.replace('. /lab-software/start-services', 'export LAB_AUDIO_SERVICES=1\n. /lab-software/start-services')
    if args.intro_race_fix:
        commands = commands.replace('. /lab-software/start-services', 'export LAB_INTRO_RACE_FIX=1\n. /lab-software/start-services')
    if args.trace_transitions:
        commands = commands.replace('. /lab-software/start-services', 'export LAB_TRACE_TRANSITIONS=1\n. /lab-software/start-services')
    if args.websockets_queue_fix:
        commands = commands.replace('. /lab-software/start-services', 'export LAB_WEBSOCKETS_QUEUE_FIX=1\n. /lab-software/start-services')
    if args.time_deadline_fix:
        commands = commands.replace('. /lab-software/start-services', 'export LAB_TIME_DEADLINE_FIX=1\n. /lab-software/start-services')
    if args.time_services:
        commands = commands.replace('. /lab-software/start-services', 'export LAB_TIME_SERVICES=1\n. /lab-software/start-services')
    if args.probe_vim:
        commands = commands.replace('echo /tmp/software/opera.core', '/lab-software/vip-trace > /tmp/software/vip-trace.log 2>&1 &\n/bin/busybox timeout -t 8 /lab-modules/trace-driver /jci/vim/vim_app > /tmp/software/vim.log 2>&1\necho VIM_PROBE_RC=$?\necho /tmp/software/opera.core')
    if args.verify_mic_gain:
        commands = commands.replace('. /lab-software/start-services', 'export LAB_VERIFY_MIC_GAIN=1\n. /lab-software/start-services')
    if args.probe_audio:
        commands = commands.replace('echo /tmp/software/opera.core', '/bin/sh /jci/am/audioconfigupdate.sh > /tmp/software/audio.log 2>&1\n/bin/busybox timeout -t 8 /lab-modules/trace-driver /usr/bin/aopen -a >> /tmp/software/audio.log 2>&1\necho AUDIO_PROBE_RC=$?\necho /tmp/software/opera.core')
        if args.audio_devices:
            commands = commands.replace('/bin/sh /jci/am/audioconfigupdate.sh >', '/lab-software/configure-audio >')
            commands = commands.replace('echo AUDIO_PROBE_RC=$?\n', 'echo AUDIO_PROBE_RC=$?\n/lab-software/audio-check </dev/null > /tmp/software/audio-check.log 2>&1\ncat /tmp/software/audio-check.log\n')
    if args.probe_player:
        commands = commands.replace('echo /tmp/software/opera.core', '''/bin/busybox timeout -t 5 /lab-modules/trace-driver /lab-software/splashplayer-vendor -q -t LAB_PLAYER_PROBE /jci/resources/TranLogo.ivf > /tmp/software/player.log 2>&1
echo PLAYER_RC=$?
echo /tmp/software/opera.core''')
    if args.probe_lvds:
        commands = commands.replace('. /lab-software/start-services', 'export LAB_VENDOR_LVDS_PROBE=1\n. /lab-software/start-services')
        commands = commands.replace('sleep 5\necho /tmp/software/opera.core', '/bin/busybox timeout -t 5 /lab-modules/trace-driver /jci/lvds/lvds_service > /tmp/software/lvds.log 2>&1\necho LVDS_RC=$?\nsleep 5\necho /tmp/software/opera.core')
    commands = commands.replace('sleep 5\n', f'sleep {args.browser_delay}\n', 1)
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
    if audio:
        audio.close()
# The guest uses forced poweroff; sync can leave committed metadata in the
# ext4 journal. debugfs does not replay it and can otherwise dump empty inodes.
# QEMU has exited, so replay only this disposable output disk's journal before
# inspecting it. Do not attempt general filesystem repairs on a failed run.
subprocess.run(['e2fsck', '-p', '-E', 'journal_only', str(disk)], check=True)
for name in ('transition-trace.json', 'websockets-queue-fix.json', 'time-deadline-fix.json', 'intro-race-fix.json', 'pattern.ppm', 'visible.ppm', 'buffer.ppm', 'compositor.log', 'compositor.core', 'opera.log', 'opera-strace.log', 'opera-samples.log', 'opera.core', 'syslog.log', 'syslog.log.0', 'nativegui.log', 'sm.log', 'smevents.txt', 'player.log', 'lvds.log', 'display.log', 'audio.log', 'audio-check.log', 'mic.wav', 'mic-half.wav', 'bluetooth.wav', 'vim.log', 'vip-trace.log', 'vip-service.log'):
    subprocess.run(['debugfs', '-R', f'dump /{name} {home / name}', str(disk)],
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
if args.capture_sequence:
    for i in range(args.seconds // 5):
        name = f'sequence-{i:02d}.ppm'
        subprocess.run(['debugfs', '-R', f'dump /{name} {home / name}', str(disk)],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
if args.probe_rounding:
    subprocess.run(['debugfs','-R',f'dump /rounding.log {home / "rounding.log"}',str(disk)],
                   stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True)
if args.verify_kernel_layout:
    subprocess.run(['debugfs','-R',f'dump /kernel-layout.log {home / "kernel-layout.log"}',str(disk)],
                   stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True)
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
if args.verify_display and not any(line.startswith('DISPLAY_BEHAVIOR_OK:') for line in lines):
    raise SystemExit('Display behavior verification failed; inspect retained display.log and serial output')
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
    if args.verify_audio:
        from check_audio_samples import verify
        diagnostic = (home / 'audio-check.log').read_text()
        for operation in ('HARDWARE_MIXER', 'MIXER', 'PLAYBACK', 'CAPTURE', 'BLUETOOTH'):
            if f'AUDIO_{operation}_RC=0' not in diagnostic.splitlines():
                raise SystemExit('Original audio operation failed: ' + operation)
        if 'overrun!!!' in diagnostic or 'underrun!!!' in diagnostic:
            raise SystemExit('Audio sample transfer reported an overrun or underrun')
        verify(home / 'audio0.wav', (1000, 2000))
        verify(home / 'mic.wav', (args.microphone_tone, args.microphone_tone))
        verify(home / 'bluetooth.wav', (args.microphone_tone,))
        if args.verify_mic_gain:
            from check_mic_gain import verify_gain
            verify_gain(home, diagnostic)
        if process.returncode or not any('Power down' in line for line in lines):
            raise SystemExit('Guest did not shut down cleanly')
        print('Original ALSA playback, microphone and Bluetooth PCM transfers verified; audio-service startup remains separate.')
        raise SystemExit(0)
    if args.verify_vbs or args.verify_tau:
        events = (home / 'smevents.txt').read_text()
        native = (home / 'syslog.log').read_text(errors='replace')
        peer = (home / 'vip-service.log').read_text(errors='replace')
        if ('VIP_HELLO_ACKED' not in peer or 'VIP communication established.' not in native
                or ',jciVBS,SM_SVC_CMD_STARTED,' not in events
                or ',system_mazda_my14,SM_SVC_CMD_STARTED,' not in events):
            raise SystemExit('Original VIM/VBS startup verification failed')
        if ('ClientHdl=0000000000000000' in native or 'CheckSum Result is NG' in native
                or 'ACK reception other than expected' in native):
            raise SystemExit('VIM/VBS transport errors remain; inspect retained logs')
        if process.returncode or not any('Power down' in line for line in lines):
            raise SystemExit('Guest did not shut down cleanly')
        if args.verify_tau:
            state = {'standby': 0, 'connected': 1, 'disconnected': 2}[args.tau_state]
            diagnostic = f'TAU Connect Standby Status [0 : Standby] [1 : Connected] [2 : Disconnected] = [{state}]'
            if diagnostic not in native or f'VIP_TAU_STATUS state={state}' not in peer:
                raise SystemExit('Original VBS did not decode the configured TAU state')
            if state == 1 and ('Tau is connected!' not in native or 'TAU request timer stopped' not in native):
                raise SystemExit('Original system did not accept TAU connection')
            if state != 1 and 'Tau is connected!' in native:
                raise SystemExit('Non-connected simulated TAU incorrectly reported connected')
            print(f'Original VBS/system interpreted simulated TAU state: {args.tau_state}.')
        print('Original VIM handshake and VBS/system startup verified; TAU/audio and full UI remain separate requirements.')
        raise SystemExit(0)
    if args.verify_vip:
        if (sum(line.startswith('VIP_TRANSPORT_OK:') for line in lines) != 2
                or not any(line.strip() == 'VIP_LIFECYCLE_OK' for line in lines)):
            raise SystemExit('VIP transport/lifecycle verification failed')
        if process.returncode or not any('Power down' in line for line in lines):
            raise SystemExit('Guest did not shut down cleanly')
        print('SPI transport and VIP IRQ behavior verified; original VIP protocol still required.')
        raise SystemExit(0)
    if args.verify_gpio:
        events = (home / 'smevents.txt').read_text()
        if (sum(line.startswith('GPIO_BEHAVIOR_OK:') for line in lines) != 2
                or sum(line.startswith('VIM_GPIO_BEHAVIOR_OK:') for line in lines) != 2
                or not any(line.strip() == 'GPIO_LIFECYCLE_OK' for line in lines)):
            raise SystemExit('GPIO behavioral verification failed')
        native_log = (home / 'syslog.log').read_text(errors='replace')
        if args.verify_thermal:
            before, marker, after = native_log.partition('THERMAL_HOT_INJECT')
            if not marker or 'SYSTEM_SMM_OVER_TEMPERATURE_EVENT' in before or 'SYSTEM_SMM_OVER_TEMPERATURE_EVENT' not in after:
                raise SystemExit('Firmware thermal transition did not match the injected temperature')
            if 'Cannot open file /sys/devices/virtual/thermal' in native_log or sum(line.startswith('THERMAL_BEHAVIOR_OK:') for line in lines) != 2:
                raise SystemExit('Thermal sysfs/lifecycle checks failed')
            print('Normal temperature prevented false overheating; injected hot sensor triggered original firmware protection.')
        if args.debug_services and not args.verify_thermal and ('Reverse Gear Status = 0' not in native_log or 'event SYSTEM_SMM_REVERSE_GEAR_ON_EVENT' in native_log):
            raise SystemExit('Firmware did not interpret the default reverse signal as disengaged')
        if ',system_mazda_my14,SM_SVC_CMD_STARTED,' not in events:
            raise SystemExit('GPIO behavior passed, but the original system service did not start; inspect retained logs')
        if process.returncode or not any('Power down' in line for line in lines):
            raise SystemExit('Guest did not shut down cleanly')
        print('GPIO edge/value behavior and original system-service startup verified; UI readiness is not asserted.')
        raise SystemExit(0)
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
