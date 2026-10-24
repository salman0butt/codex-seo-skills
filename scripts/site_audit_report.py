#!/usr/bin/env python3
"""Offline multi-page SEO handoff from a saved bounded site_audit JSON.

Never fetches URLs, accesses credentials or copies page titles, descriptions,
paths, query tokens, untrusted HTML or raw findings into the output. Pages are
referenced by ordered audit indices which the operator can map privately.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
from urllib.parse import urlsplit

MAX_FILE_BYTES = 256 * 1024
MAX_PAGES = 12
MAX_REQUESTS = 37
CORE_FINDINGS = {
    'missing-title':('high','Create a descriptive, unique HTML title','Inspect page title in saved HTML and verified rendered DOM'),
    'missing-meta-description':('medium','Write a page-specific meta description','Inspect the rendered description in context'),
    'missing-h1':('medium','Add a visible descriptive H1','Check raw source and rendered desktop/mobile DOM'),
    'long-title-review':('review','Review title clarity and search intent','Check title on mobile search-preview widths'),
    'image-alt-missing':('review','Review alt attributes on informative images','Check image context and accessibility tree'),
    'noindex-review':('review','Confirm whether noindex is intentional','Validate directives with the site owner'),
    'canonical-review':('review','Review page canonical strategy','Verify canonical URL with the site owner'),
}
CROSS_FINDINGS = {
    'shared-title-review':('review','Review repeated titles across sampled pages','Confirm page intent and unique title strategy; duplicate text may be intentional'),
    'shared-description-review':('review','Review repeated descriptions across sampled pages','Check intended search snippets; repetition may be intentional'),
}


class EvidenceError(ValueError):
    """Constant, privacy-safe error messages for untrusted stored evidence."""


def read_source(path:Path) -> dict:
    try:
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            raise EvidenceError('Evidence file missing or larger than 256 KiB')
        contents=path.read_bytes()
        if len(contents)>MAX_FILE_BYTES:
            raise EvidenceError('Evidence exceeds size limit')
        data=json.loads(contents)
        if not isinstance(data,dict):
            raise EvidenceError('Expected an evidence JSON object')
        return data
    except (OSError,UnicodeError,ValueError) as exc:
        if isinstance(exc,EvidenceError):raise
        raise EvidenceError('Unreadable or malformed evidence JSON') from None


def _stamp(raw)->str:
    if not isinstance(raw,str) or len(raw)>40:
        raise EvidenceError('Invalid evidence timestamp')
    try:
        d=datetime.fromisoformat(raw.replace('Z','+00:00'))
        if d.tzinfo is None:raise ValueError()
        return d.isoformat(timespec='seconds')
    except ValueError:
        raise EvidenceError('Invalid evidence timestamp') from None


def _value(raw, *, max_len:int)->str|None:
    if raw is None:return None
    if not isinstance(raw,str) or len(raw)>max_len:
        raise EvidenceError('Invalid source observation value')
    # Normalize case and whitespace for equality only. Never output the value.
    return ' '.join(raw.split()).casefold() or None


def _normalize(source:dict)->list[dict]:
    if (source.get('schema_version') != 1 or
        source.get('scope') != 'bounded-same-origin-static-html-crawl' or
        source.get('robots_status') != 'checked_and_seed_allowed' or
        source.get('outcome') not in ('observations_only','partial') or
        source.get('seo_score','unexpected') is not None):
        raise EvidenceError('Unsupported or unsuccessful site audit')
    if type(source.get('page_limit')) is not int or not (1<=source['page_limit']<=MAX_PAGES):
        raise EvidenceError('Invalid site audit page budget')
    pages=source.get('pages')
    if not isinstance(pages,list) or not 1<=len(pages)<=source['page_limit']:
        raise EvidenceError('Invalid site audit page count')
    if (type(source.get('network_requests')) is not int or
            not len(pages)+1<=source['network_requests']<=MAX_REQUESTS):
        raise EvidenceError('Invalid recorded request count')
    _stamp(source.get('started_at_utc'))
    try:
        root=urlsplit(source['origin'])
        seed=urlsplit(source['seed'])
        if (root.scheme not in ('https','http') or not root.hostname or
            root.username or root.password or root.query or root.fragment or root.path!='/' or
            seed.scheme!=root.scheme or seed.netloc!=root.netloc or
            seed.query or seed.fragment or len(str(source['origin']))>350):
            raise ValueError()
    except (ValueError,KeyError,TypeError):
        raise EvidenceError('Invalid site audit origin') from None
    seen=set(); safe=[]
    for idx,item in enumerate(pages,1):
        if not isinstance(item,dict):
            raise EvidenceError('Invalid page audit entry')
        try:
            url=urlsplit(item['url'])
            if (url.scheme!=root.scheme or url.netloc!=root.netloc or
                    url.username or url.password or url.query or url.fragment or
                    len(item['url'])>600 or not url.path.startswith('/') or
                    item['url'] in seen):
                raise ValueError()
            seen.add(item['url'])
        except (ValueError,TypeError,KeyError):
            raise EvidenceError('Unexpected or duplicate page URL') from None
        status=item.get('http_status')
        if type(status) is not int or not 100<=status<=599:
            raise EvidenceError('Invalid response status')
        ref=f'page-{idx}'
        if status!=200 or item.get('outcome')=='not_html':
            if item.get('outcome') not in ('not_html','not_evaluated') or item.get('findings')!=[]:
                raise EvidenceError('Inconsistent unevaluated page entry')
            safe.append({'reference':ref,'status':status,'evaluated':False,'findings':[],
                         'title':None,'description':None})
            continue
        if (item.get('schema_version')!=1 or item.get('scope')!='single-page-raw-html' or
            item.get('outcome')!='observations-only; no SEO rankings or indexation claim' or
            item.get('seo_score','unexpected') is not None):
            raise EvidenceError('Unexpected static page audit schema')
        _stamp(item.get('observed_at_utc'))
        observations=item.get('observations')
        if not isinstance(observations,dict):
            raise EvidenceError('Missing page observations')
        title=_value(observations.get('title'),max_len=180)
        description=_value(observations.get('meta_description'),max_len=350)
        raw_findings=item.get('findings')
        if not isinstance(raw_findings,list) or len(raw_findings)>40:
            raise EvidenceError('Invalid page findings')
        ids=set()
        for finding in raw_findings:
            if not isinstance(finding,dict) or finding.get('id') not in CORE_FINDINGS:
                raise EvidenceError('Unknown page finding type')
            ids.add(finding['id'])
        if (not title) != ('missing-title' in ids) or (not description) != ('missing-meta-description' in ids):
            raise EvidenceError('Contradictory title or description evidence')
        safe.append({'reference':ref,'status':status,'evaluated':True,
                     'findings':sorted(ids),'title':title,'description':description})
    return safe


def build_report(source:dict)->dict:
    safe=_normalize(source)
    counts=Counter(id_ for page in safe for id_ in page['findings'])
    tasks=[]
    for page in safe:
        for issue in page['findings']:
            priority,action,verification=CORE_FINDINGS[issue]
            tasks.append({'issue_id':issue,'priority':priority,'page_references':[page['reference']],
                          'recommended_action':action,'verification':verification,
                          'change_authorized':False})
    for issue,field in (('shared-title-review','title'),('shared-description-review','description')):
        repeated=defaultdict(list)
        for page in safe:
            if page['evaluated'] and page[field]:
                repeated[page[field]].append(page['reference'])
        for refs in repeated.values():
            if len(refs)<2:continue
            priority,action,verification=CROSS_FINDINGS[issue]
            tasks.append({'issue_id':issue,'priority':priority,'page_references':refs,
                          'recommended_action':action,'verification':verification,
                          'change_authorized':False})
            counts[issue]+=1
    order={'high':0,'medium':1,'review':2}
    tasks.sort(key=lambda x:(order[x['priority']],x['issue_id'],x['page_references']))
    return {'schema_version':1,'scope':'offline-bounded-site-audit-handoff',
        'source_scope':'bounded-same-origin-static-html-crawl',
        'source_authenticity':'unverified_saved_JSON',
        'network_requests':0,'notifications_sent':0,'site_changes_made':0,
        'page_paths_included':False,'titles_or_descriptions_included':False,
        'source_outcome':source['outcome'],'pages_recorded':len(safe),
        'pages_evaluated':sum(p['evaluated'] for p in safe),
        'pages_not_evaluated':sum(not p['evaluated'] for p in safe),
        'finding_counts':dict(sorted(counts.items())),
        'handoff_tasks':tasks,'page_references':[p['reference'] for p in safe],
        'limitations':['Only sampled static HTML from one previously saved, operator-provided source.',
            'Page references map to the corresponding entries in the original PRIVATE input file.',
            'Repeated titles and descriptions are advisory; neither is automatically an SEO error.',
            'No live website, private account, ranking, indexing or traffic was examined.',
            'No external request, notification, or website edit was made.']}


def markdown_report(report:dict)->str:
    lines=['# Bounded site SEO developer handoff','',
        f'Source: {report["source_scope"]} ({report["source_outcome"]}); authenticity not independently verified.',
        f'Pages recorded: {report["pages_recorded"]}; static HTML evaluated: {report["pages_evaluated"]}.',
        'No network requests, changes, messages or private provider reads.','',
        '## Validated findings in the saved sample','']
    for key,count in report['finding_counts'].items():lines.append(f'- {key}: {count}')
    if not report['finding_counts']:lines.append('No checklist findings; this is NOT evidence of SEO health.')
    lines.extend(['','## Advisory developer tasks',''])
    for task in report['handoff_tasks']:
        lines += [f'### {task["issue_id"]} ({task["priority"]})',
            'Evidence references: '+', '.join(task['page_references']),
            'Suggestion: '+task['recommended_action'],
            'Verification: '+task['verification'],
            'Status: unapproved; no change performed','']
    if not report['handoff_tasks']:lines.append('No advisory changes proposed from this limited evidence.')
    lines.extend(['','## Limitations','']+['- '+x for x in report['limitations']]+[''])
    return '\n'.join(lines)


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-audit',type=Path,required=True,help='Saved site_audit.py JSON; never fetched here')
    parser.add_argument('--format',choices=('markdown','json'),default='markdown')
    args=parser.parse_args(argv)
    try:
        obj=read_source(args.site_audit)
        report=build_report(obj)
        print(markdown_report(report) if args.format=='markdown' else json.dumps(report,indent=2,ensure_ascii=False))
        return 0
    except EvidenceError as exc:
        print(json.dumps({'status':'error','reason':str(exc),'network_requests':0}),file=__import__('sys').stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
