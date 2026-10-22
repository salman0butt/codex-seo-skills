"""Runtime validation, fail-closed setup and source-CLI smoke regressions."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('codex_runtime',ROOT/'scripts/runtime.py')
assert SPEC and SPEC.loader
runtime=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class RuntimeContracts(unittest.TestCase):
    def test_setup_dependency_failure_is_atomic(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            (base/'requirements.txt').write_text('something>=1\n')
            (base/'scripts').mkdir()
            env={'CLAUDE_SEO_DATA_DIR':str(base/'runtime-data')}
            calls=[]
            def fail_at_deps(argv,*,env,stage):
                calls.append(stage)
                if stage=='dependency installation':
                    raise RuntimeError('Test-only simulated missing network')
                if stage=='virtual environment creation':
                    (base/'runtime-data'/'.venv.next-1'/'bin').mkdir(parents=True,exist_ok=True)
                return SimpleNamespace(returncode=0)
            # Don't create a real venv or install any dependency.
            original=runtime._run_checked
            with patch.dict(os.environ,env),patch.object(runtime,'_root',return_value=base),patch.object(runtime,'_run_checked',side_effect=fail_at_deps):
                result=runtime.command_setup(SimpleNamespace(skip_browser=True))
            self.assertEqual(result,1)
            self.assertIn('dependency installation',calls)
            self.assertFalse((base/'runtime-data'/'runtime-state.json').exists())
            self.assertFalse((base/'runtime-data'/'.venv').exists())
            self.assertFalse((base/'runtime-data'/'.setup.lock').exists())
            self.assertIsNotNone(original)

    def test_interrupted_setup_rolls_back_staged_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'requirements.txt').write_text('requests>=2\n',encoding='utf-8')
            (root/'scripts').mkdir()
            data=root/'runtime-data'
            def interrupted(argv, *, env, stage):
                if stage=='virtual environment creation':
                    Path(argv[-1]).mkdir(parents=True,exist_ok=True)
                    return SimpleNamespace(returncode=0)
                if stage=='pip bootstrap':
                    raise KeyboardInterrupt()
                return SimpleNamespace(returncode=0)
            with patch.dict(os.environ, {'CLAUDE_SEO_DATA_DIR':str(data)}), patch.object(runtime,'_root',return_value=root), patch.object(runtime,'_run_checked',side_effect=interrupted):
                result=runtime.command_setup(SimpleNamespace(skip_browser=True))
            self.assertEqual(result,130)
            self.assertFalse(list(data.glob('.venv.next-*')))
            self.assertFalse((data/'.setup.lock').exists())
            self.assertFalse((data/'runtime-state.json').exists())
            self.assertFalse((data/'.venv').exists())

    def test_public_cli_doctor_and_restricted_run(self):
        with tempfile.TemporaryDirectory() as folder:
            env={**os.environ,'CLAUDE_SEO_DATA_DIR':str(Path(folder)/'data')}
            launcher=ROOT/'scripts'/'codex-seo'
            check=subprocess.run([str(launcher),'doctor','--json'],env=env,capture_output=True,text=True)
            self.assertEqual(check.returncode,3,check.stderr)
            report=json.loads(check.stdout)
            self.assertFalse(report['ready'])
            self.assertFalse(report['browser_ready'])
            rejected=subprocess.run([str(launcher),'run','../runtime.py'],env=env,capture_output=True,text=True)
            self.assertEqual(rejected.returncode,2)
            self.assertIn('bundled Python script basename',rejected.stderr)
            blocked=subprocess.run([str(launcher),'run','metadata_template.py','--help'],env=env,capture_output=True,text=True)
            self.assertEqual(blocked.returncode,3)
            self.assertIn('not ready',blocked.stderr)

    def test_stdlib_offline_schema_and_metadata_smoke(self):
        schema=subprocess.run([sys.executable,str(ROOT/'scripts/schema_generate.py'),'profile','--name','Example Studio','--url','https://example.com/about'],capture_output=True,text=True)
        self.assertEqual(schema.returncode,0,schema.stderr)
        self.assertIn('https://schema.org',schema.stdout)
        metadata=subprocess.run([sys.executable,str(ROOT/'scripts/metadata_template.py'),'--title','Example Studio | Pricing','--description','Example Studio | Pricing. Get started now!','--url','https://example.com/pricing','--json'],capture_output=True,text=True)
        self.assertEqual(metadata.returncode,0,metadata.stderr)
        parsed=json.loads(metadata.stdout)
        self.assertIn('pages_checked',parsed)


if __name__=='__main__':
    unittest.main()
