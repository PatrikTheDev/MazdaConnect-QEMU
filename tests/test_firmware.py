import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('firmware', 'scripts/firmware/manage.py')
fw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fw)


class FirmwareTests(unittest.TestCase):
    def test_encrypted_archive_requires_correct_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'input.txt'
            source.write_text('firmware fixture')
            package = Path(tmp) / 'encrypted.zip'
            subprocess.run(['7z', 'a', '-tzip', '-pfixture', str(package), str(source)],
                           check=True, stdout=subprocess.DEVNULL)
            target = Path(tmp) / 'outer'
            with patch.dict(fw.os.environ, {'FIRMWARE_ZIP_PASSWORD': 'wrong'}):
                with self.assertRaises(ValueError):
                    fw.extract(package, target)
            self.assertFalse(target.exists())
            with patch.dict(fw.os.environ, {'FIRMWARE_ZIP_PASSWORD': 'fixture'}):
                fw.extract(package, target)
            self.assertEqual((target / 'input.txt').read_text(), 'firmware fixture')

    def test_corrupt_import_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(fw, 'STORE', Path(tmp) / 'store'):
            source = Path(tmp) / 'source'
            source.write_bytes(b'original')
            data = {'id': 'fixture', 'size': 8, 'sha256': fw.digest(source)}
            target = fw.install(source, data)
            source.write_bytes(b'modified')
            with self.assertRaises(ValueError):
                fw.install(source, data)
            self.assertEqual(target.read_bytes(), b'original')
            with self.assertRaises(ValueError):
                fw.install(source, dict(data, id='bad'))
            self.assertFalse((fw.STORE / 'bad/original.up').exists())

    def test_traversal_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / 'package.up'
            with zipfile.ZipFile(package, 'w') as archive:
                archive.writestr('valid', 'ok')
                archive.writestr('../escaped', 'bad')
            target = Path(tmp) / 'outer'
            with self.assertRaises(ValueError):
                fw.extract(package, target)
            self.assertFalse(target.exists())
            self.assertFalse((Path(tmp) / 'escaped').exists())

    def test_signed_zip_and_executable_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / 'package.up'
            with zipfile.ZipFile(package, 'w') as archive:
                entry = zipfile.ZipInfo('bootstrap/run.sh')
                entry.external_attr = 0o100755 << 16
                archive.writestr(entry, '#!/bin/sh\n')
            with package.open('ab') as stream:
                stream.write(b'x' * 256)
            target = Path(tmp) / 'outer'
            fw.extract(package, target)
            self.assertEqual((target / 'bootstrap/run.sh').stat().st_mode & 0o777, 0o755)

    def test_incomplete_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text(json.dumps({'id': 'eu-v74', 'sha256': None}))
            with self.assertRaises(ValueError):
                fw.manifest(path)
