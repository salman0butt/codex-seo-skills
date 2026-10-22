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
