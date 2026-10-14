import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path('scripts/software').resolve()))
from qemu_profile import software_command
from runtime import instance_name, snapshot, state_path


class SoftwareRuntimeTests(unittest.TestCase):
    def test_network_is_opt_in_and_forwards_all_remote_gui_endpoints(self):
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary) / 'image'
            image.touch()
            profile = {'kernel': str(image), 'initrd': str(image), 'machine': 'virt',
                       'cpu': 'cortex-a15', 'memory_mb': 1536, 'append': ''}
            self.assertNotIn('-netdev', software_command(profile))
            result = software_command(profile, developer_mode=True)
            backend = result[result.index('-netdev') + 1]
            self.assertIn('restrict=on', backend)
            self.assertIn('ipv6=off', backend)
            for host, guest in ((8080, 80), (2700, 2700), (2766, 2766), (2800, 2800)):
                self.assertIn(f'hostfwd=tcp:0.0.0.0:{host}-10.0.2.15:{guest}', backend)
            self.assertIn('virtio-net-device,netdev=developer,mac=52:54:00:12:34:56', result)

    def test_live_inputs_survive_later_builds_and_instances_are_independent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'software'
            guest = root / 'guest'
            guest.mkdir(parents=True)
            reference = Path(temporary) / 'resources.ext4'
            reference.write_bytes(b'reference')
            for name in ('kernel', 'initrd', 'mesa.ext4'):
                (guest / name).write_bytes(name.encode())
            profile = {'kernel': str(guest / 'kernel'), 'initrd': str(guest / 'initrd'),
                       'disks': [{'path': str(reference), 'read_only': True},
                                 {'path': str(guest / 'mesa.ext4'), 'read_only': True}]}
            (guest / 'profile.json').write_text(json.dumps(profile))
            first = json.loads(snapshot('first', root).read_text())
            second = json.loads(snapshot('second', root).read_text())
            for name in ('kernel', 'initrd', 'mesa.ext4'):
                (guest / name).write_bytes(b'rebuilt')
            for frozen in (first, second):
                self.assertEqual(Path(frozen['kernel']).read_bytes(), b'kernel')
                self.assertEqual(Path(frozen['initrd']).read_bytes(), b'initrd')
                self.assertEqual(Path(frozen['disks'][1]['path']).read_bytes(), b'mesa.ext4')
                self.assertEqual(frozen['disks'][0]['path'], str(reference))
            self.assertNotEqual(first['initrd'], second['initrd'])
            Path(first['disks'][1]['path']).write_bytes(b'first')
            self.assertEqual(Path(second['disks'][1]['path']).read_bytes(), b'mesa.ext4')

    def test_instance_names_cannot_escape_state_and_lock_directories(self):
        for name in ('../live', '', 'Live', 'x' * 33, 'a/b', 'a;exit'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                instance_name(name)
        self.assertEqual(instance_name('dev-2'), 'dev-2')
        self.assertEqual(state_path('live'), Path('/software/live.json'))
        self.assertEqual(state_path('dev-2'), Path('/software/instances/dev-2.json'))
