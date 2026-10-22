# Codex SEO Skills

An MIT-licensed Codex-compatible adaptation of [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo). **30 core SEO skills**, **19 specialist guides**, and **9 optional extension skill bundles** are retained from upstream. Two extensions (`seo-dataforseo` and `seo-image-gen`) share names with core skills. The installer skips these duplicates; both original extension bundles remain available under `extensions/`.

Technical SEO, local SEO, AI search visibility (GEO/AEO), structured data, sitemaps, backlink research, content audits, Core Web Vitals, and Google Search Console/GA4 workflows are included. Optional integrations require appropriate credentials and may have usage costs.

## End-to-end mappings and traceability

- [System flow and every skill → specialist agent → script → test association](docs/SKILL_AGENT_MAP.md)
- [File-by-file repository inventory](docs/FILE_INVENTORY.md)
- [Machine-readable directed graph](docs/skill-agent-map.json)
- [Version 0.2.0 release notes](docs/RELEASE_NOTES_v0.2.0.md)

Update maps after code edits: `python3 scripts/generate_skill_map.py`. CI rejects stale maps with `python3 scripts/generate_skill_map.py --check`. The map distinguishes references from verified execution. `seo-performance` and `seo-visual` now have dedicated Codex skills, as do `$get-started` and `$seo-handoff`.

This repository also has an optional portable [Agent Plugins manifest](plugin.json) with a `$get-started` onboarding skill. It does not bundle an MCP server or preconfigured external accounts. See [comparison with the historical Codex project](docs/LEGACY_CODEX_COMPARISON.md); its proprietary code is not redistributed here.

## Install (macOS/Linux, Python 3.10+)

```bash
git clone https://github.com/salman0butt/codex-seo-skills.git
cd codex-seo-skills
python3 scripts/install_codex.py --dry-run
python3 scripts/install_codex.py
```

Skills are registered in `~/.agents/skills` as links to a shared package in `~/.local/share/codex-seo` (or `$XDG_DATA_HOME/codex-seo`). Existing unrelated skill folders are never overwritten. On filesystems where symlinks are unavailable, the installer copies the skill folder instead. Run `python3 scripts/install_codex.py --with-extensions` to opt in to the 7 unique optional extension skills; extensions require separate tools and accounts. Windows users should use WSL.

Restart your Codex session if the new skills do not appear immediately.

## Use in Codex

Mention skills in your request:

```text
$seo audit https://example.com
$seo-technical https://example.com
$seo-geo https://example.com
$seo-local https://example.com
$seo-google pagespeed https://example.com
```

These are **skill mentions**, not commands to paste into a shell.

## Runtime readiness

```bash
"$HOME/.agents/skills/seo/scripts/codex-seo" doctor --json
```

The SEO scripts have a managed Python environment. Setup and Chromium are **not automatic**; review dependencies and invoke `"$HOME/.agents/skills/seo/scripts/codex-seo" setup` if you choose to install them. Some skills need API keys or services (GSC, GA4, DataForSEO, Firecrawl, etc.). No account or data connection is supplied by this repository.

## Compatibility notes

- Native Codex skill discovery via `SKILL.md` and optional `agents/openai.yaml`.
- Legacy Claude slash commands mapped to Codex skill invocations.
- Claude plugin-root runtime paths replaced with a Codex-managed SEO launcher.
- Specialist agent prompts preserved as reference checklists; Claude hooks/MCP tool names do not automatically become native Codex tools.
- This is a compatibility adaptation, not a guarantee that every paid integration or website-specific workflow works without setup.

## License and attribution

Derived from **[AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo)** (upstream commit `23a2a811f874361d228fc2681acfc0ad66272736`, version 2.4.2). The original MIT license and individual license notices remain in this repository. See `docs/UPSTREAM_README.md` for upstream documentation. Changes for Codex compatibility maintained by [salman0butt](https://github.com/salman0butt).

## Test and readiness gates

- CI checks the 39 skill manifests (30 core + 9 extension manifests), deterministic skill graph, and protected isolated installation.
- CI also runs selected upstream runtime, URL-safety, metadata, schema, GSC and sitemap contracts, plus a managed runtime/Chromium smoke job.
- Local setup requires a stable Python package download connection: interrupted downloads must not result in a `ready: true` status.
- No provider integration is assumed available until the corresponding credentials, external MCP server and consent are configured.
- The historical Codex implementation linked in `docs/LEGACY_CODEX_COMPARISON.md` is proprietary; **do not copy its code into this MIT project**.
