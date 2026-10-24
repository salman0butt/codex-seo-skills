# Synthetic SEO reporting fixtures — NOT real website measurements

Every number in these fixtures is **fictional** and intended only for documentation, CI and report-generation regression tests. Their `result: verified` and `live_verified: true` values simulate successfully completed API responses; **they do not prove any real provider request was made.** The v0.7 builder only validates JSON shapes and never authenticates file origin. Do not publish these numbers as actual traffic or client SEO results.

All fixtures cover adjacent 28-day periods, with a fake page audit for `https://example.com/services/`. They contain no real credentials, private search queries or analytics property IDs.

From the repository root after `codex-seo setup`:

```bash
./scripts/codex-seo run seo_report_builder.py \
  --gsc-current examples/synthetic/gsc-current.json \
  --gsc-previous examples/synthetic/gsc-previous.json \
  --ga4-current examples/synthetic/ga4-current.json \
  --ga4-previous examples/synthetic/ga4-previous.json \
  --quick-audit examples/synthetic/quick-audit.json \
  --confirm-same-property --format markdown
```

For real inputs, export reports with `private_seo_report.py` and `quick_audit.py` only for properties and pages you're authorized to inspect. Use `--confirm-same-property` **only after independently establishing that each provider's historical and current exports are from the same property**, because the safe export files redact property identifiers. Adjacent equal-length periods are required; otherwise the comparison is refused. Output files are local, permission-restricted and never overwritten without `--overwrite`.

### v0.9.0 offline alert fixture

`gsc-current-drop-example.json` is another **fabricated** source report (10 clicks rather than 20 during an adjacent synthetic reporting window). Use it only to test the alert's operator-attested baseline, absolute and relative gates. These values are not collected Google Search Console results.

### v1.2.0 fabricated bounded site handoff

`site-audit-three-pages.json` is **entirely synthetic**. It describes three fictitious pages with two repeated metadata pairs and one missing title/H1/description. Running the offline `site_audit_report.py` on it produces exactly five advisory tasks, including two cross-page review items. No real website or private property was queried, and the output intentionally omits even these fictional page paths/content.
