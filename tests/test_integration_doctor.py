"""Provider preflight must never leak secrets, touch networks, or mutate files."""
from __future__ import annotations
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('integration_doctor', ROOT/'scripts/integration_doctor.py')
assert SPEC and SPEC.loader
mod=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class ProviderPreflightTests(unittest.TestCase):
    def setUp(self):
        self.context=tempfile.TemporaryDirectory()
        self.addCleanup(self.context.cleanup)
        self.home=Path(self.context.name)
        self.codex=self.home/'.codex'
        self.codex.mkdir()
        self.google=self.home/'.config'/'claude-seo'
        self.google.mkdir(parents=True)

    def check(self, env=None):
        return mod.examine(environ=env or {},home=self.home,codex_home=self.codex)

    def test_empty_host_never_claims_live_integration(self):
        report=self.check()
        self.assertEqual(set(report['services']),set(mod.SERVICES))
        self.assertEqual(report['network_requests'],0)
        self.assertTrue(all(entry['status']=='missing_configuration' for entry in report['services'].values()))
        self.assertFalse(any(entry['live_verified'] for entry in report['services'].values()))

    def test_fake_secrets_are_never_rendered(self):
        fake_sa=self.home/'service-account.json'
        fake_sa.write_text('{"private_key":"FAKE-PRIVATE-SECRET-001"}')
        (self.google/'oauth-token.json').write_text('{"access_token":"FAKE-TOKEN-002"}')
        (self.google/'google-api.json').write_text(json.dumps({
            'api_key':'FAKE-KEY-003', 'default_property':'sc-domain:example.com',
            'ga4_property_id':'properties/456789', 'service_account_path':str(fake_sa),
        }))
        (self.codex/'config.toml').write_text('''
[mcp_servers.dataforseo]
command = "npx"
args = ["-y", "dataforseo-mcp-server@2.8.10"]
env = { DATAFORSEO_PASSWORD = "FAKE-MCP-SECRET-004" }
[mcp_servers.firecrawl]
command = "npx"
args = ["-y", "firecrawl-mcp"]
''')
        env={'DATAFORSEO_USERNAME':'x@example.com','DATAFORSEO_PASSWORD':'FAKE-DF-SECRET-005',
             'FIRECRAWL_API_KEY':'FAKE-FC-SECRET-006'}
        result=self.check(env)
        self.assertTrue(all(x['status']=='configured_unverified' for x in result['services'].values()))
        dump=json.dumps(result)+mod.markdown(result)
        for secret in ['FAKE-TOKEN','FAKE-PRIVATE','FAKE-KEY','FAKE-MCP','FAKE-DF','FAKE-FC','x@example.com',str(fake_sa)]:
            self.assertNotIn(secret,dump)
        self.assertFalse(any(x['live_verified'] for x in result['services'].values()))

    def test_missing_ga4_property_is_partial_not_verified(self):
        (self.google/'oauth-token.json').write_text('{"access_token":"fake"}')
        result=self.check()
        self.assertEqual(result['services']['gsc']['status'],'partial_configuration')
        self.assertEqual(result['services']['ga4']['status'],'partial_configuration')
        self.assertEqual(result['services']['pagespeed']['status'],'missing_configuration')

    def test_mcp_disabled_and_invalid_config_fail_closed(self):
        (self.codex/'config.toml').write_text('[mcp_servers.dataforseo]\nenabled = false\n')
        r=self.check({'DATAFORSEO_USERNAME':'test','DATAFORSEO_PASSWORD':'secret'})
        self.assertEqual(r['services']['dataforseo']['status'],'partial_configuration')
        (self.codex/'config.toml').write_text('not a valid [ toml')
        self.assertEqual(self.check()['services']['dataforseo']['status'],'missing_configuration')

    def test_no_token_refresh_or_network(self):
        with patch('socket.create_connection',side_effect=AssertionError('Unexpected network')):
            r=self.check({'GOOGLE_API_KEY':'FAKE-API-KEY'})
        self.assertEqual(r['services']['crux']['status'],'configured_unverified')
        self.assertEqual(r['services']['pagespeed']['status'],'configured_unverified')
        self.assertEqual(r['network_requests'],0)


if __name__=='__main__': unittest.main()
