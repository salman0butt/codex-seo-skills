#!/usr/bin/env python3
"""Bounded, explicitly authorized live Google SEO API connectivity probes.

Runs at most one request to Google's documented API per invocation; absent
--live the tool makes ZERO network requests. No paid services or mutations.
No credentials, private URLs, account identifiers, API response bodies,
permission details or network exceptions are written into the result.

    codex-seo run live_integration_verify.py pagespeed --url https://example.com --live
    codex-seo run live_integration_verify.py crux --url https://example.com --live
    codex-seo run live_integration_verify.py gsc --property sc-domain:example.com --live --allow-account-read
    codex-seo run live_integration_verify.py ga4 --property 123456789 --live --allow-account-read

Private account probes query only property metadata. OAuth token refresh may be
performed by the Google auth library, but only behind --allow-account-read.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

GOOGLE_PSI = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'
GOOGLE_CRUX = 'https://chromeuxreport.googleapis.com/v1/records:queryRecord'
GOOGLE_GSC = 'https://www.googleapis.com/webmasters/v3/sites/'
GOOGLE_GA4 = 'https://analyticsdata.googleapis.com/v1beta/properties/'
BODY_LIMIT = 8 * 1024 * 1024
TIMEOUT = (5, 35)
DOMAIN_PROPERTY = re.compile(r'^sc-domain:(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$', re.I)


def _http_status(status: int, service: str) -> str:
    if status == 401: return 'authentication_required'
    if status == 403: return 'permission_or_quota_denied'
    if status == 429: return 'rate_limited'
    if status == 404: return 'field_data_unavailable' if service == 'crux' else 'not_found'
    if status == 400: return 'bad_request'
    if 500 <= status <= 599: return 'provider_error'
    return 'unverified_response'


def _safe_target(url: str) -> str:
    """Avoid emitting URL queries, fragments or embedded credentials."""
    parts = urlsplit(url)
    hostname = parts.hostname or ''
    if ':' in hostname and not hostname.startswith('['): hostname = f'[{hostname}]'
    # Page paths may themselves contain access tokens, even without ?query.
    # Only report the public origin; the full URL stays in the API request.
    return f'{parts.scheme}://{hostname}{":" + str(parts.port) if parts.port else ""}/'


def _valid_property(service: str, value: str) -> bool:
    if service == 'ga4':
        return bool(re.fullmatch(r'(?:properties/)?[0-9]{1,20}', value))
    if DOMAIN_PROPERTY.fullmatch(value): return True
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == 'https' and bool(parsed.hostname) and
                not parsed.username and not parsed.password and not parsed.query and
                not parsed.fragment and not parsed.port and bool(parsed.path.startswith('/')))
    except ValueError:
        return False


def _read_limited(response) -> dict:
    body = bytearray()
    for chunk in response.iter_content(chunk_size=65536):
        body.extend(chunk)
        if len(body) > BODY_LIMIT:
            raise ValueError('Response exceeds safety limit')
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError('Expected JSON object')
    return parsed


def _base(service: str) -> dict:
    return {
        'schema_version': 1,
        'service': service,
        'probe': 'single-request-property-metadata' if service in ('gsc','ga4') else 'single-request-public-metrics',
        'read_only': True,
        'network_requests': 0,
        'live_verified': False,
        'result': 'blocked',
        'http_status': None,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'metrics': {},
        'credentials_echoed': False,
        'limitations': [],
    }


def verify(service: str, *, target: str = '', prop: str = '', live: bool = False,
           allow_account_read: bool = False, timeout: int = 35,
           use_api_key: bool = False, client=None, auth_factory=None) -> dict:
    """One explicit request; mocks can inject client and auth factory for CI."""
    output = _base(service)
    if not live:
        output['result'] = 'explicit_opt_in_required'
        output['limitations'].append('Pass --live to request exactly one live read-only API call.')
        return output
    if service in ('gsc','ga4') and not allow_account_read:
        output['result'] = 'account_access_not_authorized'
        output['limitations'].append('Private property lookup requires --allow-account-read and an explicit --property.')
        return output
    if service in ('gsc','ga4'):
        if not prop or not _valid_property(service, prop):
            output['result'] = 'property_required_or_invalid'
            return output
    elif not target:
        output['result'] = 'target_url_required'
        return output
    else:
        try:
            if '?' in target or '#' in target or '@' in urlsplit(target).netloc:
                output['result'] = 'target_url_must_not_contain_secrets'
                return output
        except ValueError:
            output['result'] = 'invalid_url_or_response'
            return output
    if not (1 <= timeout <= 60):
        output['result'] = 'invalid_timeout'
        return output

    try:
        import requests
        if service in ('pagespeed','crux'):
            from url_safety import validate_url_strict
            # Strict URL checks can resolve DNS but do not make HTTP requests.
            normalized, _ = validate_url_strict(target)
            output['target_url'] = _safe_target(normalized)
            from google_auth import get_api_key
            api_key = get_api_key() if (use_api_key or service == 'crux') else None
            if use_api_key and not api_key:
                output['result'] = 'api_key_required'
                return output
            if service == 'crux' and not api_key:
                output['result'] = 'api_key_required'
                return output
            headers = {'X-Goog-Api-Key': api_key} if api_key else None
            request_client = client or requests
            output['network_requests'] = 1
            if service == 'pagespeed':
                response = request_client.get(
                    GOOGLE_PSI, params={'url': normalized,'strategy':'mobile','category':'SEO'},
                    headers=headers, timeout=(5,timeout), stream=True,
                )
            else:
                response = request_client.post(
                    GOOGLE_CRUX, json={'url':normalized,'formFactor':'PHONE'},
                    headers=headers, timeout=(5,timeout), stream=True,
                )
        else:
            # Do not load, refresh or transmit private credentials unless the
            # operator explicitly requested account read with --allow-account-read.
            if auth_factory is None:
                from google_auth import get_oauth_credentials
                from google.auth.transport.requests import AuthorizedSession
                scope = ('https://www.googleapis.com/auth/webmasters.readonly' if service == 'gsc'
                         else 'https://www.googleapis.com/auth/analytics.readonly')
                # The legacy auth helper can print private credential paths
                # in its own diagnostics. Suppress those, reporting only a
                # generic safe status through this public CLI.
                with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                    creds = get_oauth_credentials([scope])
                if not creds:
                    output['result'] = 'credentials_unavailable'
                    return output
                request_client = AuthorizedSession(creds)
            else:
                request_client = auth_factory(service)
                if request_client is None:
                    output['result'] = 'credentials_unavailable'
                    return output
            endpoint = (GOOGLE_GSC + quote(prop,safe='') if service == 'gsc' else
                        GOOGLE_GA4 + (prop.split('/')[-1]) + '/metadata')
            output['network_requests'] = 1
            response = request_client.get(endpoint, timeout=(5,timeout), stream=True)

        try:
            output['http_status'] = response.status_code
            if response.status_code != 200:
                output['result'] = _http_status(response.status_code,service)
                return output
            payload = _read_limited(response)
        finally:
            response.close()

        if service == 'pagespeed':
            lighthouse = payload.get('lighthouseResult') or {}
            if not isinstance(lighthouse,dict) or not lighthouse.get('lighthouseVersion'):
                output['result'] = 'unexpected_response'
                return output
            scores = {}
            for key, row in (lighthouse.get('categories') or {}).items():
                if key in ('seo','performance','accessibility','best-practices') and isinstance(row,dict):
                    score = row.get('score')
                    if isinstance(score,(int,float)) and not isinstance(score,bool) and 0 <= score <= 1:
                        scores[key] = round(score*100)
            output['metrics'] = {'lighthouse_version':str(lighthouse['lighthouseVersion'])[:32],
                                 'lab_scores':scores,
                                 'analysis_timestamp':payload.get('analysisUTCTimestamp')}
            output['limitations'].append('One mobile Lighthouse lab run; no verified CrUX field data or ranking outcome.')
        elif service == 'crux':
            record = payload.get('record')
            if not isinstance(record,dict) or not isinstance(record.get('metrics'),dict):
                output['result'] = 'unexpected_response'
                return output
            values = {}
            for key in ('largest_contentful_paint','interaction_to_next_paint','cumulative_layout_shift'):
                metric = record['metrics'].get(key)
                p75 = (metric.get('percentiles') or {}).get('p75') if isinstance(metric,dict) else None
                if isinstance(p75,(int,float)) and not isinstance(p75,bool): values[key] = p75
            output['metrics'] = {'field_p75':values, 'form_factor':'PHONE'}
            output['limitations'].append('CrUX is sampled field data; missing metrics are not zero.')
        elif service == 'gsc':
            if not isinstance(payload.get('permissionLevel'),str):
                output['result'] = 'unexpected_response'
                return output
            output['metrics'] = {'property_metadata_available':True}
            output['limitations'].append('Property access metadata only; Search Analytics clicks, impressions and indexing not measured.')
        else:
            if not isinstance(payload.get('name'),str) or not payload['name'].endswith('/metadata'):
                output['result'] = 'unexpected_response'
                return output
            output['metrics'] = {'property_metadata_available':True}
            output['limitations'].append('GA4 property metadata only; no traffic, conversions or attribution queried.')
        output['result'] = 'verified'
        output['live_verified'] = True
    except (ValueError, TypeError):
        output['result'] = 'invalid_url_or_response'
    except Exception as exc:
        # Never print exception strings: exceptions can contain URLs, tokens,
        # service account paths and verbose Google API response bodies.
        output['result'] = 'network_or_dependency_error'
        output['error_type'] = type(exc).__name__ if type(exc).__name__ in (
            'ConnectTimeout','ReadTimeout','ConnectionError','SSLError','ImportError','ModuleNotFoundError') else 'Unavailable'
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('service',choices=('pagespeed','crux','gsc','ga4'))
    parser.add_argument('--url',default='',help='Public URL for PSI/CrUX; no credentials or query tokens')
    parser.add_argument('--property',default='',help='Explicit GSC or GA4 property; not logged')
    parser.add_argument('--live',action='store_true',help='Authorize one live provider request')
    parser.add_argument('--allow-account-read',action='store_true',help='Authorize read-only private property metadata lookup and possible OAuth refresh')
    parser.add_argument('--use-api-key',action='store_true',help='For PSI, use configured API key instead of anonymous access')
    parser.add_argument('--timeout',type=int,default=35)
    args = parser.parse_args(argv)
    result = verify(args.service,target=args.url,prop=args.property,live=args.live,
                    allow_account_read=args.allow_account_read,timeout=args.timeout,
                    use_api_key=args.use_api_key)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['result']=='verified' else 2


if __name__=='__main__':
    sys.exit(main())
