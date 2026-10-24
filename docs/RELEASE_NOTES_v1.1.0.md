# Codex SEO Skills v1.1.0 — Consent-gated small-site audit

## New

- `site_audit.py`, an **opt-in, read-only** bounded public-site crawler. Uses the existing one-page evidence parser to sample up to 12 static HTML pages on the exact seed origin. User must provide both `--live` and `--allow-public-crawl`.
- **Fail-closed robots.txt handling**: fetches plain-text robots policy before any HTML, honors disallows and Crawl-delay with at least 1 second pacing, stops on errors and rate-limiting, and refuses robots redirects outside the scope. Missing/malformed policy is a blocked crawl, not an implicit allowance.
- **SSRF/redirect defense**: shared DNS-validated, pinned HTTP fetches; no automatic redirect following; per-hop strict same-origin and robots rechecks; no local/private host targets even when single-page staging overrides are configured. Query URLs, credentials, external links, scripts, forms, private/admin/account paths and non-HTML assets excluded; canonical-link tokens removed before reporting.
- **Hard budgets**: 1–12 pages, 37 network requests maximum, 2 redirects per page, 2 MiB decompressed HTML/page, 128 KiB robots policy, 120 queued candidates; request timeouts, no concurrency, and no automatic retries.
- Evidence-based, per-page findings and clear partial/blocked statuses. Explicit unknowns; no fabricated SEO scores, site-wide completeness, indexing, ranking, traffic or Core Web Vitals claims.
- New deterministic mock regressions, offline-by-default CI check, dedicated usage/security guide, skill guidance, and stable source/manifest smoke checks.

## Security and scope

No private Google account, paid provider, form submission or website modification. No live domain was scanned during regression tests. Use only on a website you are authorized to crawl, with respect for its robots/access policy and server resources.

## Example

```bash
# Default: zero network requests
"$HOME/.agents/skills/seo/scripts/codex-seo" run site_audit.py https://example.com/

# Requires independently confirmed site owner permission
"$HOME/.agents/skills/seo/scripts/codex-seo" run site_audit.py \
  https://example.com/ --live --allow-public-crawl --max-pages 5 --format markdown
```

See [bounded small-site audit guide](BOUNDED_SITE_AUDIT.md) and the [v1 production scope matrix](PRODUCTION_READINESS_v1.0.0.md). Native Windows installation, private Google API verification and Claude-only parallel agents remain outside this release's scope.
