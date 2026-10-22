#!/usr/bin/env python3
"""Compose offline evidence reports from codex-seo private and quick-audit JSON.

No provider requests, token reads, credential refresh, writes to websites, or
paid APIs. Inputs are treated as UNTRUSTED supplied files: schemas are checked,
provenance cannot be proven, and arbitrary content is not carried into output.

  codex-seo run seo_report_builder.py --gsc-current current-gsc.json --ga4-current current-ga4.json --format markdown
  codex-seo run seo_report_builder.py --gsc-current now.json --gsc-previous before.json --confirm-same-property --format json
  codex-seo run seo_report_builder.py --quick-audit page.json --output handoff.md
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit

MAX_INPUT_BYTES = 256 * 1024
MAX_QUICK_AUDITS = 10
COUNT_KEYS = {
    'gsc': ('clicks', 'impressions'),
    'ga4': ('organic_search_sessions', 'organic_search_total_users', 'organic_search_engaged_sessions'),
}
METRICS = {'gsc': COUNT_KEYS['gsc'] + ('ctr_percent', 'average_position'), 'ga4': COUNT_KEYS['ga4']}
ISSUES = {
    'missing-title': ('high', 'Add a descriptive page title', 'The static HTML has one useful, nonempty <title> element.', 'Inspect the HTML title after deployment.'),
    'missing-meta-description': ('medium', 'Write a page-specific description', 'The intended page includes a concise meta description.', 'Inspect the rendered page and meta description.'),
    'missing-h1': ('medium', 'Add a visible, descriptive H1', 'A descriptive visible H1 appears in source or verified rendered DOM.', 'Inspect source and rendered DOM at mobile/desktop sizes.'),
    'long-title-review': ('review', 'Review page title length and intent', 'Title intent and readability have been reviewed on mobile SERP preview.', 'Review the title in context; truncation is pixel-width dependent.'),
    'image-alt-missing': ('review', 'Review informative image alt attributes', 'Informative images have meaningful alt text; decorative images use alt="".', 'Inspect image context and accessibility tree.'),
    'noindex-review': ('review', 'Confirm page noindex intent', 'Product/content owner confirms intended indexability; unintended noindex is corrected.', 'Inspect robots directives and verify owner signoff.'),
    'canonical-review': ('review', 'Review canonical URL strategy', 'Canonical intent is documented and duplicates consistently point to the preferred URL.', 'Inspect canonical tags and site routing.'),
}


class ReportInputError(ValueError):
    """Input rejected. User-facing error text must contain no raw file data."""


def _read_json(path: Path) -> dict:
    try:
        if not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
            raise ReportInputError('Input missing, inaccessible or over 256 KiB')
        obj = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(obj, dict):
            raise ReportInputError('Expected a top-level JSON object')
        return obj
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, ReportInputError):
            raise
        raise ReportInputError('Invalid or unreadable JSON input') from None


def _num(value, minval=0, maxval=1e12) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and minval <= value <= maxval)


def _day(raw) -> date:
    if not isinstance(raw, str) or len(raw) != 10:
        raise ReportInputError('Date must be ISO YYYY-MM-DD')
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ReportInputError('Invalid date range') from None


def _normalize_source(obj: dict, service: str) -> dict:
    if obj.get('schema_version') != 1 or obj.get('service') != service or obj.get('scope') != 'aggregate-only':
        raise ReportInputError('Unexpected report schema or service')
    status = obj.get('result')
    if status not in ('verified', 'no_data', 'rate_limited', 'permission_or_quota_denied',
                      'authentication_required', 'credentials_unavailable', 'network_or_dependency_error',
                      'blocked', 'explicit_account_read_required', 'property_required_or_invalid'):
        raise ReportInputError('Unsupported provider report status')
    if obj.get('live_verified') is not (status == 'verified'):
        raise ReportInputError('Provider report evidence status is inconsistent')
    if obj.get('read_only') is not True or obj.get('property_identifier_redacted') is not True:
        raise ReportInputError('Report privacy or access contract is missing')
    if status in ('verified', 'no_data') and (obj.get('http_status') != 200 or obj.get('network_requests') != 1):
        raise ReportInputError('Provider report HTTP evidence is inconsistent')
    metrics = obj.get('metrics')
    if not isinstance(metrics, dict):
        raise ReportInputError('Missing provider metrics container')
    if status == 'verified':
        if any(not _num(metrics.get(k), maxval=100 if k == 'ctr_percent' else 1e12)
               for k in METRICS[service]):
            raise ReportInputError('Missing or invalid reported metrics')
        if service == 'ga4' and any(not isinstance(metrics[k], int) for k in METRICS[service]):
            raise ReportInputError('GA4 aggregate counts must be integer values')
        if service == 'gsc' and any(not isinstance(metrics[k], int) for k in COUNT_KEYS[service]):
            raise ReportInputError('GSC counts must be integer values')
        safe_metrics = {k: metrics[k] for k in METRICS[service]}
    else:
        if metrics:
            raise ReportInputError('Blocked or unavailable report cannot include measured metrics')
        safe_metrics = {}
    dates = obj.get('date_range')
    if status in ('verified', 'no_data'):
        if not isinstance(dates, dict) or not isinstance(dates.get('days'), int) or isinstance(dates.get('days'), bool):
            raise ReportInputError('Missing reporting date range')
        count = dates['days']
        start = _day(dates.get('start'))
        end = _day(dates.get('end'))
        if not (1 <= count <= 90) or start > end or (end - start).days != count - 1:
            raise ReportInputError('Inconsistent reporting window')
        safe_dates = {'start': start.isoformat(), 'end': end.isoformat(), 'days': count}
    else:
        safe_dates = None
    return {'service':service,'status':status,'reported_as_verified':status == 'verified',
            'metrics':safe_metrics,'date_range':safe_dates}


def _normalize_quick(obj: dict) -> dict:
    if (obj.get('schema_version') != 1 or obj.get('scope') != 'single-page-raw-html'
            or obj.get('http_status') != 200 or not str(obj.get('outcome','')).startswith('observations-only')):
        raise ReportInputError('Unsupported, unsuccessful, or blocked quick audit')
    try:
        parts = urlsplit(obj.get('url', ''))
        if (parts.scheme not in ('http','https') or not parts.hostname or parts.username
                or parts.password or parts.port or parts.query or parts.fragment):
            raise ValueError()
        hostname = parts.hostname
        if len(hostname) > 253 or not all(c.isascii() for c in hostname):
            raise ValueError()
        origin = parts.scheme + '://' + hostname + '/'
    except (ValueError, TypeError):
        raise ReportInputError('Invalid public page origin') from None
    observed = obj.get('observed_at_utc')
    if not isinstance(observed,str) or len(observed) > 40:
        raise ReportInputError('Missing observation timestamp')
    try:
        moment = datetime.fromisoformat(observed.replace('Z','+00:00'))
        if moment.tzinfo is None:
            raise ValueError()
    except ValueError:
        raise ReportInputError('Invalid observation timestamp') from None
    issues = obj.get('findings')
    if not isinstance(issues,list) or len(issues) > 100:
        raise ReportInputError('Invalid page finding list')
    issue_ids = []
    for entry in issues:
        if not isinstance(entry,dict) or entry.get('id') not in ISSUES:
            raise ReportInputError('Unexpected page finding identifier')
        if entry['id'] not in issue_ids:
            issue_ids.append(entry['id'])
    return {'scope':'single-page-raw-html','page_origin':origin,
            'page_path_redacted':True,'observed_at_utc':moment.isoformat(timespec='seconds'),
            'finding_ids':sorted(issue_ids)}


def _comparison(current: dict, previous: dict | None, attested: bool) -> dict:
    base = {'status':'no_previous_report', 'metrics':{},
            'note':'No baseline report supplied; trends cannot be calculated.'}
    if previous is None:
        return base
    if not attested:
        return {'status':'property_identity_not_attested','metrics':{},
                'note':'Inputs redact property IDs. Use --confirm-same-property only after checking both exports belong to the same property.'}
    if current['status'] != 'verified' or previous['status'] != 'verified':
        return {'status':'metrics_unavailable','metrics':{},'note':'Both reporting periods must contain verified metrics.'}
    cur, prv = current['date_range'], previous['date_range']
    if cur['days'] != prv['days'] or _day(prv['end']) + timedelta(days=1) != _day(cur['start']):
        return {'status':'nonadjacent_or_unequal_windows','metrics':{},
                'note':'Comparisons require adjacent nonoverlapping equal-length windows.'}
    diffs = {}
    for key in METRICS[current['service']]:
        now, then = current['metrics'][key], previous['metrics'][key]
        delta = round(now - then, 4)
        diffs[key] = {'current':now,'previous':then,'absolute_change':delta,
                      'relative_change_percent':round(100 * delta / then, 2) if key in COUNT_KEYS[current['service']] and then != 0 else None,
                      'units':'percentage_points' if key == 'ctr_percent' else ('average_position_units' if key == 'average_position' else 'count'),
                      'interpretation':'direction_only_not_rank_causality' if key == 'average_position' else 'period_difference_only'}
    return {'status':'compared_with_operator_attestation','metrics':diffs,
            'note':'Operator attested to same-property identity; not independently proven. Changes are descriptive, not causal.'}


def compose(inputs: dict, *, confirm_same_property: bool=False) -> dict:
    if not isinstance(inputs, dict):
        raise ReportInputError('Invalid report inputs')
    if not any(inputs.values()):
        raise ReportInputError('Supply at least one current provider report or quick audit')
    out = {'schema_version':1,'scope':'offline-composite-evidence-report',
           'generated_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
           'network_requests':0,'source_validation':'shape and content validated; input authenticity not independently verified',
           'private_property_identifiers_included':False,'provider_reports':{},'page_audits':[],
           'handoff_tasks':[], 'limitations':[
               'Source JSON is supplied by the operator; schema validation does not authenticate its provenance.',
               'GSC web search clicks and GA4 organic sessions are different measurements and are never summed or equated.',
               'A period-over-period change alone does not prove a cause, ranking improvement, or statistical significance.',
               'Raw HTML audits are not site-wide rendered DOM audits or Core Web Vitals tests.',
               'No API call, indexing submission, website edit or credential refresh was performed.',
           ]}
    for service in ('gsc','ga4'):
        curr = inputs.get(service+'_current')
        prv = inputs.get(service+'_previous')
        if prv is not None and curr is None:
            raise ReportInputError('A previous period requires its matching current provider report')
        if curr is None:
            continue
        current = _normalize_source(curr,service)
        previous = _normalize_source(prv,service) if prv is not None else None
        out['provider_reports'][service] = {'current':current,
            'previous_date_range':previous['date_range'] if previous else None,
            'comparison':_comparison(current,previous,confirm_same_property)}
    quicks = inputs.get('quick_audits') or []
    if not isinstance(quicks,list) or len(quicks)>MAX_QUICK_AUDITS:
        raise ReportInputError('At most 10 page audits allowed')
    for index, doc in enumerate(quicks, 1):
        normalized = _normalize_quick(doc)
        normalized['audit_reference'] = f'audit-{index}'
        out['page_audits'].append(normalized)
        for issue in normalized['finding_ids']:
            priority, action, acceptance, verification = ISSUES[issue]
            out['handoff_tasks'].append({'issue_id':issue,'priority':priority,
                'source_scope':'single-page-raw-html','page_origin':normalized['page_origin'],
                'audit_reference':normalized['audit_reference'],
                'page_path_redacted':True,'source_observed_at_utc':normalized['observed_at_utc'],
                'evidence':'Static source audit reported finding '+issue,
                'recommended_action':action,'acceptance_criteria':acceptance,
                'verification':verification,'owner':'To assign',
                'rollback':'Revert only the scoped change if regression is confirmed; validate before deployment.',
                'change_authorized':False})
    order={'high':0,'medium':1,'review':2}
    out['handoff_tasks'].sort(key=lambda x:(order[x['priority']],x['issue_id'],x['page_origin']))
    return out


def _markdown(out:dict) -> str:
    lines=['# Codex SEO evidence report','',
        'Generated (UTC): '+out['generated_utc'],
        'Source provenance: '+out['source_validation'],
        'Scope: offline report composition; zero external requests','',
        '## Provider metrics','']
    if not out['provider_reports']:
        lines.append('No supplied provider reports. No traffic or ranking result inferred.')
    for service,item in out['provider_reports'].items():
        c = item['current']
        lines.extend(['### '+service.upper(), '','Status: '+c['status']])
        if c['date_range']:
            d=c['date_range']
            lines.append('Window: '+d['start']+' to '+d['end']+' ('+str(d['days'])+' days)')
        if c['status']=='verified':
            lines.extend('- '+k+': '+str(c['metrics'][k]) for k in METRICS[service])
        elif c['status']=='no_data':
            lines.append('No provider rows returned; this does not establish zero traffic.')
        else:
            lines.append('Metrics unavailable. No values inferred.')
        cmp=item['comparison']
        lines.extend(['','Comparison: '+cmp['status'],cmp['note']])
        if cmp['status']=='compared_with_operator_attestation':
            lines.extend('- '+k+': '+str(v['absolute_change'])+' '+v['units']+
                         (' ('+str(v['relative_change_percent'])+'%)' if v['relative_change_percent'] is not None else '')
                         for k,v in cmp['metrics'].items())
        lines.append('')
    lines.extend(['## Page audit findings',''])
    if not out['page_audits']:
        lines.append('No page audit supplied; no site health claims made.')
    for page in out['page_audits']:
        lines.append('- '+page['audit_reference']+': '+page['page_origin']+' — '+str(len(page['finding_ids']))+
                     ' static-HTML finding(s); path redacted; observed '+page['observed_at_utc'])
    lines.extend(['','## Developer handoff tasks',''])
    if not out['handoff_tasks']:
        lines.append('No validated page findings to hand off; this does not certify SEO health.')
    for task in out['handoff_tasks']:
        lines.extend(['### '+task['issue_id']+' ('+task['priority']+')',
                      'Source: '+task['audit_reference']+' (corresponding input JSON in command order)',
                      'Scope: '+task['page_origin']+' (path redacted)',
                      'Evidence: '+task['evidence'],
                      'Suggested change: '+task['recommended_action'],
                      'Acceptance: '+task['acceptance_criteria'],
                      'Verification: '+task['verification'],
                      'Owner: '+task['owner'],
                      'Authorization: advisory only; no change made',''])
    lines.extend(['## Limitations',''])
    lines.extend('- '+x for x in out['limitations'])
    lines.append('')
    return '\n'.join(lines)


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    for service in ('gsc','ga4'):
        for period in ('current','previous'):
            parser.add_argument('--'+service+'-'+period,type=Path)
    parser.add_argument('--quick-audit',type=Path,action='append',default=[],help='One raw-HTML audit JSON (repeat up to 10 times)')
    parser.add_argument('--confirm-same-property',action='store_true',help='Attest that previous/current exports for each provider belong to the same property; cannot be proven from redacted reports')
    parser.add_argument('--format',choices=('markdown','json'),default='markdown')
    parser.add_argument('--output',type=Path,help='Optional local report path; never uploads anything')
    parser.add_argument('--overwrite',action='store_true',help='Explicitly replace a preexisting output file')
    args=parser.parse_args(argv)
    paths={service+'_'+period:getattr(args,service+'_'+period) for service in ('gsc','ga4') for period in ('current','previous')}
    if not any(paths.values()) and not args.quick_audit:
        parser.error('Supply a current report or a --quick-audit file')
    if len(args.quick_audit)>MAX_QUICK_AUDITS:
        parser.error('Maximum 10 quick audits')
    try:
        input_paths=[p for p in [*paths.values(),*args.quick_audit] if p]
        if args.output and any(p.resolve()==args.output.resolve() for p in input_paths):
            raise ReportInputError('Output may not overwrite an input file')
        objects={k:_read_json(p) if p else None for k,p in paths.items()}
        objects['quick_audits']=[_read_json(p) for p in args.quick_audit]
        out=compose(objects,confirm_same_property=args.confirm_same_property)
        payload=(json.dumps(out,indent=2,ensure_ascii=False) if args.format=='json' else _markdown(out))+'\n'
        if args.output:
            target=args.output
            if not target.parent.is_dir():
                raise ReportInputError('Output parent directory does not exist')
            if target.exists() and not args.overwrite:
                raise ReportInputError('Output exists; pass --overwrite to replace it')
            if target.is_symlink():
                raise ReportInputError('Output symlink is not allowed')
            # Atomic output; do not leave partial reports and do not replace an input.
            fd,tmp=tempfile.mkstemp(prefix='.seo-evidence-',dir=target.parent)
            try:
                os.fchmod(fd,0o600)
                with os.fdopen(fd,'w',encoding='utf-8') as handle:
                    handle.write(payload)
                os.replace(tmp,target)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
            print('Offline report saved locally',file=sys.stderr)
        else:
            print(payload,end='')
        return 0
    except ReportInputError as exc:
        print('SEO report input rejected: '+str(exc),file=sys.stderr)
        return 2
    except OSError:
        print('SEO report file operation failed',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
