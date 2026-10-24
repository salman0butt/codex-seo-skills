# v1.2.0 — Offline bounded-site review and developer handoff

`site_audit_report.py` analyzes a **previously saved JSON file** from the v1.1 `site_audit.py` bounded public crawl. It identifies repeated titles or meta descriptions **only within the sampled, static HTML**, groups the known individual-page findings and generates advisory developer tasks. It never initiates a crawl, fetches a URL, contacts Google, reads tokens, sends notifications, publishes content or edits a website.

## Workflow

First obtain a crawl JSON only on a public website you own/manage or are explicitly authorized to audit, respecting the opt-in crawler's robots.txt, request pacing and hard budgets. The crawler's `--live --allow-public-crawl` flags govern the *separate initial acquisition*; they are not necessary for the offline review.

```bash
# First use synthetic fixture from the repository (not real website data):
"$HOME/.agents/skills/seo/scripts/codex-seo" run site_audit_report.py \
  --site-audit examples/synthetic/site-audit-three-pages.json --format markdown

# Offline analysis of an already saved, authorized site's crawl:
"$HOME/.agents/skills/seo/scripts/codex-seo" run site_audit_report.py \
  --site-audit /private/path/saved-site-audit.json --format json

# For a private local Markdown output, redirect to a protected file using
# your OS's existing permissions/umask and do not commit it:
umask 077
"$HOME/.agents/skills/seo/scripts/codex-seo" run site_audit_report.py \
  --site-audit /private/path/saved-site-audit.json --format markdown > site-handoff.md
```

The tool **only prints the result**. It never installs a scheduler or writes a file itself. It rejects inputs larger than **256 KiB**, unexpected schemas, impossible page/request budgets, non-HTTP(S) or inconsistent-origin URLs, duplicated page URLs, unknown finding types, contradictory title/description observations, and malformed timestamps. It does not authenticate the original JSON or verify a claimed crawl happened. Do not treat an operator-supplied file as trusted measurement merely because it passes schema checks.

## What it reports

- `pages_recorded`, `pages_evaluated`, `pages_not_evaluated` distinguish evaluated HTML from pages with HTTP errors or non-HTML content. Neither a missing audit nor a successful request proves a page is healthy.
- `finding_counts` counts the validated v1.1 **raw HTML** checklist findings, including missing title, H1 and meta description.
- `shared-title-review` and `shared-description-review` are raised when two or more **evaluated** pages have identical metadata after case/whitespace normalization. Repetition is a **review signal**, not intrinsically an error or a ranking penalty.
- `handoff_tasks` provide proposed actions, verification instructions, and `change_authorized:false`. Nothing is assigned, deployed or changed on the website.
- `page-1`, `page-2`, etc. refer to entries **in order in the original private crawl JSON**. The handoff omits page paths, original titles/descriptions, arbitrary page content and raw untrusted finding text. If the owner needs exact URL assignments, they should consult the original protected input, not publish it in the handoff.
- `scope` is `offline-bounded-site-audit-handoff`; `source_authenticity` is always `unverified_saved_JSON`; `network_requests`, `notifications_sent`, and `site_changes_made` remain zero.

The handoff does **not** claim complete site coverage, rendered-page parity, SEO scores, search ranking/indexing status, measured Google Analytics or Search Console results, statistical significance, or implementation success. For live site acquisition use the separate [bounded crawl policy](BOUNDED_SITE_AUDIT.md).

## Testing

```bash
python3 -m unittest discover -s tests -p test_site_audit_report.py -v
python3 scripts/site_audit_report.py --site-audit \
  examples/synthetic/site-audit-three-pages.json --format json
python3 scripts/generate_skill_map.py --check
python3 scripts/portability_check.py --strict
```

The tests use entirely fictional data, include malformed and oversized JSON, inconsistent status/schema/URLs, privacy and hostile HTML payloads, and a no-network/no-file-write CLI contract. The synthetic sample deliberately produces five advisory tasks for three fabricated pages. No real website was crawled to create this example.
