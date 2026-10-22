"""Offline evidence report builder: provenance, dates, secrets, handoffs and CLI."""
from __future__ import annotations
import contextlib
import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('seo_report_builder',ROOT/'scripts/seo_report_builder.py')
assert SPEC and SPEC.loader
mod=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def provider(service='gsc',start='2026-09-22',end='2026-10-19',**changes):
    metrics=({'clicks':40,'impressions':800,'ctr_percent':5.0,'average_position':12.5}
             if service=='gsc' else {'organic_search_sessions':100,
                                     'organic_search_total_users':80,
                                     'organic_search_engaged_sessions':60})
    p={'schema_version':1,'service':service,'scope':'aggregate-only','read_only':True,
       'network_requests':1,'live_verified':True,'result':'verified',
       'http_status':200,'metrics':metrics,
       'date_range':{'start':start,'end':end,'days':(date.fromisoformat(end)-date.fromisoformat(start)).days+1},
       'property_identifier_redacted':True,
       'property':'SECRET-DOMAIN-HIDDEN',
       'private_raw_payload':{'secret':'DO-NOT-COPY'}}
    p.update(changes)
    return p


def quick(*finding_ids):
    return {'schema_version':1,'scope':'single-page-raw-html',
            'http_status':200,'url':'https://example.com/page/token-ABC123',
            'observed_at_utc':'2026-10-22T12:00:00+00:00',
            'outcome':'observations-only; no SEO rankings or indexation claim',
            'title':'SECRET TITLE NOT COPIED',
            'findings':[{'id':issue,'evidence':'SECRET-EVIDENCE-NOT-COPIED',
                         'recommendation':'<script>alert("BAD")</script>'} for issue in finding_ids]}


class ReportBuilderContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_current_gsc_aggregate_no_spurious_comparison(self):
        r=mod.compose({'gsc_current':provider()})
        entry=r['provider_reports']['gsc']
        self.assertEqual(entry['current']['metrics']['clicks'],40)
        self.assertEqual(entry['comparison']['status'],'no_previous_report')
        self.assertEqual(r['network_requests'],0)
        self.assertNotIn('SECRET',json.dumps(r))
        self.assertFalse(r['private_property_identifiers_included'])

    def test_current_ga4_report_kept_distinct_from_gsc(self):
        r=mod.compose({'gsc_current':provider(), 'ga4_current':provider('ga4')})
        self.assertEqual(r['provider_reports']['ga4']['current']['metrics']['organic_search_total_users'],80)
        self.assertNotIn('total',r)
        self.assertNotIn('SECRET',mod._markdown(r))
        self.assertIn('GSC web search clicks and GA4 organic sessions are different',json.dumps(r))

    def test_adjacent_equal_period_requires_same_property_attestation(self):
        current=provider()
        previous=provider(start='2026-08-25',end='2026-09-21',metrics={'clicks':20,'impressions':1000,'ctr_percent':2.0,'average_position':16.5})
        indata={'gsc_current':current,'gsc_previous':previous}
        no=mod.compose(indata)
        self.assertEqual(no['provider_reports']['gsc']['comparison']['status'],'property_identity_not_attested')
        self.assertEqual(no['provider_reports']['gsc']['comparison']['metrics'],{})
        yes=mod.compose(indata,confirm_same_property=True)
        cmp=yes['provider_reports']['gsc']['comparison']
        self.assertEqual(cmp['status'],'compared_with_operator_attestation')
        self.assertEqual(cmp['metrics']['clicks']['absolute_change'],20)
        self.assertEqual(cmp['metrics']['clicks']['relative_change_percent'],100)
        self.assertEqual(cmp['metrics']['ctr_percent']['absolute_change'],3)
        self.assertEqual(cmp['metrics']['ctr_percent']['units'],'percentage_points')
        self.assertIsNone(cmp['metrics']['average_position']['relative_change_percent'])
        self.assertIn('not_rank_causality',cmp['metrics']['average_position']['interpretation'])

    def test_zero_baseline_is_undefined_relative_change(self):
        prev=provider(start='2026-08-25',end='2026-09-21',metrics={'clicks':0,'impressions':0,'ctr_percent':0,'average_position':0})
        c=mod.compose({'gsc_current':provider(),'gsc_previous':prev},confirm_same_property=True)
        cmp=c['provider_reports']['gsc']['comparison']['metrics']
        self.assertIsNone(cmp['clicks']['relative_change_percent'])
        self.assertEqual(cmp['clicks']['absolute_change'],40)
        self.assertNotIn('Infinity',json.dumps(c))

    def test_nonadjacent_or_unequal_periods_not_compared(self):
        cases=[provider(start='2026-08-01',end='2026-08-28'),
               provider(start='2026-09-01',end='2026-09-21')]
        for previous in cases:
            with self.subTest(previous=previous['date_range']):
                r=mod.compose({'gsc_current':provider(),'gsc_previous':previous},confirm_same_property=True)
                self.assertEqual(r['provider_reports']['gsc']['comparison']['status'],'nonadjacent_or_unequal_windows')
                self.assertEqual(r['provider_reports']['gsc']['comparison']['metrics'],{})

    def test_missing_or_unverified_data_is_not_zero(self):
        unavailable=provider(result='no_data',live_verified=False,metrics={})
        r=mod.compose({'gsc_current':unavailable})
        self.assertEqual(r['provider_reports']['gsc']['current']['status'],'no_data')
        self.assertEqual(r['provider_reports']['gsc']['current']['metrics'],{})
        self.assertIn('not establish zero',mod._markdown(r))

    def test_inconsistent_evidence_rejected(self):
        invalid=[provider(result='verified',live_verified=False),
                 provider(result='no_data',live_verified=True,metrics={}),
                 provider(result='rate_limited',live_verified=False),
                 provider(metrics={'clicks':True,'impressions':500,'ctr_percent':3,'average_position':9}),
                 provider(metrics={'clicks':20,'impressions':500,'ctr_percent':float('nan'),'average_position':9}),
                 provider(start='2026-10-19',end='2026-10-01'),
                 provider(schema_version=2),
                 provider(network_requests=0),provider(http_status=403),
                 provider(read_only=False),
                 provider(scope='site-crawl')]
        for idx,item in enumerate(invalid):
            with self.subTest(index=idx):
                with self.assertRaises(mod.ReportInputError):
                    mod.compose({'gsc_current':item})

    def test_no_previous_without_current(self):
        with self.assertRaises(mod.ReportInputError):
            mod.compose({'gsc_previous':provider()})

    def test_quick_audit_handoff_prioritized_without_untrusted_content(self):
        r=mod.compose({'quick_audits':[quick('image-alt-missing','missing-title','noindex-review','missing-title')]})
        self.assertEqual([x['issue_id'] for x in r['handoff_tasks']],
                         ['missing-title','image-alt-missing','noindex-review'])
        self.assertEqual(r['handoff_tasks'][0]['priority'],'high')
        self.assertEqual(r['page_audits'][0]['page_origin'],'https://example.com/')
        self.assertEqual(r['page_audits'][0]['audit_reference'],'audit-1')
        self.assertEqual(r['handoff_tasks'][0]['audit_reference'],'audit-1')
        self.assertTrue(all(x['change_authorized'] is False for x in r['handoff_tasks']))
        text=json.dumps(r)+mod._markdown(r)
        for secret in ('ABC123','SECRET TITLE','SECRET-EVIDENCE','<script>'):
            self.assertNotIn(secret,text)
        self.assertIn('path redacted',mod._markdown(r))

    def test_unrecognized_finding_is_not_promoted_to_handoff(self):
        with self.assertRaises(mod.ReportInputError):
            mod.compose({'quick_audits':[quick('made-up-seo-health-score')]})

    def test_rejects_untrusted_quick_audit_urls_and_status(self):
        for changes in [{'http_status':403}, {'url':'https://user:pass@example.com/?key=secret'},
                        {'url':'file:///etc/passwd'}, {'outcome':'blocked'}]:
            doc=quick('missing-title');doc.update(changes)
            with self.subTest(changes=changes):
                with self.assertRaises(mod.ReportInputError):
                    mod.compose({'quick_audits':[doc]})

    def test_unverified_provenance_is_explicit(self):
        r=mod.compose({'quick_audits':[quick()]})
        self.assertIn('not independently verified',r['source_validation'])
        self.assertEqual(r['handoff_tasks'],[])
        self.assertIn('does not certify SEO health',mod._markdown(r))

    def test_cannot_read_oversized_or_corrupt_input(self):
        p=self.root/'large.json';p.write_text('X'*(mod.MAX_INPUT_BYTES+1))
        with self.assertRaises(mod.ReportInputError):mod._read_json(p)
        p.write_text('{not-json:SECRET')
        with self.assertRaises(mod.ReportInputError) as ctx:mod._read_json(p)
        self.assertNotIn('SECRET',str(ctx.exception))

    def test_cli_json_and_markdown_and_private_permissions(self):
        source=self.root/'current.json';source.write_text(json.dumps(provider()))
        output=self.root/'out.md'
        stderr=io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc=mod.main(['--gsc-current',str(source),'--format','markdown','--output',str(output)])
        self.assertEqual(rc,0)
        self.assertIn('# Codex SEO evidence report',output.read_text())
        self.assertEqual(stat.S_IMODE(output.stat().st_mode),0o600)
        self.assertNotIn(str(source),stderr.getvalue())
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            rc=mod.main(['--gsc-current',str(source),'--format','json'])
        self.assertEqual(rc,0)
        self.assertEqual(json.loads(out.getvalue())['schema_version'],1)

    def test_cli_does_not_clobber_source_and_has_no_side_effects(self):
        source=self.root/'current.json';source.write_text(json.dumps(provider()))
        before=source.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            rc=mod.main(['--gsc-current',str(source),'--output',str(source)])
        self.assertEqual(rc,2)
        self.assertEqual(source.read_bytes(),before)
        self.assertFalse(list(self.root.glob('.seo-evidence-*')))

    def test_output_exists_requires_explicit_overwrite(self):
        source=self.root/'current.json';source.write_text(json.dumps(provider()))
        output=self.root/'summary.md';output.write_text('ORIGINAL')
        with contextlib.redirect_stderr(io.StringIO()):
            rc=mod.main(['--gsc-current',str(source),'--output',str(output)])
        self.assertEqual(rc,2)
        self.assertEqual(output.read_text(),'ORIGINAL')
        with contextlib.redirect_stderr(io.StringIO()):
            rc=mod.main(['--gsc-current',str(source),'--output',str(output),'--overwrite'])
        self.assertEqual(rc,0)
        self.assertIn('Codex SEO evidence report',output.read_text())

    def test_symlink_output_is_rejected(self):
        source=self.root/'current.json';source.write_text(json.dumps(provider()))
        target=self.root/'outside.txt';target.write_text('UNCHANGED')
        link=self.root/'linked.md';link.symlink_to(target)
        with contextlib.redirect_stderr(io.StringIO()):
            rc=mod.main(['--gsc-current',str(source),'--output',str(link),'--overwrite'])
        self.assertEqual(rc,2)
        self.assertEqual(target.read_text(),'UNCHANGED')

    def test_limit_quick_audits(self):
        with self.assertRaises(mod.ReportInputError):
            mod.compose({'quick_audits':[quick()]*11})


if __name__=='__main__':unittest.main()
