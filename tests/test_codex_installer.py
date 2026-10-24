"""Read-only/external-isolated Codex installation smoke tests."""
from __future__ import annotations
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def _module(self):
        spec = importlib.util.spec_from_file_location('codex_install_under_test', INSTALLER)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _forced_mid_install_failure(self, mod):
        """Simulate both symlink and copy fallback failing mid-registration."""
        real_symlink = Path.symlink_to
        real_copytree = mod.shutil.copytree
        root = self.home / '.agents' / 'skills'
        def broken_symlink(path, target, target_is_directory=False):
            if path == root / 'seo-audit':
                raise OSError('simulated symlink failure')
            return real_symlink(path, target, target_is_directory=target_is_directory)
        def broken_copytree(src, dst, *args, **kwargs):
            if Path(dst) == root / 'seo-audit':
                raise OSError('simulated fallback-copy failure')
            return real_copytree(src, dst, *args, **kwargs)
        with patch.object(Path,'symlink_to',broken_symlink), patch.object(mod.shutil,'copytree',broken_copytree):
            with self.assertRaisesRegex(OSError,'fallback-copy failure'):
                mod.install(False,False)

    def test_failed_upgrade_restores_previous_package_and_skill_links(self):
        self.run_installer()
        mod = self._module()
        root=self.home/'.local'/'share'/'codex-seo'
        skills=self.home/'.agents'/'skills'
        (root/'sentinel-previous-version').write_text('ORIGINAL-PACKAGE')
        old = {p.name:p.resolve() for p in skills.iterdir()}
        with patch.dict(os.environ,{'HOME':str(self.home),'XDG_DATA_HOME':str(self.home/'.local'/'share')}):
            self._forced_mid_install_failure(mod)
        self.assertEqual((root/'sentinel-previous-version').read_text(),'ORIGINAL-PACKAGE')
        self.assertEqual({p.name:p.resolve() for p in skills.iterdir()},old)
        self.assertTrue((skills/'seo-audit'/'SKILL.md').exists())
        self.assertFalse(list(root.parent.glob('.codex-seo-backup-*')))
        self.assertFalse(list(skills.glob('.codex-seo-links-backup-*')))

    def test_failed_first_install_keeps_skills_directory_clean(self):
        mod=self._module()
        root=self.home/'.local'/'share'/'codex-seo'
        skills=self.home/'.agents'/'skills'
        with patch.dict(os.environ,{'HOME':str(self.home),'XDG_DATA_HOME':str(self.home/'.local'/'share')}):
            self._forced_mid_install_failure(mod)
        self.assertFalse(root.exists())
        self.assertEqual(list(skills.iterdir()),[])
        self.assertFalse(list(root.parent.glob('.codex-seo-install-*')))

    def test_failed_upgrade_restores_fallback_skill_copy(self):
        self.run_installer()
        mod=self._module()
        root=self.home/'.local'/'share'/'codex-seo'
        skill=self.home/'.agents'/'skills'/'seo'
        skill.unlink()
        skill.mkdir()
        (skill/mod.PACKAGE_MARKER).write_text('codex-seo-skills fallback copy\n')
        (skill/'ORIGINAL-COPY').write_text('KEPT')
        with patch.dict(os.environ,{'HOME':str(self.home),'XDG_DATA_HOME':str(self.home/'.local'/'share')}):
            self._forced_mid_install_failure(mod)
        self.assertEqual((skill/'ORIGINAL-COPY').read_text(),'KEPT')
        self.assertFalse(skill.is_symlink())
        self.assertEqual((root/mod.PACKAGE_MARKER).is_file(),True)

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
