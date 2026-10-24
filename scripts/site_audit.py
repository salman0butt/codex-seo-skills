#!/usr/bin/env python3
"""Consent-gated, robots-respecting small public-site SEO crawl.

Only public HTML, one origin, strict page/request/byte budgets. No login,
private accounts, hidden forms, sitemap enumeration, browser, paid API,
mutations, telemetry, or claims of search indexing/rankings.
"""
from __future__ import annotations

import argparse
from collections import deque
from typing import Callable
from datetime import datetime, timezone
import json
import re
import sys
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

MAX_PAGES = 12
MAX_LINKS_QUEUED = 120
MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_ROBOTS_BYTES = 128 * 1024
MAX_REDIRECTS = 2
MAX_REQUESTS = 1 + MAX_PAGES * (MAX_REDIRECTS + 1)
USER_AGENT = 'CodexSEO-SiteAudit/1.1 (+read-only; robots-respecting)'
SKIP_PATH = re.compile(r'(?i)(?:^|/)(?:wp-admin|admin|login|log-in|logout|signin|sign-in|signup|register|my-account|account|checkout|cart|search|api)(?:/|$)')
SKIP_EXT = re.compile(r'(?i)\.(?:pdf|xml|json|csv|jpg|jpeg|png|gif|webp|svg|zip|tar|gz|rar|mp4|mp3|webm|ico|css|js|woff2?|ttf|eot)$')


class CrawlBlocked(Exception):
    """No further requests should be sent."""


def origin(url: str) -> tuple[str,str,int]:
    parts=urlsplit(url)
    if parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.password:
        raise CrawlBlocked('Unsupported URL origin')
    try:
        port=parts.port or (443 if parts.scheme=='https' else 80)
    except ValueError:
        raise CrawlBlocked('Invalid URL port') from None
    return parts.scheme,parts.hostname.lower().rstrip('.'),port


def candidate(url: str, root:tuple[str,str,int], *, seed:bool=False) -> str|None:
    """Return a normalized same-origin public HTML path, never a query URL."""
    try:
        parts=urlsplit(url)
        if (origin(url)!=root or parts.query or parts.fragment or len(url)>600 or
                len(parts.path)>350 or not (parts.path or '/').startswith('/') or
                '\\' in url or any(ord(x)<32 for x in url)):
            return None
        path=parts.path or '/'
        if SKIP_PATH.search(path) or SKIP_EXT.search(path):
            return None
        # Never normalize percent-escaped slashes/dot-segments (ambiguous
        # routing across proxies). This also prevents encoded query delimiters.
        if re.search(r'(?i)%(?:2f|5c|3f|23|00|2e)',path):
            return None
        if any(segment in ('.','..') for segment in path.split('/')):
            return None
        netloc=root[1]
        if ':' in netloc: netloc='['+netloc+']'
        if root[2] != (443 if root[0]=='https' else 80):
            netloc+=f':{root[2]}'
        return urlunsplit((root[0],netloc,path,'',''))
    except (ValueError,CrawlBlocked):
        return None


def _fetch_once(url:str, *, max_bytes:int, request_counter:list[int]) -> dict:
    """One individually DNS-validated/pinned GET without automatic redirects."""
    from url_safety import safe_requests_get, read_bounded, decode_body, URLSafetyError
    import requests
    if request_counter[0]>=MAX_REQUESTS:
        raise CrawlBlocked('Request budget exhausted')
    request_counter[0]+=1
    try:
        with safe_requests_get(url,timeout=(5,12),allow_redirects=False,stream=True,
                               headers={'User-Agent':USER_AGENT, 'Accept':'text/html,text/plain;q=0.8'}) as response:
            status=response.status_code
            location=response.headers.get('Location','')
            typ=response.headers.get('Content-Type','')[:100]
            if status in (301,302,303,307,308):
                return {'status':status,'location':location,'content':None,'type':typ}
            if status!=200:
                return {'status':status,'location':None,'content':None,'type':typ}
            raw,too_large=read_bounded(response,max_bytes)
            if too_large:raise CrawlBlocked('Response exceeded byte budget')
            return {'status':status,'location':None,'content':decode_body(raw,typ),'type':typ}
    except (URLSafetyError,requests.RequestException,UnicodeError,LookupError,ValueError) as exc:
        # Never echo exception text: it can contain URL path/query secrets.
        raise CrawlBlocked('DNS-validated request failed: '+type(exc).__name__) from None


