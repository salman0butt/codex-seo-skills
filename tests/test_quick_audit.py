"""Source-only quick audit contracts: bounded output, honest findings and secrets."""
from __future__ import annotations
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('quick_audit',ROOT/'scripts/quick_audit.py')
assert SPEC and SPEC.loader
quick=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quick)


def sample(**overrides):
    defaults={'title':'Example Studio - Home','meta_description':'A local business offering website design.',
              'canonical':'https://example.com/', 'meta_robots':'max-image-preview:large',
              'h1':['Welcome'],'images':[{'alt':'A website preview'}, {'alt':''}],
              'schema':[{'@type':'Organization'}, {'@type':['WebPage','BreadcrumbList']}],
              'links':{'internal':[{'href':'https://example.com/about'}],'external':[]},
              'word_count':50}
    defaults.update(overrides)
    return defaults


class QuickAuditTests(unittest.TestCase):
    def test_grounded_no_score_no_ranking_claim(self):
        data=quick.analyze_page('https://example.com/?secret=123',sample(),measured_at='2026-10-22T08:00:00+00:00')
        self.assertEqual(data['url'],'https://example.com/')
        self.assertEqual(data['http_status'],200)
        self.assertIsNone(data['seo_score'])
        self.assertEqual(data['findings'],[])
        self.assertEqual(data['observations']['schema_types'],['BreadcrumbList','Organization','WebPage'])
        self.assertTrue(any('CrUX' in v for v in data['not_measured']))
        self.assertNotIn('secret=123',json.dumps(data))

    def test_title_h1_description_noindex_and_alt_are_evidence_based(self):
        data=quick.analyze_page('https://example.com/',sample(
            title=None,meta_description=None,canonical=None,h1=[],
            images=[{'alt':None},{'alt':''}],meta_robots='noindex, follow'))
        types={f['id']:f for f in data['findings']}
        self.assertEqual(set(types),{'missing-title','missing-meta-description','missing-h1',
                                     'image-alt-missing','noindex-review','canonical-review'})
        self.assertEqual(types['image-alt-missing']['priority'],'review')
        self.assertEqual(data['observations']['image_alt_attribute_missing'],1)

    def test_markdown_contains_scope_and_known_limitations(self):
        data=quick.analyze_page('https://example.com/',sample())
        report=quick.markdown_report(data)
        self.assertIn('single-page-raw-html',report)
        self.assertIn('Not measured',report)
        self.assertIn('No search ranking outcome',report)

    def test_public_url_redacts_credentials_query_and_fragments(self):
        self.assertEqual(quick.public_url('https://alice:pass@example.com:443/private?a=secret#token'),
                         'https://example.com:443/private')
        self.assertEqual(quick.public_url('https://[::1]/admin?token=x'), 'https://[::1]/admin')
        self.assertEqual(quick.public_url('https://example.com:bad'), '[invalid URL]')

    def test_blocked_fetch_has_no_misleading_findings(self):
        with patch.object(quick,'fetch_html',return_value={
            'url':'https://example.com/', 'status_code':None,
            'content':None,'error':'Resource is not HTML'}):
            data=quick.run('https://example.com/')
        self.assertEqual(data['outcome'],'blocked')
        self.assertEqual(data['findings'],[])
        self.assertIsNone(data['seo_score'])

    def test_cli_fails_on_invalid_byte_budget(self):
        with patch.object(sys,'argv',['quick_audit.py','https://example.com','--max-bytes','3000000']):
            with self.assertRaises(SystemExit) as err:
                quick.main()
        self.assertEqual(err.exception.code,2)


if __name__=='__main__': unittest.main()
