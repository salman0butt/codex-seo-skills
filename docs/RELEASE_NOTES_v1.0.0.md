# Codex SEO Skills v1.0.0 — Production Readiness, Upstream Security Sync & Safe Upgrades

## Release scope

The first stable Codex SEO packaging and offline/public-site audit release. **This is not a claim of full Claude Code feature parity, live GSC/GA4 access, SEO ranking impact, or paid SEO integrations.** The integrated upstream Python code and the Codex fork have separate versions: upstream `claude-seo` 2.5.0 and Codex `plugin.json` 1.0.0.

## Key improvements

- **Transactional installer upgrades with rollback:** a mid-upgrade symlink or fallback copy failure restores the previously installed package, skill registrations and fallback copies instead of destroying the working installation. Regression tests exercise fresh installs and forced upgrade failures.
- **Security backports from pinned MIT upstream [`6be93f4`](https://github.com/AgriciDaniel/claude-seo/commit/6be93f45064ffbadced572b5d5c95f55fd263af0)**: decompressed-size limits for page fetches and redirected bodies; safe browser network-guard initialization; screenshot path containment; state/PKCE/timeout protections for Google sign-in; recent dependency security floors and Python 3.11–3.14 range. Imported source hashes recorded in `docs/UPSTREAM_SECURITY_SYNC_v1.0.0.json`.
- **Version clarity:** runtime diagnostics report Codex distribution semver instead of the embedded upstream Python package version. Installer still requires explicit runtime dependency setup; installing the skills alone makes no API call.
- **Reproducible capability and provenance evidence:** clear matrix of covered skills, agent guides, optional extensions, public page audits, local reporting/history and private Google access boundaries; remaining gaps listed in [`docs/PRODUCTION_READINESS_v1.0.0.md`](PRODUCTION_READINESS_v1.0.0.md).
- **Expanded CI:** newest local-only upstream SSRF, bounded HTTP, OAuth and screenshot path tests, alongside existing Linux Chromium/macOS runtime smoke and fork-specific security/installer checks.

## Verified release scope and limitations

- 30 core skills, 19 original specialist guides, 9 optional extension manifests (7 unique names), preserved MIT source attribution.
- Python 3.11 and 3.12 CI, managed macOS and Linux runtime, and Linux Chromium live public-page smoke. Unsupported Python 3.10/3.15 fail early; Windows native installer support is not claimed.
- Private GSC/GA4, CrUX with an API key, paid providers, native Claude hooks and SEO effectiveness were **not live-verified**. No credentials were copied or provider data fetched as part of this security sync.
- Safe local reports/alerts remain offline and require operator attestation of property identity before metric comparisons.

## Get started

```bash
git clone --branch v1.0.0 https://github.com/salman0butt/codex-seo-skills.git
cd codex-seo-skills
python3.11 scripts/install_codex.py
"$HOME/.agents/skills/seo/scripts/codex-seo" setup
"$HOME/.agents/skills/seo/scripts/codex-seo" doctor --json
```

If a previously installed runtime is marked not ready after upgrading requirements, explicitly rerun `codex-seo setup` with a supported Python version. Do not assume that skills installation itself updates Python packages.