def fetch(url:str,root:tuple[str,str,int], *,max_bytes:int, counter:list[int],
          request_gap:float=1.0, pacer:list[float|None]|None=None, sleep=time.sleep,
          clock=time.monotonic, can_fetch:Callable[[str],bool]|None=None) -> dict:
    current=url
    for redirects in range(MAX_REDIRECTS+1):
        if can_fetch is not None and not can_fetch(current):
            raise CrawlBlocked('robots.txt denied URL or redirect target')
        if pacer is not None and pacer[0] is not None:
            remaining=request_gap-(clock()-pacer[0])
            if remaining>0: sleep(remaining)
        if pacer is not None: pacer[0]=clock()
        result=_fetch_once(current,max_bytes=max_bytes,request_counter=counter)
        if result['status'] not in (301,302,303,307,308):
            result['final_url']=current
            return result
        if redirects>=MAX_REDIRECTS:raise CrawlBlocked('Redirect budget exhausted')
        destination=urljoin(current,result['location'])
        next_url=candidate(destination,root)
        if next_url is None:raise CrawlBlocked('Redirect escaped same-origin public HTML policy')
        current=next_url
    raise CrawlBlocked('Redirect budget exhausted')


def _robot_policy(seed:str,root:tuple[str,str,int],counter:list[int],pacer:list,
                  *,sleep=time.sleep,clock=time.monotonic) -> tuple[RobotFileParser,float]:
    robot=urlunsplit((root[0],urlsplit(seed).netloc,'/robots.txt','',''))
    # A missing/blocked/ambiguous robots.txt is not consent to crawl.
    result=fetch(robot,root,max_bytes=MAX_ROBOTS_BYTES,counter=counter,
                 pacer=pacer,sleep=sleep,clock=clock)
    if result['status']!=200 or not result['type'].lower().startswith('text/plain'):
        raise CrawlBlocked('robots.txt is unavailable or not text/plain; crawl refused')
    if not re.search(r'(?im)^\s*user-agent\s*:',result['content']):
        raise CrawlBlocked('robots.txt contains no interpretable user-agent policy')
    policy=RobotFileParser()
    policy.set_url(robot)
    policy.parse(result['content'].splitlines())
    if not policy.can_fetch(USER_AGENT,seed):
        raise CrawlBlocked('robots.txt denies the seed URL')
    crawl_delay=policy.crawl_delay(USER_AGENT) or 0
    if crawl_delay>30:raise CrawlBlocked('robots.txt crawl delay exceeds permitted 30-second budget')
    return policy,max(1.0,float(crawl_delay))


