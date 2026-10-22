---
name: get-started
description: Start a scoped SEO task by asking for the target and evidence, selecting the appropriate specialist, and explaining unavailable integrations.
license: MIT
metadata:
  author: salman0butt
  version: "0.2.0"
  category: seo
---
# Start an SEO task in Codex

Use this skill to route an SEO request safely. This is an original Codex-specific onboarding workflow, informed by the public ChatGPT SEO capability inventory; no legacy proprietary Codex code is imported.

## Workflow
1. Identify the user's desired outcome: technical site audit, local SEO, generative-search visibility, site performance, content brief, metadata, structured data, or report handoff.
2. Collect the minimum necessary input already available: canonical site or page URL, target market and language, ownership/permission, available exports, and any requested output format. Do not request secrets in the chat.
3. Prefer one narrow skill over the full audit: `$seo-technical`, `$seo-local`, `$seo-geo`, `$seo-performance`, `$seo-visual`, `$seo-content`, `$seo-schema`, `$seo-google`, or `$seo-handoff`. Choose `$seo-audit` for broad, cross-domain requests.
4. Explain which data can actually be accessed. Distinguish public observations from Google Search Console or GA4 exports, configured API calls and assumptions.
5. Hand off the task to the selected skill in the current Codex context. If skill mentions are unavailable, read the corresponding local `skills/<name>/SKILL.md` and follow its instructions directly.
6. Produce an evidence ledger: observation, source/date, consequence, recommended action, verification procedure. Do not fabricate traffic, indexation or search rankings.

## Completion contract
Provide a specific skill route, stated inputs, blocked dependencies, and the first actionable step. Never pretend that a reference to a skill executed a tool or approved external changes.
