"""Google Indexing API mutations require explicit eligibility and publish confirmation."""
from __future__ import annotations
import contextlib
import importlib.util
import io
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT=Path(__file__).resolve().parents[1]


class IndexingPublishGuardTests(unittest.TestCase):
    def setUp(self):
        discovery=types.ModuleType('googleapiclient.discovery')
        discovery.build=MagicMock()
        package=types.ModuleType('googleapiclient')
        package.discovery=discovery
        auth=types.ModuleType('google_auth')
        auth.get_oauth_credentials=MagicMock()
        auth.validate_url=MagicMock(return_value=True)
        path=ROOT/'scripts/indexing_notify.py'
        spec=importlib.util.spec_from_file_location('test_indexing_guard_module',path)
        assert spec and spec.loader
        self.module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'googleapiclient':package,'googleapiclient.discovery':discovery,'google_auth':auth}):
            spec.loader.exec_module(self.module)
        self.calls=MagicMock()
        self.module.notify_url=self.calls
        self.module.batch_notify=self.calls
        self.module.get_notification_metadata=MagicMock(return_value={'latest_update':None,'latest_remove':None,'error':None})

    def call(self, args):
        with patch.object(sys,'argv',['indexing_notify.py',*args]),contextlib.redirect_stderr(io.StringIO()) as errors, contextlib.redirect_stdout(io.StringIO()):
            try:
                self.module.main()
            except SystemExit as exc:
                return exc.code, errors.getvalue()
        return 0, errors.getvalue()

    def test_single_requires_both_explicit_flags(self):
        for extra in [[],['--confirm-publish'],['--eligible-type','JobPosting']]:
            with self.subTest(flags=extra):
                status,stderr=self.call(['https://example.com/jobs/123',*extra,'--json'])
                self.assertEqual(status,2)
                self.assertIn('publishing requires',stderr)
        self.calls.assert_not_called()

    def test_batch_requires_both_flags_before_reading_file(self):
        status,stderr=self.call(['--batch','/tmp/file-that-does-not-exist'])
        self.assertEqual(status,2)
        self.assertIn('publishing requires',stderr)
        self.calls.assert_not_called()

    def test_explicit_eligible_type_and_confirmation_dispatch(self):
        self.calls.return_value={'url':'https://example.com/job','action':'URL_UPDATED','notify_time':None,'error':None}
        status,_=self.call(['https://example.com/job','--eligible-type','JobPosting','--confirm-publish','--json'])
        self.assertEqual(status,0)
        self.calls.assert_called_once_with('https://example.com/job','URL_UPDATED')

    def test_status_only_remains_read_only(self):
        status,_=self.call(['--status','https://example.com/job','--json'])
        self.assertEqual(status,0)
        self.module.get_notification_metadata.assert_called_once()
        self.calls.assert_not_called()


if __name__=='__main__': unittest.main()
