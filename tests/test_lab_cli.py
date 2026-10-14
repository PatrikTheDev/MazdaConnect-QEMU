"""Exercise host argument boundaries without Docker or private firmware."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class LabCliTests(unittest.TestCase):
    def invoke(self, *args, extra_env=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            trace = root / 'arguments'
            docker = root / 'docker'
            docker.write_text('#!/bin/sh\nprintf "%s\\0" "$@" >> "$MAZDA_TEST_TRACE"\n')
            docker.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                       MAZDA_TEST_TRACE=str(trace))
            env.update(extra_env or {})
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
        self.assertIn('127.0.0.1:5901:5900', calls)
        self.assertEqual(calls[-4:], ['--renderer', 'softpipe', '--seconds', '20'])
        self.assertIn('vmsplit2g', calls)
        self.assertNotIn('127.0.0.1:8080:8080', calls)

    def test_developer_mode_publishes_http_and_native_websocket_ports_on_loopback(self):
        for action in ('start', 'restart'):
            result, calls = self.invoke(action, '--developer-mode')
            self.assertEqual(result.returncode, 0, result.stderr)
            ports = [calls[i + 1] for i, value in enumerate(calls) if value == '--publish']
            self.assertEqual(ports, ['127.0.0.1:5901:5900', '127.0.0.1:8080:8080', '127.0.0.1:2700:2700',
                                     '127.0.0.1:2766:2766', '127.0.0.1:2800:2800'])
            self.assertEqual(calls[-1], '--developer-mode')

    def test_remote_gui_implies_developer_port_publications(self):
        result, calls = self.invoke('start', '--remote-gui')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('127.0.0.1:8080:8080', calls)
        self.assertIn('127.0.0.1:2700:2700', calls)
        self.assertEqual(calls[-1], '--remote-gui')

    def test_named_instance_uses_distinct_container_and_host_ports(self):
        result, calls = self.invoke('restart', '--developer-mode', extra_env={
            'MAZDA_INSTANCE': 'dev-2', 'MAZDA_VNC_PORT': '5902', 'MAZDA_HTTP_PORT': '8081'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('mazda-software-dev-2', calls)
        self.assertIn('127.0.0.1:5902:5900', calls)
        self.assertIn('127.0.0.1:8081:8080', calls)

    def test_invalid_instance_name_is_rejected_before_docker(self):
        result, calls = self.invoke('start', extra_env={'MAZDA_INSTANCE': '../bad'})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(calls, [])

    def test_setup_rejects_inputs_outside_ignored_artifacts(self):
        with tempfile.NamedTemporaryFile(suffix='.up') as package:
            result, calls = self.invoke('setup', package.name)
        self.assertEqual(result.returncode, 2)
        self.assertIn('directly in artifacts/', result.stderr)
        self.assertEqual(calls, [])

    def test_setup_rejects_invalid_worker_counts_before_docker(self):
        for value in ('0', '33', '4; exit 0'):
            with self.subTest(value=value):
                result, calls = self.invoke('setup', 'artifacts/input.up', '--jobs', value)
                self.assertEqual(result.returncode, 2)
                self.assertIn('--jobs 1..32', result.stderr)
                self.assertEqual(calls, [])
