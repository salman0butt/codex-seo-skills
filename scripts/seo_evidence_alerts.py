#!/usr/bin/env python3
"""Offline evidence-quality diagnostics and conservative change alerts.

Reads two snapshots from the private v0.8 history; does not mutate history,
connect to providers, refresh credentials, install schedules or send alerts.
Alert candidates are advisory review items, never proof of SEO causality.

  codex-seo run seo_evidence_alerts.py --history-dir ~/seo-private-history --as-of 2026-10-23
  codex-seo run seo_evidence_alerts.py --history-dir ~/seo-private-history --confirm-history-same-property --confirm-same-page-set
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import sqlite3
import sys
from pathlib import Path

from seo_history import ReportInputError, _open_existing, default_history_dir
from seo_report_builder import METRICS, _comparison, _day, _num, ISSUES

PROVIDER_ALERT_FIELDS = {'gsc': 'clicks', 'ga4': 'organic_search_sessions'}
CRITICAL_PAGE_FINDINGS = frozenset(('missing-title', 'missing-h1'))
SCHEMA_VERSION = 1


def _normalized_report(obj: dict) -> dict:
    """Refuse unsupported/tampered on-disk shapes before acting on values."""
    if (not isinstance(obj, dict) or obj.get('schema_version') != SCHEMA_VERSION or
        obj.get('scope') != 'offline-composite-evidence-report' or
        obj.get('network_requests') != 0 or
        obj.get('private_property_identifiers_included') is not False):
        raise ReportInputError('Unsupported history report structure')
    providers, pages = obj.get('provider_reports'), obj.get('page_audits')
    if not isinstance(providers, dict) or not isinstance(pages, list) or len(pages) > 10:
        raise ReportInputError('Invalid history provider or audit container')
    if set(providers) - {'gsc','ga4'}:
        raise ReportInputError('Unknown provider in history')
    safe = {'provider_reports':{}, 'page_audits':[]}
    for name,item in providers.items():
        if not isinstance(item,dict) or not isinstance(item.get('current'),dict):
            raise ReportInputError('Invalid provider report entry')
        cur = item['current']
        if cur.get('service') != name or cur.get('status') not in ('verified','no_data',
                'rate_limited','permission_or_quota_denied','authentication_required',
                'credentials_unavailable','network_or_dependency_error','blocked',
                'explicit_account_read_required','property_required_or_invalid'):
            raise ReportInputError('Invalid provider report status')
        verified = cur['status'] == 'verified'
        if cur.get('reported_as_verified') is not verified or not isinstance(cur.get('metrics'),dict):
            raise ReportInputError('Contradictory provider evidence')
        window = cur.get('date_range')
        if window is not None:
            if not isinstance(window,dict) or type(window.get('days')) is not int:
                raise ReportInputError('Invalid provider report range')
            start, end = _day(window.get('start')),_day(window.get('end'))
            if (not 1 <= window['days'] <= 90 or end < start or
                (end-start).days+1 != window['days']):
                raise ReportInputError('Inconsistent provider report dates')
            safe_window = {'start':start.isoformat(),'end':end.isoformat(),'days':window['days']}
        else:
            safe_window = None
        if verified and safe_window is None:
            raise ReportInputError('Verified metrics without dates')
        if cur['status']=='no_data' and safe_window is None:
            raise ReportInputError('No-data report without dates')
        if verified:
            metrics = cur['metrics']
            if set(metrics) != set(METRICS[name]):
                raise ReportInputError('Unknown or missing metrics')
            for key,val in metrics.items():
                if not _num(val,0,100 if key=='ctr_percent' else 1e12):
                    raise ReportInputError('Invalid reported metric')
                if key in ('clicks','impressions','organic_search_sessions','organic_search_total_users','organic_search_engaged_sessions') and type(val) is not int:
                    raise ReportInputError('Reported count must be integer')
            safe_metrics = {key:metrics[key] for key in METRICS[name]}
        else:
            if cur['metrics']:
                raise ReportInputError('Unavailable reports cannot contain metrics')
            safe_metrics={}
        safe['provider_reports'][name] = {'current':{
            'service':name,'status':cur['status'],'reported_as_verified':verified,
            'metrics':safe_metrics,'date_range':safe_window}}
    for index,page in enumerate(pages,1):
        if not isinstance(page,dict) or page.get('scope')!='single-page-raw-html':
            raise ReportInputError('Unexpected page audit structure')
        ids = page.get('finding_ids')
        if not isinstance(ids,list) or any(not isinstance(x,str) or x not in ISSUES for x in ids):
            raise ReportInputError('Unknown page finding')
        try:
            observed = datetime.fromisoformat(page['observed_at_utc'].replace('Z','+00:00'))
            if observed.tzinfo is None:
                raise ValueError()
        except (ValueError,TypeError,KeyError,AttributeError):
            raise ReportInputError('Invalid page observation timestamp') from None
        origin = page.get('page_origin')
        if (not isinstance(origin,str) or len(origin)>300 or
            not origin.startswith(('https://','http://')) or
            not origin.endswith('/') or '?' in origin or '#' in origin or '@' in origin):
            raise ReportInputError('Invalid redacted page origin')
        safe['page_audits'].append({'audit_reference':f'audit-{index}',
             'page_origin':origin,'finding_ids':sorted(set(ids)),
             'observed_at_utc':observed.isoformat(timespec='seconds')})
    return safe


def _load_two(history_dir:Path, *, current_id:int|None=None) -> tuple[tuple[int,dict],tuple[int,dict]|None]:
    with closing(_open_existing(history_dir)) as conn:
        if current_id is None:
            rows=conn.execute('SELECT id,report_json FROM snapshots ORDER BY id DESC LIMIT 2').fetchall()
        else:
            if current_id < 1:
                raise ReportInputError('Snapshot ID must be positive')
            cur=conn.execute('SELECT id,report_json FROM snapshots WHERE id=?',(current_id,)).fetchone()
            if cur is None:
                raise ReportInputError('Snapshot not found')
            previous=conn.execute('SELECT id,report_json FROM snapshots WHERE id<? ORDER BY id DESC LIMIT 1',(current_id,)).fetchone()
            rows=[cur]+([previous] if previous else [])
    if not rows:
        raise ReportInputError('No snapshots found')
    def read(row):
        try:
            parsed=json.loads(row[1])
        except (ValueError,TypeError):
            raise ReportInputError('Corrupt stored report') from None
        return row[0],_normalized_report(parsed)
    return read(rows[0]), read(rows[1]) if len(rows)>1 else None


def _alert_id(previous_id:int, current_id:int, kind:str, name:str)->str:
    raw=f'{previous_id}:{current_id}:{kind}:{name}'.encode('ascii')
    return hashlib.sha256(raw).hexdigest()[:16]


def evaluate(current:tuple[int,dict],previous:tuple[int,dict]|None, *,
             as_of:date, max_age_days:int=14, min_baseline:int=20,
             min_absolute_drop:int=10, drop_percent:float=30.0,
             confirm_history_same_property:bool=False,
             confirm_same_page_set:bool=False)->dict:
    if (type(max_age_days) is not int or type(min_baseline) is not int or
        type(min_absolute_drop) is not int or not isinstance(drop_percent,(int,float)) or
        isinstance(drop_percent,bool) or not math.isfinite(drop_percent) or
        not 1<=max_age_days<=365 or not 1<=min_baseline<=100000000 or
        not 1<=min_absolute_drop<=100000000 or not 0<drop_percent<=100):
        raise ReportInputError('Alert thresholds outside allowed bounds')
    current_id,now = current
    before_id,old = previous if previous else (None,None)
    results={'schema_version':1,'scope':'offline-evidence-quality-and-advisory-alerts',
        'current_snapshot_id':current_id,'previous_snapshot_id':before_id,
        'as_of':as_of.isoformat(),'network_requests':0,'history_modified':False,
        'notifications_sent':0,'source_provenance':'operator-provided saved JSON, not authenticated',
        'quality_findings':[], 'alerts':[], 'suppressed_comparisons':[],
        'limitations':['This is an offline diagnostic and never delivers messages or modifies sites.',
          'A flagged metric change is descriptive, not proof of Google ranking loss or a causal incident.',
          'No alert verifies that a page finding was fixed; each page slot identity must be independently attested.',
          'Stale or unauthorized sources cannot substantiate a traffic-change alert.']}
    fresh={}
    for name, entry in now['provider_reports'].items():
        cur=entry['current']
        if cur['status'] not in ('verified','no_data'):
            results['quality_findings'].append({'code':'provider_unavailable','source':name,
                'status':cur['status'],'severity':'review',
                'note':'Provider did not supply verified aggregate metrics.'})
        elif cur['status']=='no_data':
            results['quality_findings'].append({'code':'no_data','source':name,
                'severity':'review','note':'No rows returned; this is not measured zero.'})
        if cur['date_range'] is None:
            fresh[name]=False
            continue
        end=_day(cur['date_range']['end'])
        age=(as_of-end).days
        if age<0:
            results['quality_findings'].append({'code':'future_window','source':name,'severity':'review',
                'note':'Source report end date lies in the future relative to --as-of.'})
        elif age>max_age_days:
            results['quality_findings'].append({'code':'stale_window','source':name,'severity':'review',
                'age_days':age,'note':'This report window ended earlier than the allowed freshness threshold.'})
        fresh[name]=0<=age<=max_age_days and cur['status']=='verified'
    for name in sorted(now['provider_reports']):
        if old is None or name not in old['provider_reports']:
            results['suppressed_comparisons'].append({'source':name,'reason':'no_previous_provider_data'})
            continue
        if not confirm_history_same_property:
            results['suppressed_comparisons'].append({'source':name,'reason':'same_property_not_attested'})
            continue
        if not fresh.get(name):
            results['suppressed_comparisons'].append({'source':name,'reason':'current_evidence_unavailable_or_stale'})
            continue
        earlier=old['provider_reports'][name]['current']
        comp=_comparison(now['provider_reports'][name]['current'],earlier,True)
        if comp['status']!='compared_with_operator_attestation':
            results['suppressed_comparisons'].append({'source':name,'reason':comp['status']})
            continue
        field=PROVIDER_ALERT_FIELDS[name]
        metric=comp['metrics'][field]
        baseline=metric['previous']; current_value=metric['current']
        drop=baseline-current_value
        percentage=(100*drop/baseline) if baseline>0 else 0
        if baseline>=min_baseline and drop>=min_absolute_drop and percentage>=drop_percent:
            results['alerts'].append({'id':_alert_id(before_id,current_id,'drop',name),
                'kind':'aggregate_count_drop','severity':'review', 'provider':name,'metric':field,
                'previous':baseline,'current':current_value,'absolute_drop':drop,
                'relative_drop_percent':round(percentage,2),
                'note':'Review measurement and seasonality; no root cause or ranking loss inferred.'})
    page_fresh=[]
    for index,page in enumerate(now['page_audits'],1):
        observed=datetime.fromisoformat(page['observed_at_utc']).date()
        age=(as_of-observed).days
        if age<0 or age>max_age_days:
            results['quality_findings'].append({'code':'future_page_audit' if age<0 else 'stale_page_audit',
                'source':f'audit-{index}','severity':'review',
                'note':'Page evidence is outside the selected freshness window.'})
        page_fresh.append(0<=age<=max_age_days)
    if old is not None and now['page_audits'] and old['page_audits']:
        if not confirm_same_page_set:
            results['suppressed_comparisons'].append({'source':'page_audits','reason':'same_page_set_not_attested'})
        elif (len(now['page_audits'])!=len(old['page_audits']) or
              [x['page_origin'] for x in now['page_audits']] != [x['page_origin'] for x in old['page_audits']]):
            results['suppressed_comparisons'].append({'source':'page_audits','reason':'audit_set_changed'})
        else:
            for index,(current_page,old_page) in enumerate(zip(now['page_audits'],old['page_audits']),1):
                if not page_fresh[index-1]:
                    results['suppressed_comparisons'].append({'source':f'audit-{index}',
                        'reason':'page_evidence_unavailable_or_stale'})
                    continue
                cur_seen=datetime.fromisoformat(current_page['observed_at_utc'])
                prev_seen=datetime.fromisoformat(old_page['observed_at_utc'])
                if cur_seen<=prev_seen:
                    results['suppressed_comparisons'].append({'source':f'audit-{index}','reason':'non_newer_audit_timestamp'})
                    continue
                new_issues=(set(current_page['finding_ids'])-set(old_page['finding_ids'])) & CRITICAL_PAGE_FINDINGS
                for issue in sorted(new_issues):
                    results['alerts'].append({'id':_alert_id(before_id,current_id,'new_page_finding',f'{index}:{issue}'),
                        'kind':'new_static_page_finding','severity':'review','audit_reference':f'audit-{index}',
                        'issue_id':issue,
                        'note':'A new raw-HTML finding was observed; verify page context and rendered DOM manually.'})
    results['alerts'].sort(key=lambda x:(x['kind'],x.get('provider',''),x.get('audit_reference',''),x['id']))
    results['quality_status']='review_needed' if results['quality_findings'] or results['alerts'] else 'no_issues_in_supplied_evidence'
    return results


def _markdown(data:dict)->str:
    lines=['# Offline SEO evidence quality and change alerts','',
        f'As of {data["as_of"]}; snapshots {data["previous_snapshot_id"]} → {data["current_snapshot_id"]}',
        'No network or notifications; operator-source authenticity unverified.','',
        '## Data quality','']
    for entry in data['quality_findings']:
        lines.append(f'- {entry["source"]}: {entry["code"]} — {entry["note"]}')
    if not data['quality_findings']:lines.append('No structural/freshness issues detected in the supplied evidence; not an SEO health certification.')
    lines.extend(['','## Advisory alerts',''])
    for entry in data['alerts']:
        metric=entry.get('metric',entry.get('issue_id'))
        context=(f' {entry["previous"]} → {entry["current"]} ({entry["relative_drop_percent"]}% decline).'
                 if entry['kind']=='aggregate_count_drop' else '')
        lines.append(f'- {entry["id"]} {entry["kind"]} — {entry.get("provider",entry.get("audit_reference"))}: {metric}.{context} {entry["note"]}')
    if not data['alerts']:lines.append('No qualified alerts in the supplied evidence; not proof of unchanged real-world SEO.')
    lines.extend(['','## Suppressed comparisons',''])
    for item in data['suppressed_comparisons']:
        lines.append(f'- {item["source"]}: {item["reason"]}')
    if not data['suppressed_comparisons']:lines.append('None')
    lines.extend(['','## Limitations','']+[f'- {x}' for x in data['limitations']]+[''])
    return '\n'.join(lines)


def main(argv=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history-dir',type=Path,default=None)
    parser.add_argument('--id',type=int,help='Optional current snapshot ID; previous is the immediately preceding ID')
    parser.add_argument('--as-of',type=str,help='UTC comparison date YYYY-MM-DD, default today UTC')
    parser.add_argument('--max-age-days',type=int,default=14)
    parser.add_argument('--min-baseline',type=int,default=20)
    parser.add_argument('--min-absolute-drop',type=int,default=10)
    parser.add_argument('--drop-percent',type=float,default=30.)
    parser.add_argument('--confirm-history-same-property',action='store_true')
    parser.add_argument('--confirm-same-page-set',action='store_true')
    parser.add_argument('--format',choices=('json','markdown'),default='json')
    args=parser.parse_args(argv)
    try:
        as_of=_day(args.as_of) if args.as_of else datetime.now(timezone.utc).date()
        record,prior=_load_two(args.history_dir or default_history_dir(),current_id=args.id)
        result=evaluate(record,prior,as_of=as_of,max_age_days=args.max_age_days,
            min_baseline=args.min_baseline,min_absolute_drop=args.min_absolute_drop,
            drop_percent=args.drop_percent,
            confirm_history_same_property=args.confirm_history_same_property,
            confirm_same_page_set=args.confirm_same_page_set)
        print(json.dumps(result,ensure_ascii=False,indent=2) if args.format=='json' else _markdown(result))
        return 0
    except (ReportInputError,OSError,sqlite3.Error,ValueError):
        print(json.dumps({'status':'error','reason':'History unavailable, malformed, or policy checks failed',
                          'network_requests':0,'notifications_sent':0}))
        return 2


if __name__=='__main__':raise SystemExit(main())
