"""Private SEO aggregate reporting is opt-in, metadata-safe, and read-only."""
from __future__ import annotations
import importlib.util
import json
import sys
import types
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('private_seo_report',ROOT/'scripts/private_seo_report.py')
assert SPEC and SPEC.loader
sys.path.insert(0,str(ROOT/'scripts'))
reporter=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reporter)


class FakeResponse:
    def __init__(self,status=200,body=None):
        self.status_code=status
        self.body=body or {}
        self.closed=False
    def iter_content(self,chunk_size=65536):
        yield json.dumps(self.body).encode()
    def close(self):self.closed=True


class PrivateSEOReportTests(unittest.TestCase):
    def setUp(self):
        self.today=date(2026,10,22)
        self.client=MagicMock()
        self.factory=MagicMock(return_value=self.client)
    def run_report(self,service='gsc',**kwargs):
        return reporter.report(service,prop='sc-domain:example.com' if service=='gsc' else '123456789',
                               today=self.today,auth_factory=self.factory,**kwargs)

    def test_default_no_network(self):
        for service in ('gsc','ga4'):
            result=self.run_report(service)
            self.assertEqual(result['result'],'explicit_account_read_required')
            self.assertEqual(result['network_requests'],0)
        self.factory.assert_not_called()

    def test_both_explicit_authorization_flags_required(self):
        for live,allow in ((True,False),(False,True),(False,False)):
            with self.subTest(live=live,allow=allow):
                result=self.run_report('ga4',live=live,allow_account_read=allow)
                self.assertEqual(result['result'],'explicit_account_read_required')
        self.factory.assert_not_called()

    def test_property_rejected_before_credentials(self):
        for service,value in [('gsc','sc-domain:localhost'),('gsc','../admin'),('ga4','123/../../xxx')]:
            with self.subTest(service=service,value=value):
                result=reporter.report(service,prop=value,live=True,allow_account_read=True,today=self.today,auth_factory=self.factory)
                self.assertEqual(result['result'],'property_required_or_invalid')
        self.factory.assert_not_called()

    def test_date_window_is_bounded(self):
        for days in (-1,0,91,False,1.5):
            with self.subTest(days=days):
                result=self.run_report(days=days,live=True,allow_account_read=True)
                self.assertEqual(result['result'],'invalid_window')
        self.factory.assert_not_called()

    def test_gsc_single_aggregate_no_query_leak(self):
        response=FakeResponse(body={'rows':[{'clicks':45,'impressions':900,'ctr':.05,'position':13.322,
                                            'keys':['Sensitive Search Term']}], 'responseAggregationType':'byProperty'})
        self.client.post.return_value=response
        result=self.run_report(live=True,allow_account_read=True,days=28)
        self.assertEqual(result['result'],'verified')
        self.assertEqual(result['metrics'],{'clicks':45,'impressions':900,'ctr_percent':5.0,'average_position':13.32})
        self.assertTrue(result['live_verified'])
        self.assertEqual(result['network_requests'],1)
        self.assertEqual(result['date_range'],{'start':'2026-09-22','end':'2026-10-19','days':28,'finalization_lag_days':3})
        self.assertEqual(self.client.post.call_args.kwargs['json']['dimensions'],[])
        self.assertEqual(self.client.post.call_args.kwargs['json']['dataState'],'final')
        self.assertNotIn('Sensitive',json.dumps(result))
        self.assertNotIn('example.com',json.dumps(result))
        self.assertTrue(response.closed)

    def test_ga4_organic_session_filter_and_nonduplicated_total_users(self):
        response=FakeResponse(body={'metricHeaders':[{'name':'sessions'},{'name':'totalUsers'},{'name':'engagedSessions'}],
            'rows':[{'metricValues':[{'value':'93'},{'value':'80'},{'value':'71'}], 'dimensionValues':[{'value':'private'}]}]})
        self.client.post.return_value=response
        result=self.run_report('ga4',live=True,allow_account_read=True)
        self.assertEqual(result['result'],'verified')
        self.assertEqual(result['metrics'],{'organic_search_sessions':93,'organic_search_total_users':80,
                                            'organic_search_engaged_sessions':71})
        self.assertEqual(result['date_range']['end'],'2026-10-21')
        req=self.client.post.call_args.kwargs['json']
        self.assertNotIn('dimensions',req)
        self.assertEqual(req['dimensionFilter']['filter']['stringFilter']['value'],'Organic Search')
        self.assertIn('123456789:runReport',self.client.post.call_args.args[0])
        self.assertNotIn('123456789',json.dumps(result))
        self.assertNotIn('private',json.dumps(result))
        self.assertTrue(response.closed)

    def test_ga4_wrong_header_order_fails_not_mislabelled(self):
        self.client.post.return_value=FakeResponse(body={'metricHeaders':[{'name':'totalUsers'},{'name':'sessions'},{'name':'engagedSessions'}],
            'rows':[{'metricValues':[{'value':'1'},{'value':'2'},{'value':'3'}]}]})
        result=self.run_report('ga4',live=True,allow_account_read=True)
        self.assertEqual(result['result'],'unexpected_response')
        self.assertFalse(result['live_verified'])
        self.assertEqual(result['metrics'],{})

    def test_no_data_is_not_zero_traffic(self):
        self.client.post.return_value=FakeResponse(body={'rows':[]})
        result=self.run_report(live=True,allow_account_read=True)
        self.assertEqual(result['result'],'no_data')
        self.assertFalse(result['live_verified'])
        self.assertNotIn('clicks',result['metrics'])
        self.assertTrue(any('not proof' in x for x in result['limitations']))

    def test_errors_suppress_provider_messages_and_property_identifiers(self):
        for status in (401,403,429,500):
            with self.subTest(status=status):
                self.client.post.return_value=FakeResponse(status,{'error':{'message':'SECRET-API-MESSAGE'}})
                result=self.run_report('ga4',live=True,allow_account_read=True)
                self.assertNotIn('SECRET',json.dumps(result))
                self.assertNotIn('123456789',json.dumps(result))
                self.assertEqual(result['metrics'],{})
                self.assertFalse(result['live_verified'])
                self.assertEqual(result['http_status'],status)

    def test_bounded_response_read(self):
        class LargeResponse(FakeResponse):
            def iter_content(self,chunk_size=65536):
                from live_integration_verify import BODY_LIMIT
                yield b'x'*(BODY_LIMIT+1)
        self.client.post.return_value=LargeResponse()
        result=self.run_report(live=True,allow_account_read=True)
        self.assertEqual(result['result'],'network_or_dependency_error')
        self.assertEqual(result['error_type'],'Unavailable')
        self.assertTrue(self.client.post.return_value.closed)

    def test_negative_nan_and_boolean_metrics_rejected(self):
        for val in (-1,float('nan'),True):
            with self.subTest(value=str(val)):
                result,metrics=reporter._parse_gsc({'rows':[{'clicks':val,'impressions':100,'ctr':.1,'position':2}]})
                self.assertEqual(result,'unexpected_response')
                self.assertEqual(metrics,{})

    def test_missing_credentials_no_network(self):
        self.factory.return_value=None
        result=self.run_report(live=True,allow_account_read=True)
        self.assertEqual(result['result'],'credentials_unavailable')
        self.assertEqual(result['network_requests'],0)
        self.client.post.assert_not_called()


if __name__=='__main__':unittest.main()
