# Codex SEO Skills v0.3.0 — Live single-page evidence audits

## Added

- `scripts/quick_audit.py`: bounded, read-only single-page HTML SEO audit; captures status, observed title, meta description, canonical, H1, image alt attributes, structured-data types and links.
- Explicit `not_measured` ledger: JS-rendered DOM, Lighthouse/CrUX, GSC/GA4, indexation/rankings, backlinks, and site-wide crawl are **not measured**. No SEO score is invented.
- Canonical URL safety layer: public-host validation and DNS pinning; reject private/metadata targets; cap HTML to 2 MiB and 3 redirects. Never expose URL credentials, query strings or fragments in the output.
- Evidence-backed findings only, including missing description/title/H1, missing image alt attribute (with decorative exception), missing canonical *review*, and optional noindex review. No FAQ ranking claims or unconditional penalties.
- JSON and Markdown outputs; Codex `$seo-page` and `$get-started` routing hints; new unit tests and CI live check against `https://example.com/`.
- Updated manifest and deterministic file/agent/script traceability graph.

## Verified

- On the connected Mac: all 30 core skills installed at `~/.agents/skills/`; a Python 3.11 managed runtime reported both `ready: true` and `browser_ready: true`; the runner made a successful HTTP 200 read-only audit of `https://digitalmx.no/` on 2026-10-22, finding 3/35 images lacking an alt attribute in raw HTML. A separate Playwright Chromium mobile render succeeded (HTTP 200, `mode_used=rendered`, no error). This is a **review item**, not a demonstrated SEO ranking issue.
- CI must pass on the exact release commit: portability, isolated installation, mapping, upstream contracts, Ubuntu Chromium rendering, macOS managed-core setup, and the new bounded public-page audit.
- Codex CLI 0.163.0 was launched on the connected Mac; `debug prompt-input` included `seo-page`, `seo-geo`, `get-started`, and `seo-handoff`. A separate **read-only ephemeral Codex model invocation** used `$get-started` to route the supplied no-network, no-edit single-page request to `$seo-page`. No commands or network requests were performed in that validation; therefore it verifies skill routing but not the Codex model executing the audit itself.
- Third-party account API integrations are separately tracked; this release is not a promise of GSC/GA4 authentication or full-site crawling.

## Install

```bash
git clone --branch v0.3.0 https://github.com/salman0butt/codex-seo-skills.git
cd codex-seo-skills
python3 scripts/install_codex.py --dry-run
python3 scripts/install_codex.py
"$HOME/.agents/skills/seo/scripts/codex-seo" doctor --json
"$HOME/.agents/skills/seo/scripts/codex-seo" run quick_audit.py https://example.com/ --markdown
```

Chromium setup is separate; run `codex-seo setup` to install it when needed. External credentials and paid provider APIs remain opt-in. The historical proprietary `codex-seo-final` code was not reused.
