"""Portable manifest, skill contract and optional integration boundaries."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class ManifestContracts(unittest.TestCase):
    def test_plugin_manifest_and_onboarding(self):
        payload=json.loads((ROOT/'plugin.json').read_text(encoding='utf-8'))
        self.assertEqual(payload['name'],'codex-seo-skills')
        self.assertEqual(payload['version'],'0.9.0')
        self.assertEqual(payload['license'],'MIT')
        self.assertEqual(payload['$schema'],'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json')
        onboarding=payload['extensions']['com.openai']['onboardingSkill']
        self.assertTrue(onboarding.startswith('./'))
        self.assertTrue((ROOT/onboarding).is_file())
        self.assertNotIn('mcpServers',payload)  # Never silently opt in to providers.

    def test_all_core_skill_entrypoints_are_installed(self):
        skills=sorted((ROOT/'skills').glob('*/SKILL.md'))
        self.assertEqual(len(skills),30)
        names=[]
        for skill in skills:
            text=skill.read_text(encoding='utf-8')
            name=skill.parent.name
            self.assertTrue(text.startswith('---\n'),name)
            self.assertIn(f'name: {name}\n',text)
            self.assertRegex(text,r'(?m)^description: .+')
            self.assertTrue((skill.parent/'agents'/'openai.yaml').is_file())
            names.append(name)
        self.assertEqual(len(names),len(set(names)))
        for added in ['get-started','seo-handoff','seo-performance','seo-visual']:
            self.assertIn(added,names)

    def test_core_route_falls_back_without_subagents(self):
        for file in ['AGENTS.md','skills/seo/SKILL.md','skills/seo-audit/SKILL.md']:
            text=(ROOT/file).read_text(encoding='utf-8').lower()
            self.assertIn('sequential',text,file)
        self.assertTrue((ROOT/'docs/LEGACY_CODEX_COMPARISON.md').is_file())
        self.assertIn('proprietary',(ROOT/'docs/LEGACY_CODEX_COMPARISON.md').read_text().lower())


if __name__=='__main__':
    unittest.main()
