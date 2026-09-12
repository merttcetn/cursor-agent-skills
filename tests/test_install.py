import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('grok-subagent', 'cursor-subagent-3rd')


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='skills install ')
        self.addCleanup(self.temp.cleanup)
        self.dest = Path(self.temp.name)/'custom skills'

    def run_script(self, name, *extra, destination=True, env=None):
        return subprocess.run([sys.executable, str(ROOT/'scripts'/name), *(['--skills-dir', str(self.dest)] if destination else []), *extra], capture_output=True, text=True, env=env)

    def require_symlinks(self):
        link = Path(self.temp.name)/'probe'
        try:
            link.symlink_to(ROOT, target_is_directory=True)
            link.unlink()
        except OSError:
            self.skipTest('Directory symlink permission unavailable on this host')

    def test_install_run_idempotency_and_uninstall(self):
        self.require_symlinks()
        for _ in range(2):
            result = self.run_script('install.py')
            self.assertEqual(result.returncode, 0, result.stderr)
        for name in NAMES:
            link = self.dest/name
            self.assertTrue(link.is_symlink())
            args = ['--model', 'example-model'] if name == 'cursor-subagent-3rd' else []
            result = subprocess.run([sys.executable, str(link/'scripts/spawn_cursor_agent.py'), '--dry-run', *args, 'task'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['dry_run'])
        unrelated = self.dest/'unrelated.txt'
        unrelated.write_text('keep')
        for _ in range(2):
            self.assertEqual(self.run_script('uninstall.py').returncode, 0)
        self.assertEqual(unrelated.read_text(), 'keep')
        self.assertTrue((ROOT/'shared/cursor_runner.py').exists())

    def test_conflict_preflight_preserves_existing_skill(self):
        existing = self.dest/NAMES[1]
        existing.mkdir(parents=True)
        marker = existing/'SKILL.md'
        marker.write_text('original')
        for script in ('install.py', 'uninstall.py'):
            self.assertNotEqual(self.run_script(script).returncode, 0)
            self.assertEqual(marker.read_text(), 'original')
            self.assertFalse((self.dest/NAMES[0]).exists())

    def test_foreign_and_broken_symlinks_are_preserved(self):
        self.require_symlinks()
        self.dest.mkdir()
        link = self.dest/NAMES[0]
        link.symlink_to(Path(self.temp.name)/'missing', target_is_directory=True)
        for script in ('install.py', 'uninstall.py'):
            self.assertNotEqual(self.run_script(script).returncode, 0)
            self.assertTrue(link.is_symlink())

    def test_dry_run_and_codex_home(self):
        result = self.run_script('install.py', '--dry-run')
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.dest.exists())
        custom = Path(self.temp.name)/'codex home'
        result = self.run_script('install.py', '--dry-run', destination=False, env={**os.environ, 'CODEX_HOME': str(custom)})
        self.assertEqual(result.returncode, 0)
        self.assertIn(str(custom/'skills'), result.stdout)
        self.assertFalse(custom.exists())

    def test_source_destination_rejected(self):
        result = subprocess.run([sys.executable, str(ROOT/'scripts/install.py'), '--skills-dir', str(ROOT/'skills')], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
