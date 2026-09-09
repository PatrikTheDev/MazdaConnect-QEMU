import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path('scripts/firmware').resolve()))
import resources


class ResourceTests(unittest.TestCase):
    def parse(self, rows):
        return resources.instructions('[Instructions]\nCount=' + str(len(rows)) + '\n' +
                                      '\n'.join(f'{i}={row}' for i, row in enumerate(rows, 1)))

    def test_mapping_preserves_mode_and_crc(self):
        entries = self.parse(['Create,"/resources/vui/",0775',
                             'Copy,"resources/f0000000001.dat","/resources/vui/test",0755,"0x192972C3"'])
        self.assertEqual(entries[0]['mode'], 0o775)
        self.assertEqual(entries[1]['source'], 'resources/f0000000001.dat.gz')
        self.assertEqual(entries[1]['crc32'], 0x192972c3)

    def test_rejects_commands_traversal_duplicates_and_file_parents(self):
        for rows in [
            ['Execute,"touch /tmp/unexpected"'],
            ['Create,"/resources/../outside",0755'],
            ['Create,"/resources/a",0755', 'Create,"/resources/a/",0755'],
            ['Copy,"../f0000000001.dat","/resources/a",0755,"0x00000000"'],
            ['Copy,"resources/f0000000001.dat","/resources/a",0755,"0x00000000"',
             'Create,"/resources/a/b",0755'],
        ]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.parse(rows)

    def test_does_not_accept_missing_numbered_instruction(self):
        with self.assertRaises(ValueError):
            resources.instructions('[Instructions]\nCount=2\n1=Create,"/resources/a",0755')
