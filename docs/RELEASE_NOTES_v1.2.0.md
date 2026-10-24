# Codex SEO Skills v1.2.0 — Offline multi-page findings and developer handoff

## New

- `site_audit_report.py` converts a **saved v1.1 bounded site crawl JSON** into privacy-preserving Markdown or JSON. It performs **zero network requests** and does not read credentials, send alerts, edit a site, or activate any schedule.
- Counts evaluated and unevaluated pages separately; summarizes validated per-page missing title/meta/H1 and other static-HTML findings.
- Adds **advisory duplicate metadata review** within the sampled pages (`shared-title-review`, `shared-description-review`), with case/whitespace normalization and no automatic claim that repetitions are errors.
- Generates developer handoff tasks with prioritized recommendations and verification instructions, `change_authorized:false`, and **page-N references** instead of exposing page paths, raw titles, descriptions, HTML, token-bearing URLs or unsanitized evidence text.
- Strict fail-closed parsing: 256 KiB input cap, known v1.1 scope, robots-confirmed successful/partial crawl, valid page/request budgets and unique same-origin URLs, bounded observations, known finding IDs and title/description consistency. **Schema validation does not authenticate file provenance**.
- 16+ deterministic offline regression tests and one fabricated example site crawl for reproducible CI testing; updated skill and user documentation.

## Boundaries

No live site crawled for tests, no OAuth, Search Console/GA4, paid provider calls or website edits. The existing v1.1 `site_audit.py` **still** requires an independently authorized public site and both explicit crawl flags for any network acquisition. A small sampled static crawl and offline review are not a full-site audit, indexing/rank tracking, or proof that proposed changes work.

## Example

```bash
"$HOME/.agents/skills/seo/scripts/codex-seo" run site_audit_report.py \
  --site-audit examples/synthetic/site-audit-three-pages.json --format markdown
```

See the [offline multi-page review guide](OFFLINE_SITE_HANDOFF.md) and [bounded crawler security policy](BOUNDED_SITE_AUDIT.md).
