"""Build the upstream PCI HDA controller missing from the pinned ARMMP package."""
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET


def service_config():
    """Add the original audio services and dependencies to the lab SM profile."""
    base = ET.parse('overlays/software/sm.conf')
    stock = ET.parse('/software/sysroot/jci/sm/sm.conf')
    names = ('audio_config', 'audio_start', 'xsesvc2dbus_service',
             'xsesvc2dbus_tau', 'audio_control', 'audio_amplifier', 'audio_manager')
    destination = base.find('services')
    for name in names:
        service = stock.find(f'.//service[@name="{name}"]')
        if service is None:
            raise RuntimeError('Missing original audio service: ' + name)
        service.set('affinity_mask', '0x01')
        service.set('reset_board', 'no')
        destination.append(service)
    return ET.tostring(base.getroot(), encoding='utf-8', xml_declaration=True)


def alsa_adapter():
    """Keep stock Bluetooth names/rates, adapting mono clients to stereo HDA."""
    result = '# Lab HDA adapter: Bluetooth mono clients use stereo hardware.\n'
    for rate, playback_key, capture_key in ((8000, 1000, 2000), (16000, 3000, 4000)):
        for kind, key in (('dmix', playback_key), ('dsnoop', capture_key)):
            result += f'''pcm.!bt_sco_{kind}_{rate} {{
  type plug
  route_policy duplicate
  slave.pcm {{
    type {kind}
    ipc_key {key}
    ipc_key_add_uid yes
    slave {{
      pcm "hw:1,0"
      rate {rate}
      format S16_LE
      channels 2
      buffer_size 512
      period_size 256
    }}
  }}
}}
'''
    return result.encode()


def build(home, version):
    target = home / 'audio-build'
    target.mkdir(parents=True, exist_ok=True)
    source = Path('/opt/guest-audio-source')
    for name in ('hda_intel.c', 'hda_intel.h', 'hda_controller.h', 'hda_intel_trace.h'):
        shutil.copyfile(source / name, target / name)
    (target / 'Makefile').write_text(
        'obj-m := snd-hda-intel.o\n'
        'snd-hda-intel-y := hda_intel.o\n'
        'CFLAGS_hda_intel.o := -I$(src)\n')
    subprocess.run(['make', '-C', '/usr/src/linux-headers-' + version,
                    'ARCH=arm', 'CROSS_COMPILE=arm-linux-gnueabi-',
                    'M=' + str(target), 'modules'], check=True)
    return target / 'snd-hda-intel.ko'


if __name__ == '__main__':
    version = json.loads(Path('config/kernel/debian-armmp.json').read_text())['version']
    print(build(Path('/software/audio-only'), version))
