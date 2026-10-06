"""Exercise host argument boundaries without Docker or private firmware."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class LabCliTests(unittest.TestCase):
    def invoke(self, *args):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            trace = root / 'arguments'
            docker = root / 'docker'
            docker.write_text('#!/bin/sh\nprintf "%s\\0" "$@" >> "$MAZDA_TEST_TRACE"\n')
            docker.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                       MAZDA_TEST_TRACE=str(trace))
            result = subprocess.run(['bash', 'scripts/lab.sh', *args], env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            calls = trace.read_bytes().decode().split('\0')[:-1] if trace.exists() else []
            return result, calls

    def test_research_arguments_are_not_evaluated(self):
        argument = 'path with spaces; $(exit 99) "quoted"'
        result, calls = self.invoke('dev', 'firmware', 'manage', 'inspect', argument)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls[-3:], ['scripts/firmware/manage.py', 'inspect', argument])
        self.assertEqual(calls[:3], ['compose', '-f', 'compose.yaml'])

    def test_rejects_script_traversal_before_docker(self):
        result, calls = self.invoke('dev', 'software', '../firmware/manage')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(calls, [])

    def test_rejects_unknown_scope_before_docker(self):
        result, calls = self.invoke('dev', 'unknown', 'manage')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(calls, [])

    def test_live_entry_point_preserves_overrides_and_publishes_ports(self):
        result, calls = self.invoke('start', '--renderer', 'softpipe', '--seconds', '20')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--service-ports', calls)
        self.assertEqual(calls[-4:], ['--renderer', 'softpipe', '--seconds', '20'])
        self.assertIn('vmsplit2g', calls)

    def test_setup_rejects_inputs_outside_ignored_artifacts(self):
        with tempfile.NamedTemporaryFile(suffix='.up') as package:
            result, calls = self.invoke('setup', package.name)
        self.assertEqual(result.returncode, 2)
        self.assertIn('directly in artifacts/', result.stderr)
        self.assertEqual(calls, [])
