#!/usr/bin/env python3
"""Aggregate-only, explicitly authorized Google Search Console / GA4 reports.

This is a *read-only* reporting API POST, not a site mutation. Defaults to
zero network requests. With --live --allow-account-read --property, at most
one reporting HTTP request is made after any Google credential refresh.
Never prints property IDs, query text, page URLs, raw Google responses or keys.

    codex-seo run private_seo_report.py gsc --property sc-domain:example.com --days 28 --live --allow-account-read
    codex-seo run private_seo_report.py ga4 --property 123456789 --days 28 --live --allow-account-read
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

from live_integration_verify import _http_status, _read_limited, _valid_property

GSC_API = 'https://www.googleapis.com/webmasters/v3/sites/'
GA4_API = 'https://analyticsdata.googleapis.com/v1beta/properties/'
GSC_SCOPE = 'https://www.googleapis.com/auth/webmasters.readonly'
GA4_SCOPE = 'https://www.googleapis.com/auth/analytics.readonly'


def _valid_number(value, lower=0, upper=1e12):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and lower <= value <= upper


def _range(days: int, service: str, today: date):
    lag = 3 if service == 'gsc' else 1
    end = today - timedelta(days=lag)
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat(), lag


def _parse_gsc(payload: dict) -> tuple[str, dict]:
    rows = payload.get('rows', [])
    if not isinstance(rows,list): return 'unexpected_response', {}
    if not rows: return 'no_data', {}
    if len(rows) != 1 or not isinstance(rows[0],dict): return 'unexpected_response', {}
    row = rows[0]
    keys = ('clicks','impressions','ctr','position')
    if any(not _valid_number(row.get(key),0,1 if key == 'ctr' else 1e12) for key in keys):
        return 'unexpected_response', {}
    return 'verified', {
        'clicks': row['clicks'], 'impressions': row['impressions'],
        'ctr_percent': round(row['ctr']*100,2),
        'average_position': round(row['position'],2),
    }


def _parse_ga4(payload: dict) -> tuple[str, dict]:
    rows = payload.get('rows', [])
    if not isinstance(rows,list): return 'unexpected_response', {}
    if not rows: return 'no_data', {}
    headers = payload.get('metricHeaders')
    names = ('sessions','totalUsers','engagedSessions')
    if not isinstance(headers,list) or [h.get('name') for h in headers if isinstance(h,dict)] != list(names):
        return 'unexpected_response', {}
    if len(rows) != 1 or not isinstance(rows[0],dict): return 'unexpected_response', {}
    vals = rows[0].get('metricValues')
    if not isinstance(vals,list) or len(vals) != 3: return 'unexpected_response', {}
    found = {}
    for name, value in zip(names,vals):
        try:
            if not isinstance(value,dict): return 'unexpected_response', {}
            raw = value.get('value')
            if not isinstance(raw,str) or not raw.isascii() or not raw.isdecimal(): return 'unexpected_response', {}
            num = int(raw)
            if not _valid_number(num): return 'unexpected_response', {}
            found[name] = num
        except (ValueError,TypeError,OverflowError):
            return 'unexpected_response', {}
    return 'verified', {'organic_search_sessions':found['sessions'],
                        'organic_search_total_users':found['totalUsers'],
                        'organic_search_engaged_sessions':found['engagedSessions']}


def report(service: str, *, prop: str = '', days: int = 28, live: bool = False,
           allow_account_read: bool = False, today: date | None = None,
           auth_factory=None) -> dict:
    out = {
        'schema_version': 1, 'service':service, 'read_only':True,
        'scope':'aggregate-only', 'network_requests':0, 'live_verified':False,
        'result':'blocked', 'http_status':None, 'metrics':{},
        'date_range':None, 'timestamp_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'property_identifier_redacted':True, 'credentials_echoed':False,
        'limitations':['No queries, pages, visitor identifiers or raw Google API payload are included.',
                       'Metrics are property-specific and do not prove indexing, ranking improvement or conversions.'],
    }
    if service not in ('gsc','ga4'):
        out['result']='unsupported_service'; return out
    if not isinstance(days,int) or isinstance(days,bool) or not (1<=days<=90):
        out['result']='invalid_window'; return out
    if not live or not allow_account_read:
        out['result']='explicit_account_read_required'; return out
    if not prop or not _valid_property(service,prop):
        out['result']='property_required_or_invalid'; return out
    start,end,lag = _range(days,service,today or date.today())
    out['date_range']={'start':start, 'end':end, 'days':days, 'finalization_lag_days':lag}
    if service == 'gsc':
        endpoint = GSC_API + quote(prop,safe='') + '/searchAnalytics/query'
        body = {'startDate':start,'endDate':end,'dimensions':[], 'type':'web','dataState':'final','rowLimit':1}
    else:
        endpoint = GA4_API + prop.split('/')[-1] + ':runReport'
        body = {'dateRanges':[{'startDate':start,'endDate':end}],
                'metrics':[{'name':'sessions'},{'name':'totalUsers'},{'name':'engagedSessions'}],
                'dimensionFilter':{'filter':{'fieldName':'sessionDefaultChannelGroup',
                     'stringFilter':{'matchType':'EXACT','value':'Organic Search'}}},
                'limit':'1'}
    out['limitations'].append('Search Console uses finalized Pacific-time dates with a 3-day reporting lag.' if service=='gsc'
                              else 'GA4 uses the property reporting timezone; UTC-selected dates may differ from the property local date.')
    try:
        if auth_factory is None:
            from google_auth import get_oauth_credentials
            from google.auth.transport.requests import AuthorizedSession
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                creds=get_oauth_credentials([GSC_SCOPE if service=='gsc' else GA4_SCOPE])
            if not creds:
                out['result']='credentials_unavailable';return out
            client=AuthorizedSession(creds)
        else:
            client=auth_factory(service)
            if client is None:
                out['result']='credentials_unavailable';return out
        out['network_requests']=1
        response=client.post(endpoint,json=body,timeout=(5,35),stream=True)
        try:
            out['http_status']=response.status_code
            if response.status_code!=200:
                out['result']=_http_status(response.status_code,service);return out
            payload=_read_limited(response)
        finally:
            response.close()
        if not isinstance(payload,dict):
            out['result']='unexpected_response';return out
        status, metrics = (_parse_gsc(payload) if service=='gsc' else _parse_ga4(payload))
        out['result']=status
        out['metrics']=metrics
        out['live_verified']=status=='verified'
        if status=='no_data':
            out['limitations'].append('No aggregate rows were returned; this is not proof that traffic is zero.')
    except Exception as exc:
        out['result']='network_or_dependency_error'
        # Do not echo exceptions: often include private URLs or provider tokens.
        out['error_type']=type(exc).__name__ if type(exc).__name__ in (
            'ConnectTimeout','ReadTimeout','ConnectionError','SSLError','ImportError','ModuleNotFoundError') else 'Unavailable'
    return out


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('service',choices=('gsc','ga4'))
    parser.add_argument('--property',default='',help='Exact authorized property (never printed)')
    parser.add_argument('--days',type=int,default=28,help='1..90 days, with finalized reporting lag')
    parser.add_argument('--live',action='store_true',help='Explicitly enable one live read-only API request')
    parser.add_argument('--allow-account-read',action='store_true',help='Authorize aggregate private-property reporting and possible OAuth refresh')
    args=parser.parse_args(argv)
    result=report(args.service,prop=args.property,days=args.days,live=args.live,allow_account_read=args.allow_account_read)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0 if result['result']=='verified' else 2


if __name__=='__main__':
    raise SystemExit(main())
