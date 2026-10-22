#!/usr/bin/env python3
"""Bounded, read-only single-page SEO audit with evidence and explicit unknowns.

No APIs, credentials, Google indexation claims, or site mutations. Only one
GET is made to the requested public page (and up to three HTTP redirects).
Uses url_safety for DNS validation/pinning and parse_html for observations.

Usage:
    codex-seo run quick_audit.py https://example.com/ --json
    codex-seo run quick_audit.py https://example.com/ --markdown
    codex-seo run quick_audit.py https://example.com/ --output report.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3


def public_url(url: str) -> str:
    """Strip query, fragment and credentials from anything printed to a report."""
    try:
        s = urlsplit(url)
        host = s.hostname or ''
        if ':' in host and not host.startswith('['):
            host = f'[{host}]'
        if s.port:
            host = f'{host}:{s.port}'
        return urlunsplit((s.scheme, host, s.path or '/', '', ''))
    except ValueError:
        return '[invalid URL]'


def _text(s: object, max_chars: int = 250) -> str:
    """Bound potentially untrusted HTML-derived strings in generated reports."""
    return re.sub(r'[\x00-\x1f\x7f]+', ' ', str(s or '')).strip()[:max_chars]


def fetch_html(url: str, *, max_bytes: int = MAX_BODY_BYTES) -> dict:
    """Fetch one public HTML page with a bounded response body and safe redirects."""
    from url_safety import DEFAULT_REQUEST_HEADERS, URLSafetyError, safe_requests_session, validate_url_strict
    import requests

    response = {'status_code': None, 'url': public_url(url), 'content': None, 'error': None, 'content_type': None}
    try:
        normalized, _ = validate_url_strict(url)
        with safe_requests_session(normalized) as session:
            session.max_redirects = MAX_REDIRECTS
            with session.get(normalized, headers=DEFAULT_REQUEST_HEADERS, timeout=(6, 18),
                             allow_redirects=True, stream=True) as result:
                response['url'] = public_url(result.url)
                response['status_code'] = result.status_code
                content_type = result.headers.get('Content-Type', '')
                response['content_type'] = _text(content_type, 120)
                if result.status_code != 200:
                    response['error'] = f'HTTP {result.status_code}; page HTML not evaluated'
                    return response
                if content_type and 'text/html' not in content_type.lower() and 'application/xhtml+xml' not in content_type.lower():
                    response['error'] = 'Resource is not HTML'
                    return response
                body = bytearray()
                for chunk in result.iter_content(chunk_size=65536):
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        response['error'] = f'HTML response exceeded limit of {max_bytes} bytes'
                        return response
                encoding = result.encoding or requests.utils.get_encoding_from_headers(result.headers) or 'utf-8'
                response['content'] = body.decode(encoding, errors='replace')
    except (URLSafetyError, requests.exceptions.RequestException, UnicodeError, LookupError, ValueError) as exc:
        # Avoid echoing raw exceptions; they can contain URLs with query tokens.
        response['error'] = f'Fetch blocked or unavailable ({type(exc).__name__})'
    return response


def analyze_page(url: str, parsed: dict, *, status_code: int = 200,
                 measured_at: str | None = None) -> dict:
    """Convert already parsed observations into non-speculative SEO findings."""
    if measured_at is None:
        measured_at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    safe_url = public_url(url)
    title = _text(parsed.get('title'), 180)
    description = _text(parsed.get('meta_description'), 350)
    canonical = _text(parsed.get('canonical'), 300)
    robots = _text(parsed.get('meta_robots'), 150)
    headings = [_text(v, 160) for v in parsed.get('h1', [])][:12]
    images = parsed.get('images', [])
    missing_alt = sum(1 for x in images if x.get('alt') is None)
    schema = parsed.get('schema', [])
    types = set()
    for block in schema:
        if isinstance(block, dict):
            values = block.get('@type') or []
            for value in values if isinstance(values, list) else [values]:
                if isinstance(value, str):
                    types.add(_text(value, 80))
    issues = []

    def finding(id_: str, priority: str, evidence: str, action: str) -> None:
        issues.append({'id': id_, 'priority': priority, 'evidence': evidence, 'recommendation': action})

    if not title:
        finding('missing-title', 'high', 'No HTML title found in the response',
                'Write a concise, page-specific title that describes the content')
    elif len(title) > 65:
        finding('long-title-review', 'review', f'Title length: {len(title)} characters',
                'Review title clarity on mobile search results; truncation varies by pixel width')
    if not description:
        finding('missing-meta-description', 'medium', 'No meta description found',
                'Add a specific summary for search snippets; Google may generate its own snippet')
    if not headings:
        finding('missing-h1', 'medium', 'No nonempty H1 found in static HTML',
                'Use a descriptive visible page heading; verify dynamically rendered content separately')
    if missing_alt:
        finding('image-alt-missing', 'review', f'{missing_alt} of {len(images)} images lack an alt attribute',
                'Add meaningful alt text for informative images; use alt="" for decorative images')
    if 'noindex' in robots.lower().split(',') or re.search(r'(?<!\w)noindex(?!\w)', robots, re.I):
        finding('noindex-review', 'review', f'Robots meta tag contains noindex: {robots}',
                'Verify whether excluding this page from indexing is intentional')
    if not canonical:
        finding('canonical-review', 'review', 'No canonical link found in static HTML',
                'Check whether a self-referencing or preferred canonical is appropriate for this page')

    return {
        'schema_version': 1,
        'scope': 'single-page-raw-html',
        'method': 'one bounded DNS-validated public HTTP GET; static HTML parsing only',
        'url': safe_url,
        'observed_at_utc': measured_at,
        'http_status': status_code,
        'observations': {
            'title': title or None,
            'meta_description': description or None,
            'canonical': canonical or None,
            'robots_meta': robots or None,
            'h1': headings,
            'image_count': len(images),
            'image_alt_attribute_missing': missing_alt,
            'schema_types': sorted(types),
            'schema_block_count': len(schema),
            'internal_link_count': len(parsed.get('links', {}).get('internal', [])),
            'external_link_count': len(parsed.get('links', {}).get('external', [])),
            'visible_word_count_estimate': parsed.get('word_count', 0),
        },
        'findings': issues,
        'not_measured': [
            'Chromium-rendered DOM and client-side-only content',
            'Core Web Vitals, Lighthouse, and real-user CrUX field data',
            'Google Search Console indexing, clicks, rankings, or search appearance',
            'Google Analytics, conversions, and other private account data',
            'Site-wide crawl, backlinks, GBP, robots.txt, and sitemap coverage',
        ],
        'seo_score': None,
        'outcome': 'observations-only; no SEO rankings or indexation claim',
    }


def markdown_report(report: dict) -> str:
    details = report['observations']
    lines = [f'# Quick SEO observations — {report["url"]}', '',
             f'Observed (UTC): {report["observed_at_utc"]}',
             f'HTTP status: {report["http_status"]}',
             f'Scope: {report["scope"]} (not a full audit)', '',
             '## Observed facts', '',
             f'- Title: {_text(details["title"])}',
             f'- Meta description: {_text(details["meta_description"])}',
             f'- Canonical: {_text(details["canonical"])}',
             f'- H1 count: {len(details["h1"])}',
             f'- Images: {details["image_count"]} (missing alt attribute: {details["image_alt_attribute_missing"]})',
             f'- Structured-data types: {", ".join(details["schema_types"]) or "not detected in static HTML"}',
             '', '## Findings requiring review', '']
    if report['findings']:
        for finding in report['findings']:
            lines.extend([f'### {finding["id"]} ({finding["priority"]})',
                          f'Evidence: {_text(finding["evidence"], 500)}',
                          f'Next action: {_text(finding["recommendation"], 500)}', ''])
    else:
        lines.append('No issues detected by this limited static-HTML checklist.')
    lines += ['', '## Not measured (do not infer from this report)', '']
    lines.extend(f'- {x}' for x in report['not_measured'])
    lines += ['', 'No search ranking outcome, indexing status or aggregate SEO score was inferred.', '']
    return '\n'.join(lines)


def run(url: str, *, max_bytes: int = MAX_BODY_BYTES) -> dict:
    fetched = fetch_html(url, max_bytes=max_bytes)
    if fetched['error']:
        return {
            'schema_version': 1, 'scope': 'single-page-raw-html',
            'url': fetched['url'], 'http_status': fetched['status_code'],
            'outcome': 'blocked', 'error': fetched['error'],
            'findings': [], 'seo_score': None,
        }
    from parse_html import parse_html
    parsed = parse_html(fetched['content'], fetched['url'])
    return analyze_page(fetched['url'], parsed, status_code=fetched['status_code'])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url', help='Public HTTP(S) URL to examine')
    parser.add_argument('--json', action='store_true', help='Output structured evidence JSON (default)')
    parser.add_argument('--markdown', action='store_true', help='Output brief Markdown report')
    parser.add_argument('--output', type=Path, help='Save JSON or Markdown to a chosen file')
    parser.add_argument('--max-bytes', type=int, default=MAX_BODY_BYTES,
                        help='Maximum HTML response size (1..2097152 bytes)')
    args = parser.parse_args(argv)
    if not (1 <= args.max_bytes <= MAX_BODY_BYTES):
        parser.error('--max-bytes must be between 1 and 2097152')
    report = run(args.url, max_bytes=args.max_bytes)
    output = markdown_report(report) if args.markdown and report['outcome'] != 'blocked' else json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(output + '\n', encoding='utf-8')
        print(f'Report saved to {args.output}', file=sys.stderr)
    else:
        print(output)
    return 2 if report['outcome'] == 'blocked' else 0


if __name__ == '__main__':
    raise SystemExit(main())
