#!/usr/bin/env python3
"""Safe, offline Codex SEO provider-preflight. No network, token refresh, or writes.

Report presence of supported configuration only, never credential values,
file paths, email addresses, OAuth tokens, external API status or paid usage.

Usage:
    codex-seo run integration_doctor.py --json
    codex-seo run integration_doctor.py --markdown
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Mapping

SERVICES = ("pagespeed", "crux", "gsc", "ga4", "dataforseo", "firecrawl")
GOOGLE_CONFIG_BASENAME = Path('.config/claude-seo/google-api.json')
GOOGLE_TOKEN_BASENAME = Path('.config/claude-seo/oauth-token.json')
ADC_BASENAME = Path('.config/gcloud/application_default_credentials.json')


def _safe_json_dict(path: Path) -> dict:
    """Read only a small JSON configuration, without echoing errors/values."""
    try:
        if not path.is_file() or path.stat().st_size > 64 * 1024:
            return {}
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, UnicodeError, ValueError):
        return {}


def _codex_mcp_entries(config: Path) -> set[str]:
    try:
        import tomllib
    except ImportError:  # Supports Python 3.10 without a required dependency.
        return set()
    try:
        if not config.is_file() or config.stat().st_size > 1024 * 1024:
            return set()
        with config.open('rb') as handle:
            root = tomllib.load(handle)
        mcp = root.get('mcp_servers', {})
        return {name.lower() for name, value in mcp.items()
                if isinstance(name, str) and isinstance(value, dict) and value.get('enabled', True) is not False}
    except (OSError, ValueError, UnicodeError):
        return set()


def examine(*, environ: Mapping[str, str] | None = None,
            home: Path | None = None, codex_home: Path | None = None) -> dict:
    env = os.environ if environ is None else environ
    base = Path.home() if home is None else home
    codex_base = codex_home or Path(env.get('CODEX_HOME') or base / '.codex')
    conf = _safe_json_dict(base / GOOGLE_CONFIG_BASENAME)
    token_file = (base / GOOGLE_TOKEN_BASENAME).is_file()
    sa_path = conf.get('service_account_path') or env.get('GOOGLE_APPLICATION_CREDENTIALS')
    sa_file = False
    if isinstance(sa_path, str) and sa_path.strip():
        try:
            sa_file = Path(os.path.expanduser(sa_path)).is_file()
        except (OSError, ValueError):
            pass
    adc_file = (base / ADC_BASENAME).is_file()
    google_oauth = token_file or sa_file or adc_file
    api_key = bool(conf.get('api_key') or env.get('GOOGLE_API_KEY'))
    gsc_prop = bool(conf.get('default_property') or env.get('GSC_PROPERTY'))
    ga4_prop = bool(conf.get('ga4_property_id') or env.get('GA4_PROPERTY_ID'))

    servers = _codex_mcp_entries(codex_base / 'config.toml')
    df_credentials = bool(env.get('DATAFORSEO_USERNAME') and env.get('DATAFORSEO_PASSWORD'))
    firecrawl_credentials = bool(env.get('FIRECRAWL_API_KEY'))
    df_mcp = any('dataforseo' in server for server in servers)
    fc_mcp = any('firecrawl' in server for server in servers)

    def item(credentials: bool, extra: bool = True, *, notes: str = '') -> dict:
        if credentials and extra:
            level = 'configured_unverified'
        elif credentials or extra:
            level = 'partial_configuration'
        else:
            level = 'missing_configuration'
        return {'status': level, 'live_verified': False, 'notes': notes}

    result = {
        'schema_version': 1,
        'mode': 'offline-read-only',
        'network_requests': 0,
        'credentials_echoed': False,
        'credential_scope': 'presence-only',
        'services': {
            'pagespeed': item(api_key, api_key, notes='API key presence does not prove permission or quota; unauthenticated PSI may also work.'),
            'crux': item(api_key, api_key, notes='CrUX field data may be unavailable for low-traffic URLs even with a key.'),
            'gsc': item(google_oauth, gsc_prop, notes='Read-only Search Console authorization, property access, and token validity not checked.'),
            'ga4': item(google_oauth, ga4_prop, notes='GA4 Viewer permission, property access, and token validity not checked.'),
            'dataforseo': item(df_credentials, df_mcp, notes='Paid calls prohibited without explicit user consent and budget. Legacy Claude installer is not Codex-compatible.'),
            'firecrawl': item(firecrawl_credentials, fc_mcp, notes='Provider credits may be billed; do not invoke crawl without permission. Legacy Claude installer is not Codex-compatible.'),
        },
        'limitations': [
            'This checks configuration presence, not actual authentication, ownership, OAuth scopes or API connectivity.',
            'No token refresh, credential migration, third-party calls, write actions, or paid requests occurred.',
            'Legacy Google config is inspected read-only; no credentials are copied into Codex or this repository.',
            'DataForSEO and Firecrawl MCP server entries and their credentials must be explicitly configured in Codex.',
            'Google Indexing API is limited to supported JobPosting and BroadcastEvent/VideoObject pages and is not part of this preflight.',
        ],
    }
    return result


def markdown(payload: dict) -> str:
    lines = [
        '# Codex SEO integration preflight', '',
        'Offline configuration-presence check; **not a live API verification**.', '',
        '| Service | Local configuration | Live verified |', '|---|---|---|',
    ]
    for name in SERVICES:
        entry = payload['services'][name]
        lines.append(f'| {name} | {entry["status"]} | No |')
    lines += ['', '## Limitations', '']
    lines.extend(f'- {entry}' for entry in payload['limitations'])
    lines.append('')
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--json', action='store_true', help='Print JSON evidence (default)')
    group.add_argument('--markdown', action='store_true', help='Print a compact Markdown table')
    args = parser.parse_args(argv)
    payload = examine()
    print(markdown(payload) if args.markdown else json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
