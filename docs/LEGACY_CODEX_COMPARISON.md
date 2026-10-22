# Historical Codex fork comparison (read-only)

## Sources and license boundary

- Current public **Claude SEO**: [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo), MIT, baseline `23a2a811f874361d228fc2681acfc0ad66272736` (v2.4.2).
- Preserved legacy Codex repository: [codex-seo-final](https://github.com/AgriciDaniel/chatgpt-seo/tree/codex-seo-final), commit `9a644f68d39d242a7a41a0017f7286dd0512fc3b`.
- The legacy tag's **LICENSE is proprietary** and expressly prohibits copying, redistribution, and derivative distribution. **No legacy code, TOML agent definitions, scripts, templates, or assets have been copied into this public project.** We only compare publicly described architecture and inventory counts. MIT licensing of the newer ChatGPT package does not apply retroactively to the legacy tag.

## Architecture comparison

| Area | Preserved legacy tag (historical reference) | This MIT Codex fork, v0.2.0 |
|---|---|---|
| Core entry points | 27 skill folders in legacy tag | 30 standalone skill manifests built from MIT Claude SEO and original Codex workflows |
| Agent support | 24 agent TOML profiles | 19 preserved source agent guides; Codex skills usable without native subagent configuration |
| Discovery | Codex-specific plugin manifest | Portable `plugin.json`, `AGENTS.md`, `agents/openai.yaml` for 30 skills, and global installer |
| Runtime | Deterministic wrappers and headless/API execution in legacy product | MIT-sourced Python runner, safe allowlist, validated CLI setup failure handling |
| Cache | Shared `.seo-cache` described in legacy README | No claim of shared cache parity; runtime's existing drift-state functions retained |
| Testing | Historical README claims 52 tests in legacy run | CI tests structural maps, installer isolation, portability, runtime failure-path, and smoke contracts |
| Extensions | Legacy provider connectors and helper installers | MIT upstream's 9 optional extension bundles (require provider setup) |

## Gap decisions

- Retain current MIT source and implement unique Codex improvements independently. Do not migrate the legacy proprietary files.
- New standalone `seo-performance` and `seo-visual` skills use already-licensed Markdown agent guides as checklists; original Codex versions are not used.
- New original `get-started` and `seo-handoff` skills improve onboarding/implementation handoff without copying the legacy product.
- Separate public skill guidance, verifiable CLI smoke tests, and optional third-party API integrations. No account is linked automatically.
- Not a claim of feature parity with the historical proprietary product. Report runtime credentials, browser environment, private data, paid API costs, and actual measured audit outcomes independently.
