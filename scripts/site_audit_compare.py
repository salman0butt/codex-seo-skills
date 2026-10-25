#!/usr/bin/env python3
"""Offline before/after comparison of two saved bounded-site audit files.

Inputs are untrusted snapshots, not cryptographically authenticated provider
measurements. A manual identity attestation is required before any finding
comparison; only exact matching URL+freshly observed HTML pairs qualify.
No network, credentials, schedules, notifications or site writes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from pathlib import Path

from site_audit_report import EvidenceError, _normalize, _stamp, read_source


def _date(raw: str) -> datetime:
    return datetime.fromisoformat(_stamp(raw))


def compare(before: dict, after: dict, *, confirm_same_site: bool = False) -> dict:
    prev = _normalize(before)
    curr = _normalize(after)
    root_equal = before['origin'] == after['origin']
    previous_stamp = _date(before['started_at_utc'])
    current_stamp = _date(after['started_at_utc'])
    result = {
        'schema_version': 1,
        'scope': 'offline-bounded-site-before-after-review',
        'source_authenticity': 'unverified_operator_supplied_JSON',
        'network_requests': 0, 'credentials_accessed': False,
        'notifications_sent': 0, 'site_changes_made': 0,
        'page_paths_included': False, 'titles_or_descriptions_included': False,
        'same_origin_in_sources': root_equal,
        'site_identity_attested': bool(confirm_same_site),
        'before': {'pages_recorded': len(prev),
                   'pages_evaluated': sum(p['evaluated'] for p in prev),
                   'source_outcome': before['outcome']},
        'after': {'pages_recorded': len(curr),
                  'pages_evaluated': sum(p['evaluated'] for p in curr),
                  'source_outcome': after['outcome']},
        'comparison_status': 'suppressed',
        'matched_pages': 0, 'compared_pages': 0,
        'pages_only_in_before': [], 'pages_only_in_after': [],
        'suppressed_page_comparisons': [], 'changes': [],
        'limitations': [
            'Only exact overlapping page URLs in two saved, bounded static-HTML samples are compared.',
            'Input source authenticity is not proven: a human must verify origin and ownership.',
            'A finding no longer observed does not establish the underlying problem was fixed.',
            'Absence of a page in one sample does not prove it was removed from the site.',
            'A review change is not a ranking, indexing, traffic or business outcome.',
            'No website, Google provider, scheduler or other external service was accessed.',
        ],
    }
    if not root_equal:
        result['comparison_status'] = 'different_origins'
        return result
    if not confirm_same_site:
        result['comparison_status'] = 'same_site_not_attested'
        return result
    if current_stamp <= previous_stamp:
        result['comparison_status'] = 'non_newer_after_snapshot'
        return result
    before_map = {page['url']: (p, page) for p, page in zip(prev, before['pages'])}
    after_map = {page['url']: (p, page) for p, page in zip(curr, after['pages'])}
    before_only = before_map.keys() - after_map.keys()
    after_only = after_map.keys() - before_map.keys()
    result['pages_only_in_before'] = sorted(before_map[url][0]['reference'] for url in before_only)
    result['pages_only_in_after'] = sorted(after_map[url][0]['reference'] for url in after_only)
    result['matched_pages'] = len(before_map.keys() & after_map.keys())
    for record, raw_page in zip(curr, after['pages']):
        url = raw_page['url']
        if url not in before_map:
            continue
        old, raw_old = before_map[url]
        new, raw_new = after_map[url]
        refs = {'before_reference': old['reference'], 'after_reference': new['reference']}
        if not old['evaluated'] or not new['evaluated']:
            result['suppressed_page_comparisons'].append({
                **refs, 'reason': 'not_both_evaluated_as_html'})
            continue
        # Source-level timestamps are checked above, but each individual
        # observation also needs to be strictly newer to prevent replay claims.
        if _date(raw_new['observed_at_utc']) <= _date(raw_old['observed_at_utc']):
            result['suppressed_page_comparisons'].append({
                **refs, 'reason': 'non_newer_page_observation'})
            continue
        result['compared_pages'] += 1
        old_ids = set(old['findings'])
        new_ids = set(new['findings'])
        appeared = sorted(new_ids - old_ids)
        no_longer = sorted(old_ids - new_ids)
        fields = [field for field in ('title', 'description') if old[field] != new[field]]
        if appeared or no_longer or fields:
            result['changes'].append({
                **refs, 'newly_observed_findings': appeared,
                'findings_no_longer_observed': no_longer,
                'changed_metadata_fields': fields,
                'change_authorized': False,
                'interpretation': 'source_observation_difference_only_not_proof_of_fix',
            })
    result['comparison_status'] = ('no_eligible_page_comparisons'
        if result['compared_pages'] == 0 else
        'partial_sample_comparison'
        if before['outcome'] == 'partial' or after['outcome'] == 'partial'
        else 'matched_evaluated_pages_only')
    return result


def markdown_report(doc: dict) -> str:
    lines = [
        '# Offline bounded-site before/after review', '',
        'Status: ' + doc['comparison_status'],
        'Source provenance: operator-supplied JSON; authenticity not proven.',
        'No network, site changes or automatic notifications.', '',
        'Before: ' + str(doc['before']['pages_recorded']) + ' sampled; '
            + str(doc['before']['pages_evaluated']) + ' evaluated.',
        'After: ' + str(doc['after']['pages_recorded']) + ' sampled; '
            + str(doc['after']['pages_evaluated']) + ' evaluated.',
        'Exact URL matches (URL paths redacted): ' + str(doc['matched_pages']),
        'Eligible page comparisons: ' + str(doc['compared_pages']), '',
        '## Advisory source observation changes', '',
    ]
    for change in doc['changes']:
        lines += [
            '- ' + change['before_reference'] + ' → ' + change['after_reference'],
            '  - Newly observed: ' + (', '.join(change['newly_observed_findings']) or 'none'),
            '  - No longer observed (NOT confirmed fixed): '
              + (', '.join(change['findings_no_longer_observed']) or 'none'),
            '  - Metadata fields changed: '
              + (', '.join(change['changed_metadata_fields']) or 'none'),
        ]
    if not doc['changes']:
        lines.append('No qualifying changes found; this is not evidence that the site is unchanged or healthy.')
    lines += ['', '## Sampling differences and suppressed comparisons', '']
    lines += ['- Only in before sample: ' + (', '.join(doc['pages_only_in_before']) or 'none'),
              '- Only in after sample: ' + (', '.join(doc['pages_only_in_after']) or 'none')]
    for skipped in doc['suppressed_page_comparisons']:
        lines.append('- ' + skipped['before_reference'] + ' / '
                     + skipped['after_reference'] + ': ' + skipped['reason'])
    lines += ['', '## Limitations', '']
    lines.extend('- ' + line for line in doc['limitations'])
    return '\n'.join(lines) + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True, type=Path, help='Earlier saved bounded site audit JSON')
    parser.add_argument('--after', required=True, type=Path, help='Later saved bounded site audit JSON')
    parser.add_argument('--confirm-same-site', action='store_true',
                        help='Attest both files came from the same authorized website')
    parser.add_argument('--format', choices=('json','markdown'), default='markdown')
    args = parser.parse_args(argv)
    try:
        doc = compare(read_source(args.before), read_source(args.after),
                      confirm_same_site=args.confirm_same_site)
        print(json.dumps(doc, indent=2, ensure_ascii=False)
              if args.format == 'json' else markdown_report(doc), end='\n' if args.format == 'json' else '')
        return 0 if doc['comparison_status'] in (
            'matched_evaluated_pages_only','partial_sample_comparison') else 2
    except EvidenceError as exc:
        print(json.dumps({'status':'error','reason':str(exc),'network_requests':0}),
              file=sys.stderr)
        return 2
    except (OSError, UnicodeError, ValueError, TypeError):
        print(json.dumps({'status':'error','reason':'Invalid saved comparison evidence',
                          'network_requests':0}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
