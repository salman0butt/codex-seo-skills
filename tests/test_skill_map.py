"""End-to-end file/guide/script graph sanity checks (no external APIs)."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs' / 'skill-agent-map.json'


class SkillMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads(DATA.read_text(encoding='utf-8'))
        cls.files = {r['path']: r for r in cls.graph['files']}

    def test_every_repo_file_catalogued(self):
        raw = subprocess.run(
            ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
            cwd=ROOT, check=True, capture_output=True,
        ).stdout
        tracked = {p for p in raw.decode('utf-8').split('\0') if p and (ROOT / p).is_file()}
        self.assertEqual(set(self.files), tracked)
        self.assertEqual(len(self.files), self.graph['counts']['total_repo_files'])
        self.assertTrue(all((ROOT / p).is_file() for p in self.files))
        self.assertTrue(all(r['kind'] and r['owner'] for r in self.files.values()))

    def test_skill_and_agent_roots(self):
        self.assertEqual(len(self.graph['skills']), 26)
        self.assertEqual(len([r for r in self.files.values() if r['kind']=='specialist-agent-guide']), 19)
        self.assertEqual({x['name'] for x in self.graph['agent_only']}, {'seo-performance','seo-visual'})
        for skill in self.graph['skills']:
            name=skill['name']
            self.assertEqual(skill['manifest'], f'skills/{name}/SKILL.md')
            self.assertIn(skill['manifest'], self.files)
            self.assertEqual(self.files[skill['manifest']]['kind'],'skill-entrypoint')
            guide = skill['agent_guide']
            if guide:
                mirror=skill['reference_guide_mirror']
                self.assertEqual((ROOT/guide).read_bytes(), (ROOT/mirror).read_bytes())
                self.assertIn(guide,self.files)
                self.assertIn(mirror,self.files)

    def test_graph_no_dangling_edges_and_adjacency(self):
        for link in self.graph['edges']:
            src, dst, relation = link['from'], link['to'], link['relation']
            self.assertIn(src,self.files)
            self.assertIn(dst,self.files)
            self.assertIn({'path':dst,'relation':relation},self.files[src]['outgoing'])
            self.assertIn({'path':src,'relation':relation},self.files[dst]['incoming'])

    def test_unique_extension_registration(self):
        extensions = self.graph['extensions']
        self.assertEqual(len(extensions), 9)
        self.assertEqual(sum(x['registered_with_with_extensions'] for x in extensions), 7)
        self.assertEqual({x['skill_name'] for x in extensions if x['core_name_collision']}, {'seo-image-gen', 'seo-dataforseo'})

    def test_generator_check_is_deterministic(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/generate_skill_map.py'),'--check'],
                              cwd=ROOT, capture_output=True,text=True)
        self.assertEqual(result.returncode,0,f'{result.stdout}\n{result.stderr}')


if __name__ == '__main__':
    unittest.main()
