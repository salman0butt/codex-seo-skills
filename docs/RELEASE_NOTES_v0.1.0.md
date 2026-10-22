# Codex SEO Skills v0.1.0 — Initial Codex mapping release

## What is included

- Initial OpenAI Codex fork of [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo), upstream v2.4.2 / commit `23a2a811f874361d228fc2681acfc0ad66272736` (MIT license and attribution preserved).
- 26 core Codex-discoverable `SKILL.md` entries with `agents/openai.yaml` metadata, 19 retained specialist agent guides, and 9 optional extension bundles (7 additional unique skill names).
- Safe global skill installer with dry-run and optional extensions. Bundled runtime is isolated; Python/browser dependencies, credentials, and paid third-party APIs are not installed or configured automatically.
- Generated end-to-end SEO map (`docs/SKILL_AGENT_MAP.md`), file-by-file inventory (`docs/FILE_INVENTORY.md`), and machine-readable dependency graph (`docs/skill-agent-map.json`). Every repository file gets a role and owner classification; script/test links reflect static source references, not proof of runtime behavior.
- Deterministic mapping generator and CI drift validation with isolated installer and graph tests.

## Installation

```bash
git clone --branch v0.1.0 https://github.com/salman0butt/codex-seo-skills.git
cd codex-seo-skills
python3 scripts/install_codex.py --dry-run
python3 scripts/install_codex.py
```

Optional: `python3 scripts/install_codex.py --with-extensions`. Review extension dependencies and API charges separately. Windows: use WSL.

## Usage

```text
$seo audit https://example.com
$seo-technical https://example.com
$seo-geo https://example.com
$seo-local https://example.com
```

Use these in a Codex conversation, not in a shell. After installation, you can inspect environment readiness with `"$HOME/.agents/skills/seo/scripts/codex-seo" doctor --json`; run `setup` only when you choose to install the managed dependencies.

## Compatibility and limitations

- `seo-performance` and `seo-visual` are guide-only specialties, not independent Codex skills.
- Claude Code hooks, slash command registration, and automatic Claude subagent dispatch are not native Codex features; Codex can instead consult those guides as checklists.
- Live SEO/API workflows require relevant network access, credentials, dependencies, and sometimes external MCP servers or paid subscriptions.
- Static references, imported modules, and test-file mentions in the graph are **not** a guarantee of successful live execution or measured SEO performance.
- The release does not claim that all third-party integrations or real-site audits have been exercised end to end.

## Verification before publishing

- `python3 scripts/portability_check.py --strict`
- `python3 scripts/generate_skill_map.py --check`
- `python3 -m unittest discover -s tests -p 'test_codex_installer.py' -v`
- `python3 -m unittest discover -s tests -p 'test_skill_map.py' -v`
- GitHub Actions `Validate Codex skills` must pass on the release commit.
