"""Google API live-connectivity contract tests use fully mocked HTTP and auth."""
from __future__ import annotations
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock,patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('live_integration_verify',ROOT/'scripts/live_integration_verify.py')
assert SPEC and SPEC.loader
verifier=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code=status
        self.body=body if body is not None else {}
        self.closed=False
    def iter_content(self,chunk_size=65536):
        yield json.dumps(self.body).encode()
    def close(self):self.closed=True


class LiveIntegrationContracts(unittest.TestCase):
    def setUp(self):
        self.clients=[]
        self.google=types.ModuleType('google_auth')
        self.google.get_api_key=MagicMock(return_value=None)
        self.url_safety=types.ModuleType('url_safety')
        self.url_safety.validate_url_strict=MagicMock(side_effect=lambda u:(u,('93.184.215.14',)))
        self.req=types.ModuleType('requests')
        self.req.get=MagicMock()
        self.req.post=MagicMock()
        self.patch_modules=patch.dict(sys.modules,{'requests':self.req,'google_auth':self.google,'url_safety':self.url_safety})
        self.patch_modules.start()
        self.addCleanup(self.patch_modules.stop)

    def test_default_no_network_is_protected(self):
        for service in ('pagespeed','crux','gsc','ga4'):
            with self.subTest(service=service):
                d=verifier.verify(service,target='https://example.com/',prop='sc-domain:example.com')
                self.assertEqual(d['result'],'explicit_opt_in_required')
                self.assertEqual(d['network_requests'],0)
        self.req.get.assert_not_called();self.req.post.assert_not_called()
        self.url_safety.validate_url_strict.assert_not_called()

    def test_page_path_is_not_echoed_in_output(self):
        resp=FakeResponse(429,{'error':{'message':'opaque'}})
        self.req.get.return_value=resp
        result=verifier.verify('pagespeed',target='https://example.com/private-token-ABC123/',live=True)
        self.assertEqual(result['target_url'],'https://example.com/')
        self.assertNotIn('private-token-ABC123',json.dumps(result))

    def test_private_account_requires_two_flags_and_property(self):
        for service in ('gsc','ga4'):
            d=verifier.verify(service,prop='123456789',live=True)
            self.assertEqual(d['result'],'account_access_not_authorized')
            d=verifier.verify(service,live=True,allow_account_read=True)
            self.assertEqual(d['result'],'property_required_or_invalid')
        self.req.get.assert_not_called()

    def test_public_pagespeed_live_valid_result(self):
        resp=FakeResponse(body={'analysisUTCTimestamp':'2026-10-22T00:00:00Z',
            'lighthouseResult':{'lighthouseVersion':'14.0.0','categories':{
                'seo':{'score':0.93},'performance':{'score':None},'accessibility':{'score':1.0}}}})
        self.req.get.return_value=resp
        data=verifier.verify('pagespeed',target='https://example.com/',live=True)
        self.assertEqual(data['result'],'verified')
        self.assertEqual(data['metrics']['lab_scores'],{'seo':93,'accessibility':100})
        self.assertEqual(data['network_requests'],1)
        self.assertTrue(data['live_verified'])
        self.assertTrue(resp.closed)
        self.assertEqual(self.req.get.call_args.args[0],verifier.GOOGLE_PSI)
        self.assertNotIn('key',self.req.get.call_args.kwargs['params'])

    def test_rate_limited_is_not_fake_score(self):
        resp=FakeResponse(429,{'error':{'message':'token: SUPER-SECRET-DO-NOT-PRINT'}})
        self.req.get.return_value=resp
        result=verifier.verify('pagespeed',target='https://example.com/',live=True)
        self.assertEqual(result['result'],'rate_limited')
        self.assertFalse(result['live_verified'])
        self.assertEqual(result['metrics'],{})
        self.assertNotIn('SUPER-SECRET',json.dumps(result))
        self.assertTrue(resp.closed)

    def test_explicit_key_selection_never_silently_degrades_to_anonymous(self):
        result=verifier.verify('pagespeed',target='https://example.com/',live=True,use_api_key=True)
        self.assertEqual(result['result'],'api_key_required')
        self.assertEqual(result['network_requests'],0)
        self.req.get.assert_not_called()

    def test_crux_requires_key_before_request(self):
        result=verifier.verify('crux',target='https://example.com',live=True)
        self.assertEqual(result['result'],'api_key_required')
        self.assertEqual(result['network_requests'],0)
        self.req.post.assert_not_called()

    def test_crux_empty_404_is_not_zero(self):
        self.google.get_api_key.return_value='SENSITIVE-API-KEY'
        resp=FakeResponse(404,{'error':{'message':'No CrUX data'}})
        self.req.post.return_value=resp
        result=verifier.verify('crux',target='https://example.com',live=True)
        self.assertEqual(result['result'],'field_data_unavailable')
        self.assertEqual(result['metrics'],{})
        self.assertNotIn('SENSITIVE',json.dumps(result))
        self.assertEqual(self.req.post.call_args.kwargs['headers']['X-Goog-Api-Key'],'SENSITIVE-API-KEY')

    def test_crux_valid_field_metric(self):
        self.google.get_api_key.return_value='SENSITIVE-API-KEY'
        resp=FakeResponse(body={'record':{'metrics':{
            'largest_contentful_paint':{'percentiles':{'p75':2200}},
            'interaction_to_next_paint':{'percentiles':{'p75':110}}}}})
        self.req.post.return_value=resp
        result=verifier.verify('crux',target='https://example.com',live=True)
        self.assertTrue(result['live_verified'])
        self.assertEqual(result['metrics']['field_p75']['largest_contentful_paint'],2200)

    def test_private_metadata_probe_gsc(self):
        resp=FakeResponse(body={'siteUrl':'sc-domain:example.com','permissionLevel':'siteOwner'})
        client=MagicMock();client.get.return_value=resp
        result=verifier.verify('gsc',prop='sc-domain:example.com',live=True,
                               allow_account_read=True,auth_factory=lambda service:client)
        self.assertTrue(result['live_verified'])
        self.assertEqual(result['metrics'],{'property_metadata_available':True})
        self.assertNotIn('siteOwner',json.dumps(result))
        self.assertIn('%3A',client.get.call_args.args[0])
        self.assertTrue(resp.closed)

    def test_private_metadata_probe_ga4(self):
        resp=FakeResponse(body={'name':'properties/123456789/metadata'})
        client=MagicMock();client.get.return_value=resp
        result=verifier.verify('ga4',prop='properties/123456789',live=True,
                               allow_account_read=True,auth_factory=lambda service:client)
        self.assertTrue(result['live_verified'])
        self.assertNotIn('123456789',json.dumps(result))
        self.assertEqual(client.get.call_args.args[0],verifier.GOOGLE_GA4+'123456789/metadata')

    def test_no_secrets_in_errors_invalid_targets(self):
        for url in ('https://user:secret@example.com/?token=1','https://example.com/?key=abc'):
            with self.subTest(url=url):
                result=verifier.verify('pagespeed',target=url,live=True)
                self.assertEqual(result['result'],'target_url_must_not_contain_secrets')
                self.assertNotIn('user:secret',json.dumps(result))
                self.assertNotIn('key=abc',json.dumps(result))
        self.req.get.assert_not_called()

    def test_invalid_property_does_not_load_credentials(self):
        for service,prop in [('gsc','../../etc/passwd'),('ga4','properties/123/../456')]:
            result=verifier.verify(service,prop=prop,live=True,allow_account_read=True)
            self.assertEqual(result['result'],'property_required_or_invalid')
        self.req.get.assert_not_called()

    def test_bounded_response_is_closed(self):
        class HugeResponse(FakeResponse):
            def iter_content(self,chunk_size=65536):
                yield b'x'*(verifier.BODY_LIMIT+1)
        resp=HugeResponse()
        self.req.get.return_value=resp
        result=verifier.verify('pagespeed',target='https://example.com',live=True)
        self.assertEqual(result['result'],'invalid_url_or_response')
        self.assertTrue(resp.closed)


if __name__=='__main__':unittest.main()
