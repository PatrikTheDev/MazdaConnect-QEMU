import gzip
import importlib.util
import io
from pathlib import Path
import stat
import struct
import sys
import unittest

sys.path.insert(0, str(Path('scripts/firmware').resolve()))
sys.path.insert(0, str(Path('scripts/guest').resolve()))
import bootimage

spec = importlib.util.spec_from_file_location('guest_build', 'scripts/guest/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class BootImageTests(unittest.TestCase):
    def image(self):
        data = bytearray(2048)
        data[:4] = b'TOOB'
        struct.pack_into('<I', data, 4, 3)
        ramdisk = gzip.compress(b'fixture', mtime=0)
        for index, values in enumerate([(0, 20, 48, 1, 1), (2, 20, 4, 2, 1), (1, 20, len(ramdisk), 3, 1)]):
            struct.pack_into('<5I', data, 64+index*20, *values)
        data[512+36:512+40] = b'\x18\x28\x6f\x01'
        data[1024:1028] = b'abc\0'
        data[1536:1536+len(ramdisk)] = ramdisk
        return data

    def test_wrapper_offsets_and_overlap(self):
        data = self.image()
        result = bootimage.split_boot(data)
        self.assertEqual([x['offset'] for x in result], [512, 1024, 1536])
        struct.pack_into('<I', data, 64+20+12, 1)
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            bootimage.split_boot(data)

    def test_newc_metadata_and_binary_content(self):
        out = io.BytesIO()
        content = b'\0binary\xff'
        build.write_entry(out, 'bin/test', stat.S_IFREG | 0o4755, 42, 24, 0, len(content), io.BytesIO(content), 1)
        link = b'/bin/test'
        build.write_entry(out, 'bin/link', stat.S_IFLNK | 0o777, 42, 24, 0, len(link), io.BytesIO(link), 2)
        build.write_entry(out, 'TRAILER!!!', 0, 0, 0, 0, 0, io.BytesIO(), 0)
        items = bootimage.parse_newc(out.getvalue())
        self.assertEqual(items[0]['data'], content)
        self.assertEqual(items[0]['uid'], 42)
        self.assertEqual(items[0]['gid'], 24)
        self.assertEqual(items[0]['mode'], stat.S_IFREG | 0o4755)
        self.assertEqual(items[1]['data'], link)
        with self.assertRaises(ValueError):
            bootimage.parse_newc(out.getvalue()[:-8])
