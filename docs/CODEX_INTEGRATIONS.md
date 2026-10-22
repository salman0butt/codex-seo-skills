# Codex SEO integrations — explicit, read-only setup

This guide is for the [Codex CLI MCP configuration format](https://learn.chatgpt.com/docs/extend/mcp?surface=cli). It **does not** copy, install, migrate, or configure credentials automatically. The upstream `extensions/*/install.sh` tools mostly configure **Claude Code** (`~/.claude.json`), not Codex. Do **not** run those installers to configure Codex. Native `SKILL.md` discovery and MCP tool connectivity are separate.

## Step 1 — Offline provider-preflight

After installing the 30 core skills and setting up the bundled Python runtime:

```bash
"$HOME/.agents/skills/seo/scripts/codex-seo" run integration_doctor.py --json
"$HOME/.agents/skills/seo/scripts/codex-seo" run integration_doctor.py --markdown
```

`missing_configuration` means no usable local configuration evidence was found; `partial_configuration` means only some required pieces are present; `configured_unverified` means local configuration **may** be sufficient. None means authenticated, authorized, quota-approved, connected, or tested. The preflight performs zero network requests, no credential refresh, no writes and no billing. It inspects the default **user-level** Codex MCP config (`$CODEX_HOME/config.toml` or `~/.codex/config.toml`); project-scoped MCP configurations are not currently detected by the preflight. It does not print keys, tokens, service account paths, or account identities.

## Step 2 — Google's read-only APIs

- **PageSpeed Insights (PSI)**: Can offer limited anonymous requests, but `GOOGLE_API_KEY` helps with project quota. The preflight checks key presence, not validity.
- **Chrome UX Report (CrUX)**: Requires a valid API key for bundled API requests. Field metrics may be unavailable for a low-traffic page; that is **not** a zero score.
- **Search Console**: You need `https://www.googleapis.com/auth/webmasters.readonly`, access to the exact verified property, and `GSC_PROPERTY=sc-domain:example.com` (or pass `--property`). URL inspection is read-only.
- **GA4 Data API**: You need `https://www.googleapis.com/auth/analytics.readonly`, Viewer or equivalent property access, and `GA4_PROPERTY_ID` (`123456789` or `properties/123456789`). A configured ID does not prove permission.

The existing upstream Google helper reads `~/.config/claude-seo/google-api.json` and `~/.config/claude-seo/oauth-token.json` as legacy paths, or supports environment variables. This version **does not rename, copy, or migrate** those files. Store keys and service-account files outside this Git repository; restrict file permissions. Run `codex-seo run google_auth.py --check --json` only in your own trusted terminal, because the legacy helper may display account-identifying metadata. The new preflight intentionally does not display it.

For ordinary website pages, use sitemaps, Search Console, and URL Inspection. Google's **Indexing API is restricted to pages with JobPosting or BroadcastEvent embedded in a VideoObject**, and it does not guarantee indexing. Do not run `indexing_notify.py` on ordinary pages. The publishing CLI now requires both `--eligible-type JobPosting|BroadcastEvent` and `--confirm-publish`; these are operator acknowledgements only, not a schema or permission check. [Google's official scope restrictions](https://developers.google.com/search/apis/indexing-api/v3/using-api).

## Step 3 — Optional paid MCP providers (manual, opt-in)

Codex uses `~/.codex/config.toml` or a trusted project's `.codex/config.toml`. Unlike Claude Code, it does not use `~/.claude.json`. Do not store API keys directly in TOML. Instead, you can configure STDIO MCP servers with **environment-variable forwarding** (supported by Codex):

```toml
# Illustration only — add after deciding to use the provider.
[mcp_servers.dataforseo]
command = "npx"
args = ["-y", "dataforseo-mcp-server@2.8.10"]
env_vars = ["DATAFORSEO_USERNAME", "DATAFORSEO_PASSWORD"]
enabled = false  # Set true only after reviewing tools and cost controls.

[mcp_servers.firecrawl]
command = "npx"
args = ["-y", "firecrawl-mcp@3.11.0"]
env_vars = ["FIRECRAWL_API_KEY"]
enabled = false  # Provider credits may be consumed.
```

The npm versions above match the upstream extension scripts as inspected for this release; verify package provenance and latest compatibility before enabling. Set environment variables via an approved secret manager or shell environment inherited by Codex, **not** via `codex mcp add --env KEY=VALUE`, which stores literal values in local configuration. Restart your Codex session, verify only the intended providers with `codex mcp list`, and inspect the actual exposed tools before making requests.

Treat DataForSEO cost estimates as approximate, never guaranteed charges. Use the bundled `dataforseo_costs.py estimate`/`check` before any paid tool call and seek **explicit** permission for its actual budget, target URLs and proposed operations. Firecrawl crawl/map requests may consume credits even when read-only. Do not start either provider as part of automatic installation or unattended discovery.

## Step 4 — What remains blocked without actual access

Actual search clicks, impressions, GA4 sessions, indexing details, CrUX data availability and paid-provider responses are **not available from local configuration inspection alone**. To verify those, the user must supply an authorized property and an appropriate service connection. Use one low-impact, clearly identified read-only query per provider, record the date and API response, and stop on authentication, permission, quota or billing errors. Never mislabel an empty API response as a healthy SEO outcome.

## Step 5 — Explicit live verification (v0.5.0)

The offline `integration_doctor.py` does **not** authorize live calls. To test actual API connectivity, use `live_integration_verify.py`. Without `--live` it exits nonzero and makes **zero HTTP requests**. Live probes make one read-only call to the selected Google API; an OAuth-backed property check can also refresh a Google token (consent implied only when passing `--allow-account-read`).

```bash
# Public, anonymous PageSpeed Lighthouse SEO-category, mobile device only
"$HOME/.agents/skills/seo/scripts/codex-seo" run live_integration_verify.py pagespeed --url https://example.com/ --live

# Public CrUX field data (must have a configured key)
"$HOME/.agents/skills/seo/scripts/codex-seo" run live_integration_verify.py crux --url https://example.com/ --live

# Only for properties you can legally access and have configured credentials for
"$HOME/.agents/skills/seo/scripts/codex-seo" run live_integration_verify.py gsc --property sc-domain:example.com --live --allow-account-read
"$HOME/.agents/skills/seo/scripts/codex-seo" run live_integration_verify.py ga4 --property 123456789 --live --allow-account-read
```

Responses intentionally omit token contents, service-account paths, queried account identities, raw HTTP response bodies, GSC ownership roles, GA4 business data and detailed provider exception strings. `verified` means **this specific API endpoint returned the expected structure**, not that any other permission, property, Google ranking, Core Web Vitals field dataset, or report is available. GSC and GA4 probes check only **metadata**, not Search Analytics or sessions. HTTP 429 is `rate_limited` with no score; 404 from CrUX is `field_data_unavailable`, not a performance failure. The tool does not retry. Timeouts are bounded; targets containing embedded authentication or query-string tokens are rejected.

An anonymous PageSpeed mobile SEO-category probe returned **HTTP 429** from the checked Mac on 2026-10-22. That result proves the endpoint was reached but **does not confirm Lighthouse execution**. A configured API key may be appropriate; don't hardcode or paste it into prompts. Never interpret API denial as a low SEO score. Paid providers remain outside this verifier and require explicit separate approval.

## Step 6 — Aggregate-only reporting (v0.6.0)

**Only if you have verified GSC/GA4 property access and authorize a read-only analytics query**, use `private_seo_report.py` with both `--live` and `--allow-account-read`. Without both flags, the command makes **zero network calls**, does not load OAuth credentials and returns a nonzero exit.

```bash
"$HOME/.agents/skills/seo/scripts/codex-seo" run private_seo_report.py gsc --property sc-domain:example.com --days 28 --live --allow-account-read
"$HOME/.agents/skills/seo/scripts/codex-seo" run private_seo_report.py ga4 --property 123456789 --days 28 --live --allow-account-read
```

GSC uses [Search Analytics `query`](https://developers.google.com/webmaster-tools/v1/searchanalytics/query) with **zero dimensions** (one true property-level aggregate rather than incomplete totals inferred by summing anonymized query rows), `type=web`, and finalized data ending three days before the local runtime date. GSC dates are interpreted by Google in Pacific Time; the local machine's date may cross a day boundary relative to Google. GA4 uses [Data API `runReport`](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/properties/runReport) with the `sessionDefaultChannelGroup = Organic Search` filter and no dimensions; `sessions`, `totalUsers`, and `engagedSessions` are fetched **once** for the full requested period to avoid invalid summing of distinct daily users. GA4 dates are interpreted in the property's configured timezone. The current default GA4 data window ends yesterday in the runtime's local timezone.

Both commands make at most one Google reporting HTTP request (OAuth credential refresh, if necessary, is separate). No paid provider is invoked. `no_data` is not equivalent to measured zero. HTTP authentication, permission and rate-limit errors are reported with a generic status, without echoing account IDs or raw provider payloads. We do not claim that these two metrics sets are directly comparable or proof of a ranking improvement. The bundled legacy `gsc_query.py` and `ga4_report.py` provide more detailed per-row workflows, which may expose query text or page URLs and should not be automatically invoked when aggregate-only reporting was requested.
