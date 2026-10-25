"""Stable Codex release gates, offline; no upstream fetches or credentials."""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StableReleaseReadiness(unittest.TestCase):
    def test_upstream_security_sync_matches_pinned_checksums(self):
        manifest=json.loads((ROOT/'docs/UPSTREAM_SECURITY_SYNC_v1.0.0.json').read_text())
        self.assertEqual(manifest['schema_version'],1)
        self.assertEqual(manifest['license'],'MIT')
        self.assertEqual(manifest['upstream_commit'],'6be93f45064ffbadced572b5d5c95f55fd263af0')
        self.assertEqual(manifest['upstream_package_version'],'2.5.0')
        self.assertEqual(len(manifest['mirrored_paths']),11)
        for rel,digest in manifest['mirrored_paths'].items():
            with self.subTest(path=rel):
                self.assertFalse(rel.startswith(('/', '..')))
                self.assertRegex(digest,r'^[0-9a-f]{64}$')
                self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),digest)

    def test_distribution_and_upstream_versions_are_distinct_and_documented(self):
        plugin=json.loads((ROOT/'plugin.json').read_text())
        self.assertEqual(plugin['name'],'codex-seo-skills')
        self.assertIn(plugin['version'], ('1.0.0','1.1.0','1.2.0','1.3.0'))
        project=(ROOT/'pyproject.toml').read_text()
        self.assertRegex(project,r'(?m)^version = "2\.5\.0"$')
        self.assertIn('requires-python = ">=3.11"',project)
        guide=(ROOT/'docs/PRODUCTION_READINESS_v1.0.0.md').read_text()
        self.assertIn('Codex distribution',guide)
        self.assertIn('upstream Python',guide)

    def test_skill_and_agent_inventory_is_stable(self):
        names={p.parent.name for p in (ROOT/'skills').glob('*/SKILL.md')}
        self.assertEqual(len(names),30)
        self.assertEqual(len(list((ROOT/'agents').glob('*.md'))),19)
        optional=list((ROOT/'extensions').rglob('SKILL.md'))
        self.assertEqual(len(optional),9)
        self.assertEqual(len({p.parent.name for p in optional}-names),7)
        self.assertTrue({'seo','get-started','seo-handoff','seo-performance','seo-visual'} <= names)

    def test_stable_docs_distinguish_native_vs_unverified(self):
        readme=(ROOT/'README.md').read_text()
        notes=(ROOT/'docs/RELEASE_NOTES_v1.0.0.md').read_text()
        cap=(ROOT/'docs/PRODUCTION_READINESS_v1.0.0.md').read_text()
        self.assertIn('docs/RELEASE_NOTES_v1.0.0.md',readme)
        self.assertIn('rollback',notes.lower())
        for term in ('Claude-specific hooks','Not ported','Search Console / GA4','Python 3.11','Windows','live'):
            self.assertIn(term,cap)
        self.assertIn('proprietary',cap)
        self.assertIn('No credentials',notes)

    def test_github_actions_are_pinned_to_supported_runner_and_actions(self):
        workflow=(ROOT/'.github/workflows/validate.yml').read_text()
        self.assertIn('runs-on: ubuntu-24.04',workflow)
        self.assertIn('uses: actions/checkout@v5',workflow)
        self.assertIn('uses: actions/setup-python@v6',workflow)
        self.assertNotIn('runs-on: ubuntu-latest',workflow)
        self.assertNotIn('uses: actions/checkout@v4',workflow)
        self.assertNotIn('uses: actions/setup-python@v5',workflow)

    def test_public_installer_and_runtime_have_guards(self):
        installer=(ROOT/'scripts/install_codex.py').read_text()
        for guard in ('committed = False','backup.rename(root)','previous.rename(dest)','link_backups'):
            self.assertIn(guard,installer)
        runtime=(ROOT/'scripts/runtime.py').read_text()
        self.assertIn('MIN_PYTHON = (3, 11)',runtime)
        self.assertIn('MAX_PYTHON = (3, 14)',runtime)
        self.assertIn('codex.get("name") == "codex-seo-skills"',runtime)
        browser=(ROOT/'scripts/url_safety.py').read_text()
        self.assertIn('MAX_REDIRECT_BODY_BYTES',browser)
        self.assertIn('new_guarded_context',browser)
        self.assertIn('read_bounded',browser)


if __name__=='__main__':
    unittest.main()
