"""Build an isolated software output overlay without modifying reference artifacts."""
import gzip
import io
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import argparse
import hashlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'guest'))
from build import write_entry

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--opera', action='store_true')
args = parser.parse_args()
home = Path('/software/guest')
home.mkdir(exist_ok=True)
plugin = home / 'libwlxs-software.so'
subprocess.run(['arm-linux-gnueabi-gcc', '-shared', '-fPIC', '-nostdlib', '-O2', '-g',
                '-Wall', '-Wextra', '-Werror', 'src/software/winston-software.c',
                '-o', str(plugin), '-lgcc'], check=True)
client = home / 'shm-pattern'
subprocess.run(['arm-linux-gnueabi-gcc', '-static', '-O2', '-Wall', '-Wextra', '-Werror',
                'src/software/shm-pattern.c', '-o', str(client)], check=True)
settings = json.loads(Path('config/qemu/eu-v74-lab.json').read_text())
report = json.loads(Path('artifacts/cmu150-eu-74.00.324A.guest.json').read_text())
if report['rootfs_sha256'] != '0f437c420e4d95220245898e99f68c6a97eaf63502d91f1a75a851b8a19f0bb4':
    raise ValueError('Software plugin ABI has not been verified for this rootfs')
with Path(settings['initrd']).open('rb') as stream:
    if hashlib.file_digest(stream, 'sha256').hexdigest() != report['initramfs_sha256']:
        raise ValueError('Reference initramfs differs from its build report')
target = home / 'initramfs.cpio.gz'
shutil.copyfile(settings['initrd'], target)
files = [('lab-software/libwlxs-software.so', plugin.read_bytes(), 0o755),
         ('lab-software/shm-pattern', client.read_bytes(), 0o755),
         ('lab-software/compositor.conf', b'plugin = ivi, software\n', 0o644)]
directories = ['lab-software']
if args.opera:
    player = home / 'splashplayer-software'
    subprocess.run(['arm-linux-gnueabi-gcc', '-static', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-I/opt/mesa-armel/usr/include', 'src/software/splashplayer.c',
                    '/opt/mesa-armel/usr/lib/arm-linux-gnueabi/libvpx.a', '-lm', '-pthread',
                    '-o', str(player)], check=True)
    files.append(('usr/bin/splashplayer', player.read_bytes(), 0o755))
    files.append(('lab-software/splashplayer-vendor', Path('/software/sysroot/usr/bin/splashplayer').read_bytes(), 0o755))
    modules = {}
    kernel = json.loads(Path('config/kernel/debian-armmp.json').read_text())
    kernel_root = Path('/lab/kernels') / kernel['version'] / 'package'
    available = {p.name.split('.ko')[0].replace('-', '_'): p for p in kernel_root.rglob('*.ko')}
    def add_module(name):
        name = name.replace('-', '_')
        if name in modules:
            return
        source = available[name]
        dependencies = subprocess.check_output(['modinfo', '-F', 'depends', str(source)], text=True).strip()
        for dep in filter(None, dependencies.split(',')):
            add_module(dep)
        modules[name] = source
    for name in ('virtio_input', 'evdev', 'virtio_gpu'):
        add_module(name)
    for source in modules.values():
        files.append(('lab-software/' + source.name, source.read_bytes(), 0o644))
    script = '#!/bin/sh\nset -eu\n' + ''.join('/bin/busybox insmod /lab-software/' + p.name + '\n' for p in modules.values())
    files.append(('lab-software/load-input', script.encode(), 0o755))
    files = [(name, b'plugin = ivi, software, xkb\ninput = /dev/input/event1, /dev/input/event2\nxkbmap = /usr/share/wayland/evdev-pc105-us.xkm\n' if name.endswith('/compositor.conf') else data, mode) for name, data, mode in files]
    files.append(('lab-software/sm.conf', Path('overlays/software/sm.conf').read_bytes(), 0o644))
    directories += ['lab-software/runtime']
    runtime = Path('/software/runtime-tree')
    runtime.mkdir(exist_ok=True)
    for folder in ('lib/arm-linux-gnueabi', 'usr/lib/arm-linux-gnueabi'):
        for source in sorted((Path('/opt/mesa-armel') / folder).glob('*.so*')):
            dest = runtime / source.name
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            if source.is_symlink():
                dest.symlink_to(source.resolve().name)
            else:
                shutil.copyfile(source, dest)
                dest.chmod(0o755)
    dri = Path('/opt/mesa-armel/usr/lib/arm-linux-gnueabi/dri/swrast_dri.so')
    (runtime / 'dri').mkdir(exist_ok=True)
    shutil.copyfile(dri, runtime / 'dri/swrast_dri.so')
    alias = runtime / 'libwayland-egl.so.0'
    if not alias.is_symlink():
        alias.symlink_to('libwayland-egl.so.1')
    disk = home / 'mesa.ext4'
    with disk.open('wb') as stream:
        stream.truncate(512 * 1024**2)
    subprocess.run(['mkfs.ext4', '-q', '-F', '-L', 'MAZDA_MESA', '-d', str(runtime), str(disk)], check=True)
    settings['disks'].append({'path': str(disk), 'read_only': True})
    files.append(('lab-software/mesa.json', b'{"file_format_version":"1.0.0","ICD":{"library_path":"/lab-software/runtime/libEGL_mesa.so.0"}}', 0o644))
    files.append(('lab-software/run-opera', Path('overlays/software/run-opera').read_bytes(), 0o755))
    files.append(('lab-software/start-services', Path('overlays/software/start-services').read_bytes(), 0o755))
    files.append(('lab-software/render-test.html', Path('overlays/software/render-test.html').read_bytes(), 0o644))
with target.open('ab') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as out:
    for inode, name in enumerate(directories, 1):
        write_entry(out, name, stat.S_IFDIR | 0o755, 0, 0, 0, 0, io.BytesIO(), inode)
    for inode, (name, data, mode) in enumerate(files, len(directories)+1):
        write_entry(out, name, stat.S_IFREG | mode, 0, 0, 0, len(data), io.BytesIO(data), inode)
    write_entry(out, 'TRAILER!!!', 0, 0, 0, 0, 0, io.BytesIO(), 0)
settings['initrd'] = str(target)
settings['software_opera'] = args.opera
(home / 'profile.json').write_text(json.dumps(settings, indent=2) + '\n')
print(target)
