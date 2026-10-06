"""Ensure deleting a private payload cannot bypass the publication guard."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class PublicationTests(unittest.TestCase):
    def test_deleted_binary_is_rejected_from_history(self):
        checker = Path('scripts/release/check_publication.py').resolve()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env = dict(os.environ, GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
                       GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')
            def git(*args):
                subprocess.run(['git', *args], cwd=root, env=env, check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            git('init')
            payload = root / 'payload.txt'
            payload.write_bytes(b'private\0binary')
            git('add', '.')
            git('commit', '-m', 'fixture input')
            payload.unlink()
            git('add', '-u')
            git('commit', '-m', 'remove fixture')
            result = subprocess.run(['python3', str(checker)], cwd=root,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('binary retained in reachable history', result.stderr)
