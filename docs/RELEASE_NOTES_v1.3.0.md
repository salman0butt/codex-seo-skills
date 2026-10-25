# Codex SEO Skills v1.3.0 — Offline bounded-site before/after comparisons

## New

- `site_audit_compare.py` compares two already saved v1.1 static-site audit JSON files, with **zero network requests**, zero credential access, no provider calls, messages, notifications or website changes.
- Mandatory **operator `--confirm-same-site` attestation**, exact saved origin equality, and a strictly later after-snapshot time. No comparison data is exposed by default without attestation.
- Exact URL matching performed **privately in memory**; page order can change. Outputs use only before/after `page-N` identifiers, not the URL or its path, and omit titles, descriptions, arbitrary source data and raw findings text.
- Only successfully evaluated static-HTML pages with strictly newer per-page observations are compared. Partially sampled runs stay labeled partial; missing, failed or non-newer pages are separately suppressed. No overlapping eligible pages yields an unsuccessful result.
- Distinguishes newly observed finding identifiers, findings no longer observed (**not proof of fixes**), and normalized title/description field changes (without copying values). Never implies site-wide coverage, ranking/indexing movement, or a confirmed incident.
- 19 new offline regression tests; two entirely fictional saved-site snapshots for demonstration; expanded GitHub CI, skill guidance and privacy/safety documentation.

## Limitations and provenance

- Source JSON can be validated for shape and consistency but **cannot be cryptographically authenticated**. The user must verify source ownership and provenance before confirming comparison.
- The earlier and later files may sample different pages. Absence from a bounded crawl does not demonstrate a page was deleted, and absence of a previous finding does not prove a fix.
- No real website was crawled for these fixtures, and no private Google or paid provider account was accessed.

## Example

```bash
"$HOME/.agents/skills/seo/scripts/codex-seo" run site_audit_compare.py \
  --before examples/synthetic/site-audit-before.json \
  --after examples/synthetic/site-audit-after.json \
  --confirm-same-site --format markdown
```

The fixture is imaginary and safe for local testing only. [Read the comparison guide](OFFLINE_SITE_COMPARISON.md) and [bounded crawl policy](BOUNDED_SITE_AUDIT.md).
