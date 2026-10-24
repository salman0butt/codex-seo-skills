# Codex SEO Skills: Agent Instructions

This repository is a Codex adaptation of [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo), under the MIT license (preserved in `LICENSE`).

## Skill routing
- Use `$seo` for full SEO orchestration only if the user wants a broad audit; prefer an exact leaf skill like `$seo-technical`, `$seo-geo`, `$seo-local`, `$seo-content`, `$seo-schema`, `$seo-google` for targeted tasks.
- These are Codex skill mentions, not shell commands or native Claude slash commands. Read `skills/<name>/SKILL.md` for the workflow.
- `seo-performance` and `seo-visual` are now standalone Codex skills, with the original agent guides preserved. `$get-started` and `$seo-handoff` are Codex-specific workflows.
- All 19 original specialist agent guides are retained in `skills/seo/references/agent-guides/` and `agents/`. Do not assume Claude agent orchestration works in Codex; execute their steps sequentially when agent delegation is unavailable.
- To call a bundled script after installation, use `"${HOME}/.agents/skills/seo/scripts/codex-seo" run <script.py> ...`. Run `... doctor --json` to inspect readiness and `... setup` only after user approval to install dependencies.

## Evidence and safety
- Respect robots.txt, access policy, privacy, and rate limits. Do not run intrusive scans or change live sites without owner approval.
- Distinguish measured metrics from estimates; distinguish lab Lighthouse scores from CrUX real-user field data.
- Don't promise ranking, ChatGPT inclusion, backlinks, 100/100 Lighthouse scores, or automatic search engine indexing.
- Never guess API data, site rankings, performance metrics, or historical trends. Flag missing credentials or unavailable tools.
- Require consent before setting up credentials, installing dependencies, initiating paid API requests, or writing/deploying external changes.
- Preserve attribution to upstream authors.

## Verification and provenance
- Do not copy or adapt source from the historical `codex-seo-final` tag; it is **proprietary**, not MIT. See `docs/LEGACY_CODEX_COMPARISON.md`.
- The portable `plugin.json` is optional packaging metadata; it does not connect any MCP providers or install Python dependencies.
- Check `python3 scripts/generate_skill_map.py --check`, `python3 scripts/portability_check.py --strict`, and the `test_codex_*.py` smoke tests before publishing.
- For untrusted live sites, use explicit user-approved scopes, DNS-pinned URL checks, and read-only access. Do not pay for external provider queries without an agreed budget.

- For a read-only first-pass of **one public page**, prefer `codex-seo run quick_audit.py <url> --markdown`; this is not a browser-based full-site crawl or Google API measurement. Do not infer rankings or aggregate SEO scores.

## Google and paid SEO integrations
- Run the offline `codex-seo run integration_doctor.py --json` before deciding what providers are configured. Never treat `configured_unverified` as successful authentication.
- Do not invoke `extensions/*/install.sh` as Codex MCP installers; upstream scripts primarily write Claude configuration. Follow `docs/CODEX_INTEGRATIONS.md` for reviewed, manual Codex MCP configuration.
- Do not auto-run Google's Indexing API on ordinary pages; Google restricts it to specific structured-data page types. Do not make paid DataForSEO or Firecrawl requests without explicit consent and cost budget.

## Live integration probes (v0.5)
- `integration_doctor.py` is entirely offline. `live_integration_verify.py` is **also offline unless `--live` is specified**; one targeted read-only Google API request is the limit for each invocation.
- Private GSC and GA4 property access checks additionally require `--allow-account-read --property <property>`; authenticating may refresh an OAuth token. Never infer clicks, impressions, sessions or indexing from metadata access.
- Report `rate_limited`, `field_data_unavailable`, `credentials_unavailable`, 403, and other blocked statuses as missing evidence; do not fabricate score/traffic metrics or repeat calls automatically. Paid-provider calls remain unapproved until a separate authorization and budget.

