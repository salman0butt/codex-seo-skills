# Codex SEO Skills: Agent Instructions

This repository is a Codex adaptation of [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo), under the MIT license (preserved in `LICENSE`).

## Skill routing
- Use `$seo` for full SEO orchestration only if the user wants a broad audit; prefer an exact leaf skill like `$seo-technical`, `$seo-geo`, `$seo-local`, `$seo-content`, `$seo-schema`, `$seo-google` for targeted tasks.
- These are Codex skill mentions, not shell commands or native Claude slash commands. Read `skills/<name>/SKILL.md` for the workflow.
- `seo-performance` and `seo-visual` are agent-only guides, not registered `$seo-performance` or `$seo-visual` skills. Use them through the audit hub or read their checklists directly.
- All 19 original specialist agent guides are retained in `skills/seo/references/agent-guides/` and `agents/`. Do not assume Claude agent orchestration works in Codex; execute their steps sequentially when agent delegation is unavailable.
- To call a bundled script after installation, use `"${HOME}/.agents/skills/seo/scripts/codex-seo" run <script.py> ...`. Run `... doctor --json` to inspect readiness and `... setup` only after user approval to install dependencies.

## Evidence and safety
- Respect robots.txt, access policy, privacy, and rate limits. Do not run intrusive scans or change live sites without owner approval.
- Distinguish measured metrics from estimates; distinguish lab Lighthouse scores from CrUX real-user field data.
- Don't promise ranking, ChatGPT inclusion, backlinks, 100/100 Lighthouse scores, or automatic search engine indexing.
- Never guess API data, site rankings, performance metrics, or historical trends. Flag missing credentials or unavailable tools.
- Require consent before setting up credentials, installing dependencies, initiating paid API requests, or writing/deploying external changes.
- Preserve attribution to upstream authors.
