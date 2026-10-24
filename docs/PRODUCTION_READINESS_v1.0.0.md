# v1.0.0 — Codex SEO Skills production readiness and capability evidence

**Release scope:** stable *local/offline and public-site Codex SEO skill packaging*. This label does **not** assert that credentials are connected, Google rankings improved, the platform is a hosted SaaS, or that all Claude Code features are ported to Codex. Evidence references below are exact executable tests and pinned code; see the GitHub Actions CI and release-tag results for each released commit.

## Source provenance / upstream delta

- Original source: MIT [`AgriciDaniel/claude-seo`](https://github.com/AgriciDaniel/claude-seo), baseline `23a2a811f874361d228fc2681acfc0ad66272736` (upstream `v2.4.2`). Licensing and attribution preserved.
- Independently fetched latest reviewed upstream: commit `6be93f45064ffbadced572b5d5c95f55fd263af0`, upstream `v2.5.0` at the time of review. **This commit is pinned**: future upstream changes are not automatically imported. See [security synchronization manifest](UPSTREAM_SECURITY_SYNC_v1.0.0.json) for checksums of eleven code/dependency files imported verbatim from upstream. Includes response-size caps (also on redirects), guarded browser context, safe screenshot destination handling, SSRF protections, Google OAuth state/PKCE/timeout improvements and updated requirements including Pillow 13 security floor.
- The original *baseline* inventory is preserved for **all 169 `skills/` files, 19 `agents/` guides, 61 `scripts/` files and 74 `extensions/` files**. Some original scripts were intentionally modified by this Codex fork; identical names are not a promise of identical semantics.
- Added Codex skills and workflows coexist with upstream files. **Claude-specific hooks and slash command handlers are not installed**. The historical `AgriciDaniel/chatgpt-seo` `codex-seo-final` branch has a **proprietary license**: none of its code was copied or adapted. See [legacy comparison](LEGACY_CODEX_COMPARISON.md).
- `plugin.json` version **1.0.0** names this Codex distribution; `pyproject.toml` **2.5.0** describes the embedded upstream Python package. The managed runtime now prioritizes the Codex manifest for user-facing version diagnostics.

## Verified capability matrix

| Capability | Level | Evidence and boundaries |
|---|---|---|
| Core skill discovery | **Supported** | 30 `skills/*/SKILL.md`, 30 `agents/openai.yaml`, `get-started`, `seo-performance`, `seo-visual`, `seo-handoff`; portable frontmatter lint; installer tests |
| Preserved specialist checklists | **Supported, manual orchestration** | 19 upstream agent guides in both `agents/` and `skills/seo/references/agent-guides`; sequential Codex execution, not automatic Claude parallel agents |
| Optional extension skill discovery | **Supported with separate setup** | Nine extension SKILL manifests, seven unique after colliding core names; provider-specific credentials/MCP setup are **not** automated |
| Installer/reinstall rollback | **Verified** | `tests/test_codex_installer.py` includes fresh install, conflict protection and injected mid-upgrade symlink+copy fallback failures; restores old package, symlinks and fallback copies |
| Python and browser runtime | **CI verified for supported targets** | Python 3.11–3.14 allowed; CI Python 3.11/3.12 and Mac/Linux managed setup with Linux Chromium browser smoke. Actual physical Windows and Python 3.13/3.14 dependencies not all exercised |
| Safe read-only public SEO page acquisition | **Tested** | `quick_audit`, `render_page`, `fetch_page`, guarded browser context; bounded responses, redirects and SSRF checks; no assertion of whole-site crawl or search ranking |
| Google OAuth logic | **Security-flow tests only** | State, PKCE and timeout verified locally with mocked token endpoint. No live credential, Google property or paid service access |
| PageSpeed / CrUX live probes | **Conditional** | Explicit `--live`, one read-only request; PageSpeed anonymous endpoint previously responded with HTTP 429; real CrUX requires API key |
| Search Console / GA4 aggregate reports | **Conditional** | Explicit `--live --allow-account-read` and authorized property; deterministic mocked reporting tests, **not** live property verification |
| Offline reports / history / advisory alerts | **Supported** | v0.7–0.9 local schema, replay/concurrency/threshold tests; input authenticity is **not cryptographically verified**; private aggregate data remains sensitive |
| SEO edits, publishing, provider spending | **Not automatic** | No automatic live site edits, Google Indexing API publish, third-party paid API calls, or real scheduled delivery; separately approved action needed |
| Claude native hooks, `seo-cockpit`, proprietary legacy Codex agents | **Not ported / intentionally excluded** | Claude-specific runtime bindings, proprietary legacy Codex code, and unverified downstream MCP integrations are not native OpenAI Codex implementations |

## Security and correctness gates

1. Python 3.11/3.12 CI runs isolated `test_codex_*` suite, portable SKILL lint, map consistency, indexation publish restrictions, live API gate tests, aggregate report/privacy/threshold tests, and **release readiness static checks**.
2. Upstream contracts include new Python 3.11 local-only tests: bounded final/redirect HTTP bodies, SSRF, guarded screenshot path, PKCE + OAuth flow, hostile inputs, runtime setup and reporting contracts. These do not require real paid or private Google access.
3. Managed Linux runtime smoke performs fresh dependency installation, Chromium launch, public `https://example.com/` page rendering, private API no-opt-in denial, synthetic history, comparison/alert smoke. macOS smoke installs runtime, exercises local metadata generation and fail-closed target blocking.
4. Release ZIP and SHA-256 are produced from the exact immutable annotated Git tag (not the untracked local checkout). The `main` and tag CI must be green; repository clean and zero open PRs before signoff.
5. No secrets are committed. No external account scopes are expanded by default. The `--live` and `--allow-account-read` contract remains mandatory for new private provider requests. Upstream `google_auth.py` import itself performs no Google sign-in.

## Important known limitations

- A user must separately install Python 3.11–3.14 and use `codex-seo setup` to create or refresh the managed environment. The compiled dependency matrix is validated on Python 3.11/3.12 CI, not guaranteed on every OS/Python combination. Browser download and public-page network tests can be blocked by local firewalls, quota limits or network policy.
- Live private Google APIs are **not** asserted tested on the user's properties. No Search Console impression/click measurements or GA4 organic traffic are invented.
- The toolchain does not guarantee search engine indexing, Google ranking changes, AI citation inclusion, revenue, or Lighthouse 100/100 scores.
- A scheduled replay reads pre-existing local exports; it does **not refresh Google metrics automatically**. Advisory alerts are not delivered unless the user explicitly sets up a separate workflow.
- The native Windows installation experience, upstream `seo-cockpit`, Claude-only hooks and parallel agent semantics are **not implemented** in this fork.
- Upstream continues independently. All future security changes must be reviewed, re-tested and attributed before import. The fork is not feature-parity complete across every Claude-only feature.

## Reproduce the offline checks

```bash
python3 scripts/generate_skill_map.py --check
python3 scripts/portability_check.py --strict
python3 -m unittest discover -s tests -p 'test_codex_*.py' -v
python3 -m unittest discover -s tests -p test_v1_readiness.py -v
python3 -m unittest discover -s tests -p test_seo_evidence_alerts.py -v
# Optional when pytest and its non-provider prerequisites are installed:
python3 -m pytest -q tests/test_url_safety.py tests/test_fetch_page_size_cap.py \
  tests/test_redirect_body_cap.py tests/test_google_oauth_flow.py \
  tests/test_capture_screenshot_paths.py
```

The overall test result is only a *release gate*, not a proof of live external API permissions or SEO outcomes.
