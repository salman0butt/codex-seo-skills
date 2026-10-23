"""Schedules are printed only; never activated, never contain secrets."""
from __future__ import annotations
import importlib.util
import io
import plistlib
import shlex
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('seo_schedule_template',ROOT/'scripts/seo_schedule_template.py')
module=importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


class ScheduleTemplateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        self.launcher=self.directory/'space name'/'codex-seo'
        self.history=self.directory/'private-history'
        self.input=self.directory/"file name; echo PWNED.json"

    def test_cron_quotes_all_local_paths_and_never_executes(self):
        with patch('subprocess.run',side_effect=AssertionError('Unexpected process')):
            line=module.build('cron',launcher=self.launcher,history_dir=self.history,
                              sources={'gsc-current':self.input})
        self.assertIn('0 9 * * 1 umask 077;',line)
        self.assertIn(shlex.quote(str(self.input)),line)
        self.assertNotIn('--live',line)
        self.assertNotIn('--confirm-history-same-property',line)
        self.assertFalse(self.history.exists())
        self.assertFalse(self.input.exists())

    def test_launchd_contains_only_bounded_args_and_private_logs(self):
        xml=module.build('launchd',launcher=self.launcher,history_dir=self.history,
                         sources={'quick-audit':[self.input]})
        parsed=plistlib.loads(xml.encode())
        self.assertEqual(parsed['Umask'],0o077)
        self.assertFalse(parsed['RunAtLoad'])
        self.assertEqual(parsed['StartCalendarInterval'],{'Weekday':1,'Hour':9,'Minute':0})
        self.assertEqual(parsed['ProgramArguments'][-2:],['--quick-audit',str(self.input)])
        self.assertEqual(parsed['StandardOutPath'],str(self.history/'scheduled-stdout.log'))
        self.assertFalse(self.history.exists())

    def test_main_only_emits_template(self):
        buffer=io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(module.main(['--platform','cron','--history-dir',str(self.history),
                                          '--quick-audit',str(self.input)]),0)
        self.assertIn('seo_history.py record',buffer.getvalue())
        self.assertFalse(self.history.exists())

    def test_empty_or_unsupported_schedule_fails(self):
        with self.assertRaises(ValueError):
            module.build('cron',launcher=self.launcher,history_dir=self.history,sources={})
        with self.assertRaises(ValueError):
            module.build('windows',launcher=self.launcher,history_dir=self.history,
                         sources={'gsc-current':self.input})


if __name__=='__main__':unittest.main()
