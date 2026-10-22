# Codex SEO Skills v0.3.1 — Stable managed Python selection

This patch release retains v0.3.0's 30 core Codex SEO skills, 19 specialist guide references, bounded public-page audit runner, portable plugin manifest, and MIT upstream attribution.

## Fixes

- The `scripts/codex-seo` launcher now selects the exact Python minor version recorded by a successfully installed managed runtime. For example, a Mac with `python3` pointing at 3.14 correctly reuses a working Python 3.11 environment, rather than reporting it outdated or rebuilding dependencies.
- An explicit `CLAUDE_SEO_PYTHON` still takes priority. Absent, corrupt, or non-allowlisted runtime state values are ignored safely.
- Adds four launcher regression tests for saved Python selection, explicit override, invalid state, and absent state.
- Improves release CI: hosted macOS validates managed setup, bundled script execution, and fail-closed private-URL rejection without assuming a third-party public site always responds. Ubuntu retains live page fetching and headless Chromium smoke checks.

## Verified evidence

- The connected Mac successfully installed all 30 core skills and a managed Python 3.11/Chromium runtime. With this new launcher, `doctor --json` reported `ready: true` and `browser_ready: true` **without an interpreter environment override**.
- The installed Mac tool ran a read-only `https://example.com/` quick audit (HTTP 200), and previously ran both raw-HTML and mobile Chromium tests for `https://digitalmx.no/` (HTTP 200). Those findings are page-specific and do not imply search ranking outcomes.
- Codex CLI 0.163.0 loaded `$get-started` in a read-only ephemeral session and routed an example public-page request to `$seo-page`; no remote changes were made.
- GitHub Actions on the release commit must pass Python 3.11/3.12 structural checks, upstream security contracts, macOS core runtime checks, and Linux Chromium/live audit smoke tests.

## Installation

```bash
git clone --branch v0.3.1 https://github.com/salman0butt/codex-seo-skills.git
cd codex-seo-skills
python3 scripts/install_codex.py --dry-run
python3 scripts/install_codex.py
```

For macOS hosts with a newer default Python and Python 3.11 available, bootstrap once using:

```bash
CLAUDE_SEO_PYTHON="$(command -v python3.11)" "$HOME/.agents/skills/seo/scripts/codex-seo" setup
"$HOME/.agents/skills/seo/scripts/codex-seo" doctor --json
"$HOME/.agents/skills/seo/scripts/codex-seo" run quick_audit.py https://example.com/ --markdown
```

After setup the wrapper automatically reuses the recorded Python minor. Optional GSC, GA4, DataForSEO, Firecrawl, and other provider integrations still require separately configured credentials and consent. Full-site crawling, private Analytics verification and ranking measurements are not claimed in this release.

Historical `codex-seo-final` source was marked proprietary and was **not copied** into this repository.
