import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('guest', 'scripts/guest/boot.py')
guest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guest)


class GuestTests(unittest.TestCase):
    def test_missing_input_is_reported_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Missing kernel'):
                guest.command({'kernel': str(Path(tmp) / 'missing')})

    def test_debug_graphics_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            kernel = Path(tmp) / 'kernel with spaces'
            kernel.touch()
            profile = {'kernel': str(kernel), 'initrd': str(kernel),
                       'machine': 'virt-7.2,highmem=off', 'cpu': 'cortex-a15',
                       'memory_mb': 1024, 'append': 'console=ttyAMA0', 'graphics': True}
            args = guest.command(profile, debug=True)
            self.assertEqual(args[args.index('-kernel') + 1], str(kernel))
            self.assertIn('-S', args)
            self.assertIn('virtio-gpu-pci', args)
            self.assertEqual(args[args.index('-nic') + 1], 'none')

    def test_disk_read_only_and_missing_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / 'image'
            image.touch()
            profile = {'kernel': str(image), 'initrd': str(image), 'machine': 'virt',
                       'cpu': 'cortex-a15', 'memory_mb': 1536, 'append': '',
                       'disks': [{'path': str(image)}, {'path': str(image), 'read_only': False}]}
            args = guest.command(profile)
            drives = [args[i + 1] for i, value in enumerate(args) if value == '-drive']
            self.assertIn('readonly=on', drives[0])
            self.assertIn('readonly=off', drives[1])
            profile['disks'][0]['path'] = str(Path(tmp) / 'missing')
            with self.assertRaisesRegex(ValueError, 'Missing disk'):
                guest.command(profile)
