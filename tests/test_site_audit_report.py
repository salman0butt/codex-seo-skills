"""Cross-page offline handoff, privacy and source-shape consistency tests."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import site_audit_report as report


def page(path, title='Example page', desc='Example description', findings=()):
    return {'schema_version':1,'scope':'single-page-raw-html',
        'outcome':'observations-only; no SEO rankings or indexation claim',
        'seo_score':None,'url':'https://example.com'+path,'http_status':200,
        'observed_at_utc':'2026-10-24T12:00:00+00:00',
        'observations':{'title':title,'meta_description':desc,
                        'canonical':'https://example.com'+path},
        'findings':[{'id':f,'evidence':'SECRET-EVIDENCE',
                     'recommendation':'<script>EXFILTRATE</script>'} for f in findings]}


def source(*pages):
    return {'schema_version':1,'scope':'bounded-same-origin-static-html-crawl',
        'started_at_utc':'2026-10-24T12:00:00+00:00',
        'origin':'https://example.com/','seed':'https://example.com/',
        'page_limit':max(1,len(pages)),'network_requests':len(pages)+1,
        'pages':list(pages),'robots_status':'checked_and_seed_allowed',
        'stop_reason':'discovery_queue_empty','outcome':'observations_only',
        'seo_score':None,'arbitrary_hostile_html':'<script>LEAK-UNTRUSTED</script>',
        'private_source':'SECRET-PRIVATE-URL-TOKEN'}


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.sample=source(page('/',title='My title',desc='Same description'),
            page('/hidden/token-SECRET-STRING',title=' MY  TITLE ',desc='same description'),
            page('/third',title=None,desc=None,findings=('missing-title','missing-meta-description','missing-h1')))

    def test_shared_metadata_and_validated_findings(self):
        result=report.build_report(self.sample)
        self.assertEqual(result['network_requests'],0)
        self.assertEqual(result['site_changes_made'],0)
        self.assertEqual(result['pages_evaluated'],3)
        self.assertEqual(result['finding_counts']['shared-title-review'],1)
        self.assertEqual(result['finding_counts']['shared-description-review'],1)
        self.assertEqual(result['finding_counts']['missing-title'],1)
        self.assertEqual(result['finding_counts']['missing-h1'],1)
        cross=[x for x in result['handoff_tasks'] if x['issue_id']=='shared-title-review'][0]
        self.assertEqual(cross['page_references'],['page-1','page-2'])
        self.assertFalse(cross['change_authorized'])
        self.assertEqual(result['handoff_tasks'][0]['priority'],'high')
        self.assertEqual(result['source_authenticity'],'unverified_saved_JSON')

    def test_no_input_paths_titles_descriptions_or_untrusted_html_in_any_output(self):
        result=report.build_report(self.sample)
        outputs=(json.dumps(result), report.markdown_report(result))
        for output in outputs:
            for secret in ('SECRET','My title','Same description','LEAK-UNTRUSTED',
                           'EXFILTRATE','/hidden/token-','https://example.com/third'):
                self.assertNotIn(secret,output)
        self.assertFalse(result['page_paths_included'])
        self.assertFalse(result['titles_or_descriptions_included'])

    def test_empty_findings_never_certify_site_health(self):
        data=source(page('/'))
        result=report.build_report(data)
        self.assertEqual(result['handoff_tasks'],[])
        self.assertEqual(result['finding_counts'],{})
        self.assertIn('NOT evidence of SEO health',report.markdown_report(result))

    def test_unevaluated_page_does_not_count_as_clean(self):
        denied={'url':'https://example.com/private','http_status':403,
                'outcome':'not_evaluated','findings':[]}
        data=source(page('/'),denied)
        result=report.build_report(data)
        self.assertEqual(result['pages_not_evaluated'],1)
        self.assertEqual(result['pages_evaluated'],1)
        self.assertEqual(result['pages_recorded'],2)

    def test_partial_source_never_promoted_to_completed(self):
        data=source(page('/'))
        data['outcome']='partial';data['stop_reason']='HTTP 429; stopped rather than retrying'
        result=report.build_report(data)
        self.assertEqual(result['source_outcome'],'partial')
        self.assertIn('(partial)',report.markdown_report(result))

    def test_blocked_and_missing_robots_sources_rejected(self):
        for override in ({'outcome':'blocked'}, {'robots_status':'not_checked'},
                         {'scope':'private-crawl'}, {'seo_score':100},
                         {'page_limit':100}, {'network_requests':False}):
            with self.subTest(override=override):
                obj=copy.deepcopy(self.sample);obj.update(override)
                with self.assertRaises(report.EvidenceError):report.build_report(obj)

    def test_invalid_or_private_origin_and_cross_origin_pages_rejected(self):
        for original in ('https://evil.com/','https://alice:pass@example.com/',
                         'https://example.com/path','https://example.com/?q=secret',
                         'file:///etc/passwd'):
            with self.subTest(origin=original):
                doc=copy.deepcopy(self.sample);doc['origin']=original
                with self.assertRaises(report.EvidenceError):report.build_report(doc)
        for bad_page in ('https://evil.com/path','http://example.com/','https://example.com/b?secret=1',
                         'https://example.com/#fragment'):
            with self.subTest(page=bad_page):
                doc=copy.deepcopy(self.sample);doc['pages'][1]['url']=bad_page
                with self.assertRaises(report.EvidenceError):report.build_report(doc)

    def test_duplicated_page_identity_fails(self):
        doc=copy.deepcopy(self.sample)
        doc['pages'][1]['url']=doc['pages'][0]['url']
        with self.assertRaisesRegex(report.EvidenceError,'duplicate'):
            report.build_report(doc)

    def test_mutated_metrics_types_and_invalid_findings_rejected(self):
        for val in (True,-1,999,1.2):
            doc=copy.deepcopy(self.sample);doc['pages'][0]['http_status']=val
            with self.subTest(value=val),self.assertRaises(report.EvidenceError):report.build_report(doc)
        doc=copy.deepcopy(self.sample)
        doc['pages'][0]['findings']=[{'id':'<script>alert(1)</script>'}]
        with self.assertRaises(report.EvidenceError):report.build_report(doc)

    def test_observation_consistency_rejects_forged_missing_title_and_description(self):
        doc=copy.deepcopy(self.sample)
        doc['pages'][0]['observations']['title']=None
        with self.assertRaisesRegex(report.EvidenceError,'Contradictory'):
            report.build_report(doc)
        doc=copy.deepcopy(self.sample)
        doc['pages'][2]['observations']['meta_description']='Now filled'
        with self.assertRaises(report.EvidenceError):report.build_report(doc)

    def test_input_file_bounded_no_network_or_file_write(self):
        location=self.folder/'saved-site.json'
        location.write_text(json.dumps(self.sample))
        with patch('socket.create_connection',side_effect=AssertionError('unexpected network')):
            report.build_report(report.read_source(location))
        before=location.read_bytes()
        stdout=io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result=report.main(['--site-audit',str(location),'--format','json'])
        self.assertEqual(result,0)
        parsed=json.loads(stdout.getvalue())
        self.assertEqual(parsed['network_requests'],0)
        self.assertEqual(location.read_bytes(),before)
        self.assertEqual(list(self.folder.iterdir()),[location])

    def test_bad_file_error_does_not_disclose_secret_location_or_contents(self):
        location=self.folder/'TOKEN-WITH-SECRET.json'
        location.write_text('SECRET-FILE-DATA not valid JSON')
        stderr=io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc=report.main(['--site-audit',str(location),'--format','json'])
        self.assertEqual(rc,2)
        self.assertNotIn('SECRET',stderr.getvalue())
        self.assertEqual(json.loads(stderr.getvalue())['network_requests'],0)
        location.write_bytes(b'{' + b'A'*300000)
        with self.assertRaises(report.EvidenceError):report.read_source(location)

    def test_long_html_values_malformed_timestamps_and_extra_pages_fails(self):
        bad=copy.deepcopy(self.sample);bad['pages'][0]['observations']['title']='X'*181
        with self.assertRaises(report.EvidenceError):report.build_report(bad)
        bad=copy.deepcopy(self.sample);bad['pages'][0]['observed_at_utc']='yesterday'
        with self.assertRaises(report.EvidenceError):report.build_report(bad)
        bad=copy.deepcopy(self.sample);bad['pages']=bad['pages']*5;bad['page_limit']=12
        with self.assertRaises(report.EvidenceError):report.build_report(bad)

    def test_current_page_count_not_comparable_with_source_page_budget(self):
        doc=copy.deepcopy(self.sample)
        doc['network_requests']=2
        with self.assertRaises(report.EvidenceError):report.build_report(doc)

    def test_cross_page_shared_fields_require_at_least_two_evaluated_pages(self):
        doc=source(page('/a',title='same'),{
            'url':'https://example.com/blocked','http_status':503,
            'outcome':'not_evaluated','findings':[]})
        out=report.build_report(doc)
        self.assertNotIn('shared-title-review',out['finding_counts'])

    def test_source_is_never_promoted_to_authenticated_measurement(self):
        doc=source(page('/'))
        doc['live_verified']=True
        out=report.build_report(doc)
        self.assertEqual(out['source_authenticity'],'unverified_saved_JSON')
        self.assertEqual(out['notifications_sent'],0)


if __name__=='__main__':unittest.main()
