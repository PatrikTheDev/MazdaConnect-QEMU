"""Verify factory overlay integrity and preservation of native service dependencies."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('factory_debug', 'scripts/software/build_factory_debug.py')
factory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(factory)


class FactoryDebugTests(unittest.TestCase):
    def test_rejects_modified_firmware(self):
        with patch.object(Path, 'read_bytes', return_value=b'changed input'):
            for relative in factory.SOURCE_HASHES:
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    factory.verified(relative)

    def test_keeps_native_dependencies_in_opt_in_profile(self):
        base = b'<sm><services><service name="jciVBS"/></services></sm>'
        stock = b'''<sm><services><service name="jciTestDiag"
          path="/jci/testdiag/svcjcitestdiag.so" reset_board="yes" retry_count="3">
          <dependency type="service" value="jciVBS"/>
          <dependency type="service" value="system_mazda_my14"/>
        </service></services></sm>'''
        with patch.object(factory, 'verified', return_value=stock):
            result = ET.fromstring(factory.service_config(base))
        service = result.find('.//service[@name="jciTestDiag"]')
        self.assertEqual(service.get('reset_board'), 'no')
        self.assertEqual(service.get('retry_count'), '0')
        self.assertEqual(service.get('path'), '/jci/testdiag/svcjcitestdiag.so')
        self.assertEqual([item.get('value') for item in service],
                         ['jciVBS', 'system_mazda_my14'])
        self.assertIsNone(ET.fromstring(base).find('.//service[@name="jciTestDiag"]'))

    def test_only_adds_debug_script_to_verified_entry_point(self):
        source = b'<html><body><script>framework.init();</script></body></html>'
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(factory, 'verified', return_value=source):
                result = factory.build(Path(directory))
            self.assertEqual(result.replace(
                b'<script src="file:///lab-software/factory-debug.js"></script>\n    ', b''), source)
            self.assertTrue((Path(directory) / 'factory-debug.json').exists())

    def test_rejects_ambiguous_injection_site(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(factory, 'verified', return_value=b'</body></body>'):
                with self.assertRaises(ValueError):
                    factory.build(Path(directory))
