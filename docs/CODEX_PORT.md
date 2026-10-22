# Codex port design

- Source: AgriciDaniel/claude-seo, commit `23a2a811f874361d228fc2681acfc0ad66272736`, MIT.
- Core: 26 retained skills from `skills/`, 19 guide prompts from `agents/`, all bundled SEO execution scripts.
- Optional: 9 extension skill manifests available, of which `seo-dataforseo` and `seo-image-gen` collide with core skills and are not registered twice.
- Codex install: shared data root + `~/.agents/skills/<skill-name>` symlink or copy.
- Runtime: each skill's canonical script invocation uses `$HOME/.agents/skills/seo/scripts/codex-seo`, which finds the installed shared runtime without `${CLAUDE_PLUGIN_ROOT}`.
- Intentional exclusions from this Codex-first fork: upstream Claude plugin registry, Claude-only hooks, and Claude-specific install/uninstall launchers. The upstream content remains available from the linked repository.
- Limitations: Claude slash command hooks and agent definitions aren't native Codex registrations. Third-party MCP servers and API credentials must be configured separately.