def crawl(seed:str, *, allow_live:bool=False, max_pages:int=5,
          max_bytes:int=MAX_HTML_BYTES, sleep=time.sleep,clock=time.monotonic)->dict:
    base={
        'schema_version':1,'scope':'bounded-same-origin-static-html-crawl',
        'started_at_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'page_limit':max_pages,'network_requests':0,'pages':[],
        'robots_status':'not_checked','stop_reason':None,'seo_score':None,
        'not_measured':['Entire site or sitemap coverage','JavaScript-rendered DOM',
                        'Search rankings, indexing status or Search Console data',
                        'Core Web Vitals and user analytics','Private or login-protected pages'],
    }
    if not allow_live:
        return {**base,'outcome':'blocked','stop_reason':'Explicit --live --allow-public-crawl required; no requests made'}
    if type(max_pages) is not int or not 1<=max_pages<=MAX_PAGES or type(max_bytes) is not int or not 1<=max_bytes<=MAX_HTML_BYTES:
        return {**base,'outcome':'blocked','stop_reason':'Page or byte budget outside allowed limits'}
    try:
        root=origin(seed)
        clean=candidate(seed,root,seed=True)
        if clean is None:raise CrawlBlocked('Seed must be a query-free same-origin public HTML path')
        from url_safety import validate_url_strict, is_safe_ip
        normalized,pinned=validate_url_strict(clean)
        # Unlike single-page staging probes, this multi-page public crawler
        # never opts in to private hosts even through LOCAL_TARGETS.
        if not is_safe_ip(pinned):
            raise CrawlBlocked('Only publicly routable hosts are allowed')
        clean=candidate(normalized,root)
        if clean is None:raise CrawlBlocked('Seed URL did not pass public URL policy')
        base['origin']=f'{root[0]}://{urlsplit(clean).netloc}/'
        base['seed']=clean
        queued=deque([clean]);seen={clean}
        counter=[0];pacer=[None]
        policy,gap=_robot_policy(clean,root,counter,pacer,sleep=sleep,clock=clock)
        from quick_audit import analyze_page, public_url
        from parse_html import parse_html
        base['robots_status']='checked_and_seed_allowed'
        skipped=0
        while queued and len(base['pages'])<max_pages:
            url=queued.popleft()
            if not policy.can_fetch(USER_AGENT,url):
                skipped+=1
                continue
            try:
                result=fetch(url,root,max_bytes=max_bytes,counter=counter,
                             request_gap=gap,pacer=pacer,sleep=sleep,clock=clock,
                             can_fetch=lambda dest:policy.can_fetch(USER_AGENT,dest))
            except CrawlBlocked as exc:
                base['stop_reason']=str(exc)
                break
            if result['status'] in (429,500,502,503,504):
                base['stop_reason']=f'HTTP {result["status"]}; stopped rather than retrying'
                break
            if result['status']!=200:
                base['pages'].append({'url':url,'http_status':result['status'],
                                      'outcome':'not_evaluated','findings':[]})
                continue
            if not ('text/html' in result['type'].lower() or 'application/xhtml+xml' in result['type'].lower()):
                base['pages'].append({'url':url,'http_status':result['status'],
                                      'outcome':'not_html','findings':[]})
                continue
            parsed=parse_html(result['content'],result['final_url'])
            # Canonical href is untrusted page content; unlike outbound links,
            # it is displayed as a finding. Remove query, fragment and
            # credentials rather than allowing embedded tokens into reports.
            if parsed.get('canonical'):
                proposed=urljoin(result['final_url'],str(parsed['canonical']))
                if urlsplit(proposed).scheme in ('http','https'):
                    parsed['canonical']=public_url(proposed)
                else:
                    parsed['canonical']=None
            report=analyze_page(result['final_url'],parsed)
            report['not_measured']=[x for x in report['not_measured'] if 'Site-wide crawl' not in x]
            base['pages'].append(report)
            for item in parsed.get('links',{}).get('internal',[])[:400]:
                if len(seen)>=MAX_LINKS_QUEUED:break
                dest=candidate(item.get('href',''),root)
                if dest is not None and dest not in seen:
                    seen.add(dest)
                    queued.append(dest)
        base['skipped_robots_paths']=skipped
        base['discovered_candidate_count']=len(seen)
        if not base['stop_reason']:
            base['stop_reason']='page_limit_reached' if queued else 'discovery_queue_empty'
        base['outcome']='partial' if base['stop_reason'] not in ('page_limit_reached','discovery_queue_empty') else 'observations_only'
    except (CrawlBlocked,ValueError) as exc:
        base['outcome']='blocked'
        base['stop_reason']=str(exc)
    finally:
        base['network_requests']=locals().get('counter',[0])[0]
    return base


def markdown_report(report:dict)->str:
    lines=['# Bounded public-site SEO observations','',
           f'Origin: {report.get("origin","not validated")}',
           f'Outcome: {report["outcome"]}; robots: {report["robots_status"]}',
           f'Requests: {report["network_requests"]}; pages recorded: {len(report["pages"])}',
           f'Stop: {report["stop_reason"]}', '',
           'These are static-HTML observations, not a site-wide completeness or ranking claim.','']
    for page in report['pages']:
        lines.append(f'## {page["url"]}')
        for finding in page.get('findings',[]):
            lines.append(f'- {finding["id"]}: {finding["evidence"]}')
        if not page.get('findings'):lines.append('- No checklist findings; coverage remains limited')
        lines.append('')
    return '\n'.join(lines)


def main(argv=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url',help='Public, query-free seed URL')
    parser.add_argument('--live',action='store_true',help='Permit public HTTP requests')
    parser.add_argument('--allow-public-crawl',action='store_true',help='Confirm explicit small crawl intent')
    parser.add_argument('--max-pages',type=int,default=5)
    parser.add_argument('--max-bytes',type=int,default=MAX_HTML_BYTES)
    parser.add_argument('--format',choices=['json','markdown'],default='json')
    args=parser.parse_args(argv)
    result=crawl(args.url,allow_live=args.live and args.allow_public_crawl,
                 max_pages=args.max_pages,max_bytes=args.max_bytes)
    print(markdown_report(result) if args.format=='markdown' else json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['outcome']=='observations_only' else 2


if __name__=='__main__':raise SystemExit(main())
