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
