"""Offline history contracts: replay, change checks, locks, secrecy and retention."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sqlite3
import stat
import tempfile
import threading
import unittest
from pathlib import Path

import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import seo_history as history
from test_seo_report_builder import provider,quick


class HistoryContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.dir=self.root/'private-history'
        self.gsc=self.root/'gsc.json'
        self.gsc.write_text(json.dumps(provider()))
        self.quick=self.root/'audit.json'
        self.quick.write_text(json.dumps(quick('missing-title')))

    def record(self, extra=None):
        return history.run(['record','--history-dir',str(self.dir),'--gsc-current',str(self.gsc),
                            '--quick-audit',str(self.quick),*(extra or [])])
    def list(self, *args):
        return history.run(['list','--history-dir',str(self.dir),*args])

    def test_record_once_then_replay_is_unchanged(self):
        first=self.record()
        self.assertEqual(first['status'],'created')
        self.assertEqual(first['snapshot']['id'],1)
        again=self.record()
        self.assertEqual(again['status'],'unchanged')
        self.assertFalse(again['record_created'])
        self.assertEqual(len(self.list()['snapshots']),1)
        self.assertEqual(first['network_requests'],0)
        self.assertEqual(stat.S_IMODE(self.dir.stat().st_mode),0o700)
        self.assertEqual(stat.S_IMODE((self.dir/'history.sqlite3').stat().st_mode),0o600)

    def test_changed_evidence_creates_new_snapshot(self):
        self.record()
        changed=provider(metrics={'clicks':60,'impressions':950,'ctr_percent':6.32,'average_position':11.0})
        self.gsc.write_text(json.dumps(changed))
        new=self.record()
        self.assertEqual(new['status'],'created')
        self.assertEqual(new['previous_id'],1)
        self.assertEqual(new['changes']['providers']['gsc']['status'],'property_identity_not_attested')
        self.assertEqual(new['changes']['providers']['gsc']['metric_changes'],{})
        self.assertEqual(len(self.list()['snapshots']),2)
        self.assertNotIn('SECRET',json.dumps(new))
        self.assertNotIn('SECRET',str((self.dir/'history.sqlite3').read_bytes()))

    def test_cross_snapshot_delta_requires_attestation_and_adjacent_dates(self):
        prev=provider(start='2026-08-25',end='2026-09-21')
        self.gsc.write_text(json.dumps(prev))
        self.record()
        self.gsc.write_text(json.dumps(provider(metrics={
            'clicks':80,'impressions':1000,'ctr_percent':8,'average_position':9})))
        result=self.record(['--confirm-history-same-property'])
        comp=result['changes']['providers']['gsc']
        self.assertEqual(comp['status'],'compared_with_operator_attestation')
        self.assertEqual(comp['metric_changes']['clicks']['absolute_change'],40)
        self.assertEqual(comp['metric_changes']['clicks']['relative_change_percent'],100)

    def test_snapshot_comparison_rejects_unmatched_date_windows(self):
        self.record()
        self.gsc.write_text(json.dumps(provider(start='2026-10-01',end='2026-10-28')))
        comp=self.record(['--confirm-history-same-property'])['changes']['providers']['gsc']
        self.assertEqual(comp['status'],'nonadjacent_or_unequal_windows')
        self.assertEqual(comp['metric_changes'],{})

    def test_same_page_set_attested_only(self):
        self.record()
        self.quick.write_text(json.dumps(quick('missing-title','image-alt-missing')))
        without=self.record()
        self.assertEqual(without['changes']['page_findings']['status'],'page_identity_not_attested')
        self.quick.write_text(json.dumps(quick('image-alt-missing')))
        with_attestation=self.record(['--confirm-same-page-set'])
        self.assertEqual(with_attestation['changes']['page_findings']['status'],'compared_with_operator_page_attestation')
        self.assertEqual(with_attestation['changes']['page_findings']['previously_present_only'],['audit-1:missing-title'])
        self.assertIn('NOT proof',with_attestation['changes']['page_findings']['note'])

    def test_page_set_different_audit_count_does_not_infer_resolution(self):
        self.record()
        response=history.run(['record','--history-dir',str(self.dir),
                              '--gsc-current',str(self.gsc),'--confirm-same-page-set'])
        self.assertEqual(response['changes']['page_findings']['status'],'different_audit_set')

    def test_list_and_show_are_readonly_and_redacted(self):
        self.record()
        items=self.list('--limit','1')
        self.assertEqual(items['snapshots'][0]['providers'],['gsc'])
        self.assertNotIn('example.com',json.dumps(items))
        show=history.run(['show','--history-dir',str(self.dir),'--id','1'])
        self.assertEqual(show['report']['provider_reports']['gsc']['current']['metrics']['clicks'],40)
        self.assertNotIn('SECRET',json.dumps(show))
        self.assertNotIn('token-ABC123',json.dumps(show))
        self.assertEqual(show['network_requests'],0)

    def test_list_requires_existing_db_without_creation(self):
        with self.assertRaises(history.ReportInputError):
            self.list()
        self.assertFalse(self.dir.exists())

    def test_prune_gated_and_keeps_newest(self):
        self.record()
        self.gsc.write_text(json.dumps(provider(metrics={
            'clicks':55,'impressions':700,'ctr_percent':7.86,'average_position':10})))
        self.record()
        denied=history.run(['prune','--history-dir',str(self.dir),'--keep','1'])
        self.assertEqual(denied['status'],'confirmation_required')
        self.assertEqual(len(self.list()['snapshots']),2)
        result=history.run(['prune','--history-dir',str(self.dir),'--keep','1','--confirm-prune'])
        self.assertEqual(result['removed_count'],1)
        self.assertEqual(self.list()['snapshots'][0]['id'],2)
        self.assertEqual(len(self.list()['snapshots']),1)

    def test_rejects_symlink_database_or_directory(self):
        self.dir.mkdir(mode=0o700)
        outside=self.root/'elsewhere.db';outside.write_text('DO NOT TOUCH')
        (self.dir/'history.sqlite3').symlink_to(outside)
        with self.assertRaises(history.ReportInputError):self.record()
        self.assertEqual(outside.read_text(),'DO NOT TOUCH')
        alias=self.root/'alias';alias.symlink_to(self.dir,target_is_directory=True)
        with self.assertRaises(history.ReportInputError):
            history.run(['record','--history-dir',str(alias),'--gsc-current',str(self.gsc)])

    def test_optional_markdown_export_only_once_with_safe_permissions(self):
        first=self.record(['--export-markdown'])
        self.assertEqual(first['markdown_export'],'written')
        exported=self.dir/'reports'/'snapshot-000001.md'
        original=exported.read_text()
        self.assertIn('Codex SEO evidence report',original)
        self.assertNotIn('SECRET',original)
        self.assertEqual(stat.S_IMODE(exported.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(exported.parent.stat().st_mode),0o700)
        second=self.record(['--export-markdown'])
        self.assertEqual(second['markdown_export'],'already_exists')
        self.assertEqual(exported.read_text(),original)
        self.assertFalse(list(exported.parent.glob('.seo-report-*')))

    def test_markdown_export_is_opt_in_not_default(self):
        first=self.record()
        self.assertNotIn('markdown_export',first)
        self.assertFalse((self.dir/'reports').exists())

    def test_rejects_export_symlink_without_overwrite(self):
        self.record()
        (self.dir/'reports').mkdir(mode=0o700)
        target=self.root/'target.md';target.write_text('PRESERVE')
        (self.dir/'reports'/'snapshot-000001.md').symlink_to(target)
        with self.assertRaises(history.ReportInputError):
            self.record(['--export-markdown'])
        self.assertEqual(target.read_text(),'PRESERVE')

    def test_broad_history_directory_permissions_rejected(self):
        self.dir.mkdir(mode=0o777)
        os.chmod(self.dir,0o755)
        with self.assertRaises(history.ReportInputError):self.record()
        self.assertFalse((self.dir/'history.sqlite3').exists())

    def test_corrupted_db_fails_safely_and_does_not_leak_input(self):
        self.dir.mkdir(mode=0o700)
        db=self.dir/'history.sqlite3';db.write_bytes(b'not sqlite SECRET-SENSITIVE-CONTENT')
        os.chmod(db,0o600)
        stderr=io.StringIO();output=io.StringIO()
        with contextlib.redirect_stderr(stderr),contextlib.redirect_stdout(output):
            status=history.main(['record','--history-dir',str(self.dir),'--gsc-current',str(self.gsc)])
        self.assertEqual(status,2)
        self.assertNotIn('SECRET',output.getvalue()+stderr.getvalue())

    def test_concurrent_same_evidence_creates_only_one_row(self):
        errors=[]
        results=[]
        def job():
            try:results.append(self.record())
            except Exception as exc:errors.append(type(exc).__name__)
        workers=[threading.Thread(target=job) for _ in range(6)]
        for t in workers:t.start()
        for t in workers:t.join()
        self.assertEqual(errors,[])
        self.assertEqual(sorted(r['status'] for r in results),['created']+['unchanged']*5)
        self.assertEqual(len(self.list()['snapshots']),1)

    def test_reversion_after_change_is_new_observation(self):
        self.record()
        changed=provider(metrics={'clicks':55,'impressions':700,'ctr_percent':7.86,'average_position':10})
        self.gsc.write_text(json.dumps(changed));self.record()
        self.gsc.write_text(json.dumps(provider()))
        self.assertEqual(self.record()['snapshot']['id'],3)

    def test_missing_or_invalid_arguments_are_bounded(self):
        with self.assertRaises(history.ReportInputError):
            history.run(['record','--history-dir',str(self.dir)])
        self.record()
        with self.assertRaises(history.ReportInputError):
            self.list('--limit','1000')
        with self.assertRaises(history.ReportInputError):
            history.run(['prune','--history-dir',str(self.dir),'--keep','0','--confirm-prune'])
        with self.assertRaises(history.ReportInputError):
            history.run(['show','--history-dir',str(self.dir),'--id','1000'])


if __name__=='__main__':unittest.main()
