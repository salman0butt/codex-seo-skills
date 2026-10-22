# Codex SEO Skills v0.2.1 — Interrupted setup rollback hotfix

This patch release contains the v0.2.0 Codex onboarding, 30 core skills, the portable plugin manifest, skill/agent mapping, live mobile Chromium audit smoke and integration contracts.

## Fix

- Treat a user-interrupted (`Ctrl-C` / `SIGINT`) runtime setup as an explicit rollback. Remove the staged `.venv.next-*` environment, remove temporary state, preserve any prior known-good environment, and exit with status `130`.
- Add a regression test that interrupts the virtualenv bootstrapping sequence and asserts staged files and locks are cleaned up.
- No bundled dependencies or paid-provider configuration changed.

## Verification and limitations

- Run `python3 -m unittest discover -s tests -p test_codex_runtime_contract.py -v`, `python3 scripts/portability_check.py --strict`, and `python3 scripts/generate_skill_map.py --check`. All GitHub Actions jobs must pass on the release commit.
- Headless Chromium and a live public `https://example.com/` mobile rendering check were validated on GitHub Actions Ubuntu; the checked macOS computer still cannot complete its Python package download reliably. No runtime success is claimed on that Mac.
- Third-party accounts and paid SEO integrations are optional and require separate credentials and user authorization. Codex CLI invocation on the checked Mac remains unverified because the CLI is not installed in that shell.
- Historical `codex-seo-final` source has a proprietary license and was not copied.

## Install

```bash
git clone --branch v0.2.1 https://github.com/salman0butt/codex-seo-skills.git
cd codex-seo-skills
python3 scripts/install_codex.py --dry-run
python3 scripts/install_codex.py
"$HOME/.agents/skills/seo/scripts/codex-seo" doctor --json
```
