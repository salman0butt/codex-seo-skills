"""Offline site comparison: exact matches, attestation, timestamps and secrecy."""
from __future__ import annotations

import contextlib
import copy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import site_audit_compare as compare
from site_audit_report import EvidenceError
from test_site_audit_report import source,page


def fixtures():
    before=source(
        page('/secret/URL-TOKEN', title='Before title', desc='Before description',
             findings=('missing-h1',)),
        page('/about',title='About',desc='Description'),
        page('/skip',title='Skip',desc='Skip description'))
    before['started_at_utc']='2026-10-22T11:00:00+00:00'
    for p in before['pages']:
        p['observed_at_utc']='2026-10-22T11:00:00+00:00'
    after=source(
        page('/about',title='ABOUT',desc='Description'),
        page('/secret/URL-TOKEN',title='After title',desc='After description',
             findings=('noindex-review',)),
        page('/new',title='New',desc='New description'))
    after['started_at_utc']='2026-10-24T11:00:00+00:00'
    for p in after['pages']:
        p['observed_at_utc']='2026-10-24T11:00:00+00:00'
    for doc in (before,after):
        doc['query-token']='SUPER-SECRET-PRIVATE-HTML-CONTENT'
    return before,after


class SiteBeforeAfterTests(unittest.TestCase):
    def setUp(self):
        self.before,self.after=fixtures()
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def result(self,attested=False):
        return compare.compare(self.before,self.after,confirm_same_site=attested)

    def test_no_identity_attestation_suppresses_all_diff_and_page_identity(self):
        r=self.result()
        self.assertEqual(r['comparison_status'],'same_site_not_attested')
        self.assertEqual(r['matched_pages'],0)
        self.assertEqual(r['compared_pages'],0)
        self.assertEqual(r['changes'],[])
        self.assertEqual(r['pages_only_in_before'],[])
        self.assertEqual(r['pages_only_in_after'],[])
        self.assertEqual(r['network_requests'],0)
        self.assertFalse(r['site_changes_made'])

    def test_reordered_exact_urls_compared_without_exposing_any_path(self):
        r=self.result(True)
        self.assertEqual(r['comparison_status'],'matched_evaluated_pages_only')
        self.assertEqual(r['matched_pages'],2)
        self.assertEqual(r['compared_pages'],2)
        self.assertEqual(r['pages_only_in_before'],['page-3'])
        self.assertEqual(r['pages_only_in_after'],['page-3'])
        self.assertEqual(len(r['changes']),1)
        change=r['changes'][0]
        self.assertEqual(change['before_reference'],'page-1')
        self.assertEqual(change['after_reference'],'page-2')
        self.assertEqual(change['newly_observed_findings'],['noindex-review'])
        self.assertEqual(change['findings_no_longer_observed'],['missing-h1'])
        self.assertEqual(change['changed_metadata_fields'],['title','description'])
        self.assertFalse(change['change_authorized'])
        self.assertIn('not_proof_of_fix',change['interpretation'])
        data=json.dumps(r)+compare.markdown_report(r)
        for token in ('URL-TOKEN','SUPER-SECRET','Before title','After description',
                      '/about','/skip','/new','https://example.com'):
            self.assertNotIn(token,data)

    def test_metadata_case_whitespace_only_is_not_change(self):
        r=self.result(True)
        self.assertEqual(len(r['changes']),1)
        self.assertEqual(r['changes'][0]['after_reference'],'page-2')

    def test_source_origins_must_match_even_with_attestation(self):
        self.after['origin']='https://another.example/'
        self.after['seed']='https://another.example/'
        for p in self.after['pages']:
            p['url']=p['url'].replace('example.com','another.example')
        r=self.result(True)
        self.assertEqual(r['comparison_status'],'different_origins')
        self.assertEqual(r['changes'],[])
        self.assertEqual(r['matched_pages'],0)

    def test_after_scan_must_be_later(self):
        self.after['started_at_utc']='2026-10-22T11:00:00+00:00'
        r=self.result(True)
        self.assertEqual(r['comparison_status'],'non_newer_after_snapshot')
        self.assertEqual(r['changes'],[])

    def test_identical_or_older_page_observation_is_suppressed(self):
        self.after['pages'][1]['observed_at_utc']=self.before['pages'][0]['observed_at_utc']
        r=self.result(True)
        self.assertEqual(r['matched_pages'],2)
        self.assertEqual(r['compared_pages'],1)
        self.assertEqual(r['changes'],[])
        self.assertEqual(r['suppressed_page_comparisons'],[{
            'before_reference':'page-1','after_reference':'page-2',
            'reason':'non_newer_page_observation'}])

    def test_no_matching_pages_is_not_a_successful_comparison(self):
        for index, p in enumerate(self.after['pages']):
            p['url']='https://example.com/entirely-new-'+str(index)
        r=self.result(True)
        self.assertEqual(r['comparison_status'],'no_eligible_page_comparisons')
        self.assertEqual(r['matched_pages'],0)
        self.assertEqual(r['compared_pages'],0)
        self.assertFalse(r['changes'])

    def test_all_matching_pages_are_unevaluated_is_not_a_successful_comparison(self):
        for p in self.after['pages']:
            p.update({'http_status':503,'outcome':'not_evaluated','findings':[]})
        r=self.result(True)
        self.assertEqual(r['comparison_status'],'no_eligible_page_comparisons')
        self.assertEqual(r['compared_pages'],0)

    def test_not_evaluated_page_cannot_establish_disappearance_or_fix(self):
        self.after['pages'][1]={'url':'https://example.com/secret/URL-TOKEN',
                                'http_status':503,'outcome':'not_evaluated','findings':[]}
        r=self.result(True)
        self.assertEqual(r['compared_pages'],1)
        self.assertEqual(r['changes'],[])
        self.assertEqual(r['suppressed_page_comparisons'][0]['reason'],
                         'not_both_evaluated_as_html')

    def test_partial_after_source_remains_partial_comparison(self):
        self.after['outcome']='partial'
        self.after['stop_reason']='HTTP 429; stopped rather than retrying'
        r=self.result(True)
        self.assertEqual(r['comparison_status'],'partial_sample_comparison')
        self.assertEqual(r['after']['source_outcome'],'partial')
        self.assertEqual(len(r['changes']),1)

    def test_sample_removal_not_treated_as_removed_page(self):
        self.after['pages']=self.after['pages'][:2]
        r=self.result(True)
        self.assertEqual(r['pages_only_in_before'],['page-3'])
        self.assertEqual(r['pages_only_in_after'],[])
        self.assertIn('does not prove it was removed',json.dumps(r))

    def test_untrusted_status_or_page_findings_rejected_without_raw_echo(self):
        self.after['pages'][0]['findings']=[{'id':'<script>SUPER-SECRET</script>'}]
        with self.assertRaises(EvidenceError) as err:
            self.result(True)
        self.assertNotIn('SUPER-SECRET',str(err.exception))

    def test_raw_paths_and_descriptions_never_appear_even_if_changed(self):
        self.before['pages'][0]['observations']['title']='SECRET-A'*10
        self.after['pages'][1]['observations']['title']='SECRET-B'*10
        r=self.result(True)
        self.assertNotIn('SECRET-A',json.dumps(r))
        self.assertNotIn('SECRET-B',compare.markdown_report(r))

    def test_timestamp_offsets_compare_by_real_instant(self):
        self.after['started_at_utc']='2026-10-22T09:00:00-02:00' # same time
        r=self.result(True)
        self.assertEqual(r['comparison_status'],'non_newer_after_snapshot')

    def test_malformed_file_fails_privately(self):
        earlier=self.root/'before-TOKEN.json'
        later=self.root/'after-SECRET.json'
        earlier.write_text(json.dumps(self.before))
        later.write_text('not JSON SUPER-SECRET')
        stderr=io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc=compare.main(['--before',str(earlier),'--after',str(later),'--confirm-same-site'])
        self.assertEqual(rc,2)
        self.assertNotIn('SECRET',stderr.getvalue())
        self.assertIn('network_requests',stderr.getvalue())

    def test_main_no_attestation_is_nonzero_and_has_zero_network(self):
        earlier=self.root/'before.json';later=self.root/'after.json'
        earlier.write_text(json.dumps(self.before));later.write_text(json.dumps(self.after))
        out=io.StringIO()
        with patch('socket.create_connection',side_effect=AssertionError('unexpected network')), \
             contextlib.redirect_stdout(out):
            rc=compare.main(['--before',str(earlier),'--after',str(later),'--format','json'])
        self.assertEqual(rc,2)
        doc=json.loads(out.getvalue())
        self.assertEqual(doc['network_requests'],0)
        self.assertEqual(doc['comparison_status'],'same_site_not_attested')

    def test_main_confirmed_emits_valid_no_write_json(self):
        earlier=self.root/'before.json';later=self.root/'after.json'
        earlier.write_text(json.dumps(self.before));later.write_text(json.dumps(self.after))
        original=earlier.read_bytes(),later.read_bytes()
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            rc=compare.main(['--before',str(earlier),'--after',str(later),
                             '--confirm-same-site','--format','json'])
        self.assertEqual(rc,0)
        self.assertEqual(json.loads(out.getvalue())['compared_pages'],2)
        self.assertEqual((earlier.read_bytes(),later.read_bytes()),original)
        self.assertEqual(set(p.name for p in self.root.iterdir()),{'before.json','after.json'})

    def test_source_with_multiple_scans_different_origins_fails(self):
        self.before['pages'][1]['url']='https://other.example/about'
        with self.assertRaises(EvidenceError):self.result(True)

    def test_exact_url_match_without_finding_changes_does_not_certify_health(self):
        self.after=copy.deepcopy(self.before)
        self.after['started_at_utc']='2026-10-24T12:00:00+00:00'
        for p in self.after['pages']:p['observed_at_utc']='2026-10-24T12:00:00+00:00'
        r=self.result(True)
        self.assertEqual(r['compared_pages'],3)
        self.assertEqual(r['changes'],[])
        self.assertIn('not evidence that the site is unchanged or healthy',compare.markdown_report(r))


if __name__=='__main__':unittest.main()
