"""Read-only/external-isolated Codex installation smoke tests."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

INSTALLER = Path(__file__).resolve().parents[1] / 'scripts' / 'install_codex.py'


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.home = Path(self.sandbox.name)
        self.env = {**os.environ, 'HOME': str(self.home), 'XDG_DATA_HOME': str(self.home / '.local' / 'share')}

    def run_installer(self, *args, expected=0):
        p = subprocess.run([sys.executable, str(INSTALLER), *args], capture_output=True, text=True, env=self.env)
        self.assertEqual(p.returncode, expected, f'{p.stdout}\n{p.stderr}')
        return p

    def test_dry_run_does_not_write(self):
        p=self.run_installer('--dry-run')
        self.assertEqual(json.loads(p.stdout)['skills_to_register'], 30)
        self.assertFalse((self.home/'.agents').exists())

    def test_global_install_and_extension_registration(self):
        self.run_installer()
        hub=self.home/'.agents'/'skills'/'seo'
        self.assertTrue((hub/'SKILL.md').is_file())
        self.assertEqual(len(list((self.home/'.agents'/'skills').iterdir())), 30)
        cmd=hub/'scripts'/'codex-seo'
        p=subprocess.run(['bash',str(cmd),'doctor','--json'],capture_output=True,text=True,env=self.env)
        self.assertIn(p.returncode, (0, 3), p.stderr)  # doctor returns 3 if dependencies are not yet set up
        self.assertIn('ready', json.loads(p.stdout))
        self.run_installer('--with-extensions')
        self.assertEqual(len(list((self.home/'.agents'/'skills').iterdir())), 37)
        self.assertTrue((self.home/'.agents'/'skills'/'seo-firecrawl'/'SKILL.md').is_file())
        self.run_installer('--with-extensions')  # idempotent re-install

    def test_foreign_skill_collision_is_safe(self):
        foreign=self.home/'.agents'/'skills'/'seo'
        foreign.mkdir(parents=True)
        (foreign/'SKILL.md').write_text('do not touch\n')
        p=self.run_installer(expected=1)
        self.assertIn('Refusing to overwrite',p.stderr)
        self.assertEqual((foreign/'SKILL.md').read_text(),'do not touch\n')
        self.assertFalse((self.home/'.local'/'share'/'codex-seo').exists())


if __name__ == '__main__':
    unittest.main()