## Safe aggregate Search Console and GA4 reporting
- `private_seo_report.py` defaults to zero network access. Require `--live --allow-account-read --property <exact-id>` for a single, authorized, aggregate-only read of GSC or GA4. Both flags are mandatory. OAuth refresh may occur after authorization.
- The report is limited to 1–90 days and must not include properties, queries, landing pages, visitor identifiers, raw provider responses or secrets. Missing rows are `no_data`, not zero.
- Never treat GSC clicks and GA4 sessions as matching metrics, sum daily GA4 users, or infer ranking improvements. For complete row-level output, request separate authorization and use upstream helpers intentionally.

## Offline report generation and implementation handoff
- `seo_report_builder.py` is an offline, zero-provider-call composer. Use it to combine valid `private_seo_report.py` and `quick_audit.py` outputs, not as a substitute for executing an audit or obtaining Google authorization.
- Treat supplied JSON as untrusted even if `live_verified=true`; schema checks do not authenticate data provenance. Reject malformed sources rather than invent values.
- Calculate trends only for adjacent equal-length windows and only when the operator attests both exports are from the same Google property (`--confirm-same-property`); no causal claims or cross-source conflation.
- Hand off only reviewed raw-HTML findings with source references and non-authorized suggested changes. Never silently deploy and never echo private property IDs, URLs with sensitive paths, search terms, or personal information. See `docs/EVIDENCE_REPORTING.md`.

## Offline history & scheduled replays (v0.8.0)
- Use `seo_history.py` only for locally saved authorized JSON inputs; record, list, show and explicitly confirmed prune do not invoke APIs. History is private (SQLite 0600; directory 0700), and successive identical inputs must be idempotent even under concurrency.
- Only explicitly create Markdown copies with `--export-markdown`. Generated reports and databases may contain commercially sensitive aggregated metrics; never commit them or share without permission.
- `seo_schedule_template.py` only generates **reviewable text** for a weekly local cron/launchd replay; never silently install/enable a schedule. It does not refresh GSC/GA4 files or imply automatic data acquisition.
- Comparing distinct recorded snapshots requires `--confirm-history-same-property` for independently established provider identity; `--confirm-same-page-set` also requires matching actual ordered URLs. Never equate a vanished checklist finding to a deployed fix.

## Evidence-quality alert discipline (v0.9.0)
- `seo_evidence_alerts.py` is a read-only, no-provider-call local diagnostic over previously saved private history; never describe its output as a delivered notification or schedule. It does not create/modify a history snapshot.
- Do not alert on an unverified, stale, future, missing or mismatched report. Comparisons require adjacent equal-length windows AND explicit same-property attestation. Page finding alerts require same ordered exact URLs attested, a strictly newer observation, and recent evidence.
- Alerts are advisory anomaly candidates with clear baseline, absolute and relative gates, not proven ranking loss or a causal claim. Stable alert IDs assist an external consumer with deduplication; this tool does not persist acknowledgements. See `docs/EVIDENCE_ALERTS.md`.

## Stable v1.0.0 production gates
- The MIT upstream security sync is pinned to `6be93f45064ffbadced572b5d5c95f55fd263af0`; verify `docs/UPSTREAM_SECURITY_SYNC_v1.0.0.json` checksums and tests before altering synchronized files. Keep Codex-specific version (1.0.0) distinct from upstream Python dependency/project metadata (2.5.0).
- Never break an existing installation during upgrade: staged content, skill symlinks and fallback copies must recover on any pre-commit registration error. See injected installer failure tests.
- Browser security guard, decompressed response limits, redirect caps, SSRF exclusions and Google OAuth state/PKCE tests are release gates. No real private Google credentials, paid calls or site mutations without separate authorization.
- Production readiness applies to verified local/public read-only paths and does not imply Windows native support, Claude-only hook parity or live provider access. Read `docs/PRODUCTION_READINESS_v1.0.0.md` before describing coverage.
