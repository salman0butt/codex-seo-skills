"""Offline quality gates and advisory alerts without private-provider calls."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import seo_evidence_alerts as watcher
import seo_history as history
from seo_report_builder import compose
from test_seo_report_builder import provider,quick

AS_OF=date(2026,10,23)


def gsc(start,end,clicks=100,impressions=1000):
    return provider(start=start,end=end,metrics={'clicks':clicks,'impressions':impressions,
                 'ctr_percent':round(clicks/impressions*100,2),'average_position':10.0})


def report(provider_data=None,issue_ids=(),page_timestamp='2026-10-22T12:00:00+00:00'):
    if provider_data is None:provider_data=gsc('2026-09-22','2026-10-19')
    q=quick(*issue_ids)
    q['observed_at_utc']=page_timestamp
    return compose({'gsc_current':provider_data,'quick_audits':[q]})


class OfflineAlertsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)/'history'
        self.db=history._location(self.folder,create=True)
        self.previous=report(gsc('2026-08-25','2026-09-21'),issue_ids=('missing-meta-description',),
                             page_timestamp='2026-10-20T12:00:00+00:00')
        self.current=report(gsc('2026-09-22','2026-10-19',clicks=40),
                            issue_ids=('missing-meta-description','missing-title'))

    def insert(self,payload):
        result=history._record(self.db,payload,same_property=False,same_page_set=False)
        return result['snapshot']['id']

    def evaluate(self,**kwargs):
        a,b=watcher._load_two(self.folder)
        return watcher.evaluate(a,b,as_of=kwargs.pop('as_of',AS_OF),**kwargs)

    def test_single_snapshot_never_generates_change_alert(self):
        self.insert(self.current)
        result=self.evaluate(confirm_history_same_property=True,confirm_same_page_set=True)
        self.assertEqual(result['alerts'],[])
        self.assertEqual(result['suppressed_comparisons'][0]['reason'],'no_previous_provider_data')
        self.assertEqual(result['network_requests'],0)

    def test_unattested_provider_comparison_is_suppressed(self):
        self.insert(self.previous);self.insert(self.current)
        result=self.evaluate()
        self.assertEqual(result['alerts'],[])
        self.assertIn('same_property_not_attested',[x['reason'] for x in result['suppressed_comparisons']])
        self.assertIn('same_page_set_not_attested',[x['reason'] for x in result['suppressed_comparisons']])

    def test_attested_large_count_drop_flags_advisory_once(self):
        self.insert(self.previous);self.insert(self.current)
        output=self.evaluate(confirm_history_same_property=True)
        self.assertEqual(len(output['alerts']),1)
        alert=output['alerts'][0]
        self.assertEqual(alert['kind'],'aggregate_count_drop')
        self.assertEqual(alert['relative_drop_percent'],60)
        self.assertEqual(alert['absolute_drop'],60)
        self.assertEqual(alert['severity'],'review')
        self.assertNotIn('example.com',json.dumps(output))
        self.assertEqual(alert['id'],self.evaluate(confirm_history_same_property=True)['alerts'][0]['id'])
        self.assertFalse(output['history_modified'])
        self.assertEqual(output['notifications_sent'],0)

    def test_threshold_and_small_sample_suppression(self):
        self.insert(self.previous);self.insert(self.current)
        self.assertEqual(self.evaluate(confirm_history_same_property=True,min_baseline=101)['alerts'],[])
        self.assertEqual(self.evaluate(confirm_history_same_property=True,min_absolute_drop=61)['alerts'],[])
        self.assertEqual(self.evaluate(confirm_history_same_property=True,drop_percent=61)['alerts'],[])

    def test_ga4_sessions_drop_only_with_matching_property(self):
        old=provider('ga4',start='2026-08-25',end='2026-09-21',
            metrics={'organic_search_sessions':100,'organic_search_total_users':90,
                     'organic_search_engaged_sessions':80})
        new=provider('ga4',start='2026-09-22',end='2026-10-19',
            metrics={'organic_search_sessions':50,'organic_search_total_users':45,
                     'organic_search_engaged_sessions':40})
        self.insert(compose({'ga4_current':old}))
        self.insert(compose({'ga4_current':new}))
        self.assertEqual(self.evaluate()['alerts'],[])
        accepted=self.evaluate(confirm_history_same_property=True)
        self.assertEqual(len(accepted['alerts']),1)
        self.assertEqual(accepted['alerts'][0]['metric'],'organic_search_sessions')
        self.assertEqual(accepted['alerts'][0]['relative_drop_percent'],50)
        self.assertIn('100 → 50',watcher._markdown(accepted))

    def test_completely_unavailable_provider_requires_review_not_alert(self):
        self.insert(self.previous)
        missing=provider(result='rate_limited',metrics={},live_verified=False,date_range=None,http_status=429)
        self.insert(report(missing))
        result=self.evaluate(confirm_history_same_property=True)
        self.assertEqual(result['alerts'],[])
        self.assertEqual(result['quality_findings'][0]['code'],'provider_unavailable')

    def test_stale_current_report_prevents_count_alert(self):
        self.insert(self.previous);self.insert(self.current)
        output=self.evaluate(confirm_history_same_property=True,max_age_days=2)
        self.assertFalse(output['alerts'])
        self.assertEqual(output['quality_findings'][0]['code'],'stale_window')
        self.assertEqual(output['suppressed_comparisons'][0]['reason'],'current_evidence_unavailable_or_stale')

    def test_no_data_is_not_measured_zero(self):
        self.insert(self.previous)
        missing=provider(start='2026-09-22',end='2026-10-19',result='no_data',
                         metrics={},live_verified=False)
        self.insert(report(missing))
        output=self.evaluate(confirm_history_same_property=True)
        self.assertEqual(output['alerts'],[])
        self.assertEqual(output['quality_findings'][0]['code'],'no_data')
        self.assertEqual(output['suppressed_comparisons'][0]['reason'],'current_evidence_unavailable_or_stale')

    def test_nonadjacent_reporting_windows_do_not_trigger(self):
        self.insert(self.previous)
        self.insert(report(gsc('2026-09-25','2026-10-22',clicks=10)))
        output=self.evaluate(confirm_history_same_property=True)
        self.assertFalse(output['alerts'])
        self.assertIn('nonadjacent_or_unequal_windows',[x['reason'] for x in output['suppressed_comparisons']])

    def test_attested_new_important_html_finding(self):
        self.insert(self.previous);self.insert(self.current)
        output=self.evaluate(confirm_same_page_set=True)
        self.assertEqual(len(output['alerts']),1)
        entry=output['alerts'][0]
        self.assertEqual((entry['kind'],entry['issue_id']),('new_static_page_finding','missing-title'))
        self.assertIn('verify',entry['note'])
        self.assertNotIn('page/',json.dumps(output))
        self.assertNotIn('token-ABC123',json.dumps(output))

    def test_non_newer_or_different_page_set_is_suppressed(self):
        self.insert(self.previous)
        prior_timestamp=self.previous['page_audits'][0]['observed_at_utc']
        self.current['page_audits'][0]['observed_at_utc']=prior_timestamp
        self.insert(self.current)
        output=self.evaluate(confirm_same_page_set=True)
        self.assertEqual(output['alerts'],[])
        self.assertIn('non_newer_audit_timestamp',[x['reason'] for x in output['suppressed_comparisons']])

    def test_stale_page_audit_does_not_trigger_new_finding(self):
        self.insert(self.previous)
        self.current['page_audits'][0]['observed_at_utc']='2026-10-21T12:00:00+00:00'
        self.insert(self.current)
        output=self.evaluate(confirm_same_page_set=True,max_age_days=1)
        self.assertFalse(output['alerts'])
        self.assertIn('stale_page_audit',[x['code'] for x in output['quality_findings']])
        self.assertIn('page_evidence_unavailable_or_stale',[x['reason'] for x in output['suppressed_comparisons']])

    def test_invalid_stored_report_is_rejected(self):
        self.insert(self.previous)
        bad=json.loads(json.dumps(self.current))
        bad['provider_reports']['gsc']['current']['metrics']['clicks']=True
        with self.assertRaises(watcher.ReportInputError):watcher._normalized_report(bad)
        bad=json.loads(json.dumps(self.current));bad['network_requests']=1
        with self.assertRaises(watcher.ReportInputError):watcher._normalized_report(bad)
        bad=json.loads(json.dumps(self.current));bad['page_audits'][0]['finding_ids']=['invented_seo_score']
        with self.assertRaises(watcher.ReportInputError):watcher._normalized_report(bad)

    def test_future_date_quality_issue(self):
        self.insert(self.previous);self.insert(self.current)
        out=self.evaluate(as_of=date(2026,10,15),confirm_history_same_property=True)
        self.assertEqual(out['quality_findings'][0]['code'],'future_window')
        self.assertEqual(out['alerts'],[])

    def test_read_only_history_checks_and_no_network(self):
        self.insert(self.previous);self.insert(self.current)
        before=self.db.read_bytes()
        with patch('socket.create_connection',side_effect=AssertionError('Unexpected network')):
            result=self.evaluate(confirm_history_same_property=True)
        self.assertEqual(self.db.read_bytes(),before)
        self.assertEqual(result['network_requests'],0)
        self.assertEqual(result['notifications_sent'],0)

    def test_cli_is_read_only_and_md_is_text(self):
        self.insert(self.previous);self.insert(self.current)
        from contextlib import redirect_stdout
        import io
        with redirect_stdout(io.StringIO()) as buf:
            rc=watcher.main(['--history-dir',str(self.folder),'--confirm-history-same-property','--as-of','2026-10-23'])
        self.assertEqual(rc,0)
        parsed=json.loads(buf.getvalue())
        self.assertEqual(len(parsed['alerts']),1)
        with redirect_stdout(io.StringIO()) as buf:
            rc=watcher.main(['--history-dir',str(self.folder),'--format','markdown','--as-of','2026-10-23'])
        self.assertEqual(rc,0)
        self.assertIn('Offline SEO evidence quality',buf.getvalue())

    def test_invalid_thresholds_fail_closed(self):
        self.insert(self.current)
        for overrides in ({'drop_percent':float('nan')},{'drop_percent':float('inf')},{'min_baseline':False},
                          {'max_age_days':0},{'min_absolute_drop':0}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(watcher.ReportInputError):
                    self.evaluate(**overrides)

    def test_no_history_does_not_create_database(self):
        empty=Path(self.tmp.name)/'empty'
        with self.assertRaises(watcher.ReportInputError):watcher._load_two(empty)
        self.assertFalse(empty.exists())


if __name__=='__main__':unittest.main()
