# Codex SEO Skills v0.4.0 — Safe provider integration preflight

## Added

- `integration_doctor.py` — an **offline, read-only** diagnostic for PageSpeed, CrUX, Search Console, GA4, DataForSEO, and Firecrawl. Shows only missing/partial/configured-but-unverified states, never keys, tokens, account identities, secret paths, external API results, or fake traffic/ranking data.
- Tests for empty configuration, fabricated credentials, secret redaction, disabled/invalid MCP entries, explicit Google property requirements and no network calls.
- `docs/CODEX_INTEGRATIONS.md`: verified Codex TOML MCP configuration model, environment-variable forwarding, credential boundaries, legacy Google path compatibility, scope guidance and opt-in paid-provider setup.
- New skill guidance guarding against running upstream Claude extension installers to configure Codex and against assuming credentials imply access.
- Optional provider readiness in CI, separate from real provider API calls.
- Fail-closed Indexing API publishing flags: an operator must assert an eligible page type and explicitly acknowledge publishing before a single or batch send; status reads remain available without those flags. This is an intentional tightening of the previous CLI contract.

## Verified / not verified

- GitHub Actions must pass Python 3.11/3.12 and macOS/Linux managed-runtime, browser and static provider-contract checks on the exact release commit.
- Local integration preflight performs **zero** network calls and does not migrate, modify or log credentials.
- Google Search Console and GA4 live API permissions are **not** authenticated by this release. PageSpeed/CrUX API credentials, DataForSEO and Firecrawl provider billing/credits are **not** verified. The user must explicitly connect authorized accounts and accept potential costs for live tests.
- Google's Indexing API only supports eligible JobPosting or BroadcastEvent/VideoObject pages; it is not a general-purpose indexing shortcut.

## Usage

```bash
git clone --branch v0.4.0 https://github.com/salman0butt/codex-seo-skills.git
cd codex-seo-skills
python3 scripts/install_codex.py
"$HOME/.agents/skills/seo/scripts/codex-seo" run integration_doctor.py --markdown
```

Documentation: [Codex integrations](CODEX_INTEGRATIONS.md). Manual configuration is optional. This release does not install MCP servers, copy private credentials, access proprietary legacy Codex source, or initiate paid queries.
