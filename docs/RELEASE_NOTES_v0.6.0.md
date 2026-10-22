# Codex SEO Skills v0.6.0 — Aggregate-only GSC and GA4 reports

## Added

- `private_seo_report.py` — explicitly authorized single-request read-only aggregate reporting for **Google Search Console** and **Google Analytics 4**.
- Mandatory **two-key permission gate**: `--live` and `--allow-account-read` plus an explicit validated `--property`. No OAuth loading, refresh or HTTP call before both flags. Reports are limited to **1–90 days**.
- GSC: `searchAnalytics.query` with no dimensions (`type=web` and finalized data), a single aggregate row of clicks, impressions, CTR and average position. Never sum query rows, which undercount anonymized query data.
- GA4: `properties.runReport` once per report period, filtered to `Organic Search`, with sessions, total users and engaged sessions aggregated across the period. Never sum daily distinct users.
- Responses redact properties, visitor data, query/page rows, raw API payloads, account identifiers and secrets. Empty results are `no_data`, not measured zero. API permissions and rate limits fail visibly.
- 12 provider-mocked contract tests plus real CLI smoke tests (without authorization flags, **zero** network calls).
- Documentation and skill routing updates for source attribution and differing GSC/GA4 metric definitions.

## Testing and limitations

- GitHub Actions must pass the exact tag commit: Python 3.11/3.12, macOS managed runtime, Linux Chromium, offline authorization and upstream regression checks.
- **Private properties were not queried during this release**. The tool's API schemas and response behavior are regression-tested with deterministic mocks; actual GSC and GA4 usage requires user-owned properties, valid credentials, authorization and available API quota.
- Date windows use the local runtime calendar, ending 3 days ago for finalized GSC and 1 day ago for GA4. GSC dates are Pacific Time and GA4 dates follow property timezone. A single report is not an SEO trend, and GSC clicks are not equivalent to GA4 organic sessions.
- No paid-provider calls, Indexing API notifications, credential copying or unattended account changes. OAuth refresh can occur **only after explicit private-read authorization**.

## Install and verify

```bash
git clone --branch v0.6.0 https://github.com/salman0butt/codex-seo-skills.git
cd codex-seo-skills
python3 scripts/install_codex.py
"$HOME/.agents/skills/seo/scripts/codex-seo" run integration_doctor.py --markdown
"$HOME/.agents/skills/seo/scripts/codex-seo" run private_seo_report.py gsc
# Once the property and read access are explicitly authorized:
"$HOME/.agents/skills/seo/scripts/codex-seo" run private_seo_report.py gsc --property sc-domain:example.com --days 28 --live --allow-account-read
"$HOME/.agents/skills/seo/scripts/codex-seo" run private_seo_report.py ga4 --property 123456789 --days 28 --live --allow-account-read
```

See [Codex Integrations](CODEX_INTEGRATIONS.md) for configuration and credential requirements.
