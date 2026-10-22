"""Auto-select persisted Python only when caller did not explicitly override it."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class CodexLauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.scripts=self.folder/'scripts'
        self.scripts.mkdir()
        shutil.copy2(ROOT/'scripts/codex-seo',self.scripts/'codex-seo')
        stub=self.scripts/'claude-seo'
        stub.write_text('#!/usr/bin/env bash\nprintf "%s" "${CLAUDE_SEO_PYTHON:-unset}"\n')
        stub.chmod(0o755)
        self.data=self.folder/'data'
        self.data.mkdir()
        self.env={**os.environ,'CLAUDE_SEO_DATA_DIR':str(self.data)}
        self.env.pop('CLAUDE_SEO_PYTHON',None)

    def call(self):
        return subprocess.run([str(self.scripts/'codex-seo')],env=self.env,
                              capture_output=True,text=True,check=True).stdout

    def test_autoselect_existing_python_version_from_state(self):
        executable=shutil.which('python3.11')
        if not executable:
            self.skipTest('Python 3.11 is not in PATH')
        (self.data/'runtime-state.json').write_text(json.dumps({'python':'3.11'}))
        self.assertEqual(Path(self.call()).resolve(),Path(executable).resolve())

    def test_explicit_python_override_has_priority(self):
        (self.data/'runtime-state.json').write_text(json.dumps({'python':'3.11'}))
        self.env['CLAUDE_SEO_PYTHON']='/opt/custom/python3'
        self.assertEqual(self.call(),'/opt/custom/python3')

    def test_malformed_and_untrusted_state_are_ignored(self):
        (self.data/'runtime-state.json').write_text('{invalid JSON')
        self.assertEqual(self.call(),'unset')
        (self.data/'runtime-state.json').write_text(json.dumps({'python':'3.11;rm -rf /'}))
        self.assertEqual(self.call(),'unset')

    def test_absent_state_preserves_default_selection(self):
        self.assertEqual(self.call(),'unset')


if __name__=='__main__':
    unittest.main()
