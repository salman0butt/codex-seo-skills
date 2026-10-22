# Codex SEO Skills v0.2.0 — Codex compatibility, onboarding and audit readiness

## Added

- Four original/derived Codex skills: `$get-started`, `$seo-handoff`, `$seo-performance`, and `$seo-visual`, for a total of **30 core skills**. The original two performance/visual agent guides are used only as allowed MIT references.
- Portable OpenAI Agent Plugins `plugin.json` with optional onboarding skill (`get-started`); no bundled MCP server, hooks, automatic provider login or paid API calls.
- Independent static comparison with the former `codex-seo-final` tag in `docs/LEGACY_CODEX_COMPARISON.md`. That tag has a proprietary license and **none of its code has been included or adapted**.
- Runtime CLI diagnostics and tests covering the unready state, rejection of unlisted scripts, safe failure when dependency downloads fail, and pure-Python SEO metadata/schema smoke checks.
- Expanded GitHub Actions with six selected upstream runtime/URL-safety/schema/query unit-test groups and Codex-specific contracts.
- Updated skills/agent routing to fall back to sequential execution when agent delegation is unavailable.
- Refreshed machine-readable repo map and per-file relationships.

## Verification / limitations

- Verified local structural checks and smoke contracts; release must have green CI on exact tag commit; the Linux job also launches headless Chromium, reads the public `https://example.com/` test page through the browser, and runs bundled scripts.
- Managed runtime installation and Chromium setup **passed on a fresh GitHub Actions Ubuntu runner**; a separate macOS check is still blocked. A Playwright wheel failed mid-download due to interrupted package-host connectivity. The macOS failure left no successful state marker; the runtime correctly reports `ready=false` until dependencies are installed.
- The installed Codex CLI itself was not present in the checked shell, so live Codex skill invocation is not yet host-verified; API account/paid-provider integrations are not tested without credentials.
- No live SEO measurements, ranking claims, automated indexing, paid API results or unattended site modifications are claimed.
- Browser rendering requires Playwright/Chromium; run `codex-seo setup` once network access is reliable.
- Native `plugin.json` compatibility follows the OpenAI public Agent Plugins manifest shape, but marketplace acceptance has not been asserted.

## Install and verify

```bash
git clone --branch v0.2.0 https://github.com/salman0butt/codex-seo-skills.git
cd codex-seo-skills
python3 scripts/install_codex.py --dry-run
python3 scripts/install_codex.py
"$HOME/.agents/skills/seo/scripts/codex-seo" doctor --json
"$HOME/.agents/skills/seo/scripts/codex-seo" setup
```

Restart Codex after installation, then request `$get-started`, `$seo-audit`, or `$seo-performance` as skills. Python/browser setup and optional provider accounts must be configured explicitly.
