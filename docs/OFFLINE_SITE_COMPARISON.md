# v1.3.0 — Offline before/after review of bounded site audits

`site_audit_compare.py` compares two **previously saved** v1.1 bounded public-site JSON audits, internally matching only exact URLs but reporting **only page-number references**. It never fetches a website, reads Google credentials, sends alerts or messages, installs scheduling, or changes content. Results are advisory and source files are treated as **untrusted** even when the JSON schema is valid.

## Safe start

```bash
# Unattested comparison: validates both files, reveals counts only,
# and intentionally exits 2 with comparison_status=same_site_not_attested.
"$HOME/.agents/skills/seo/scripts/codex-seo" run site_audit_compare.py \
  --before examples/synthetic/site-audit-before.json \
  --after examples/synthetic/site-audit-after.json --format json

# Only after an operator independently confirms that both files contain
# successive observations from the same website they are authorized to audit:
"$HOME/.agents/skills/seo/scripts/codex-seo" run site_audit_compare.py \
  --before examples/synthetic/site-audit-before.json \
  --after examples/synthetic/site-audit-after.json \
  --confirm-same-site --format markdown
```

The example snapshots above are **fictional** and intended only as safe tests. For real work, acquire each source JSON separately using the existing `site_audit.py` command, **only on a public site you own/administer or have explicit authorization to crawl**, respecting its separate `--live --allow-public-crawl` flags, robots policy, rate limits and 12-page hard limit. This offline tool accepts neither `--live` nor private provider credentials.

## Comparison gates

- Input files: maximum **256 KiB each**; both must validate as bounded same-origin v1.1 audits with a robots-allowed seed, coherent page and request limits, unique same-origin, query-free page URLs, known finding IDs, valid title/description consistency, and timezone-aware observation timestamps.
- Before/after must have the **same exact origin** (scheme, host and port in saved source), `--confirm-same-site` must be present, and the overall after snapshot timestamp must be **strictly later** than the earlier snapshot. The manual attestation means the operator reviewed ownership, property identity, and provenance externally; software cannot authenticate supplied JSON.
- Individual page comparisons require exact matching URL strings and **both pages successfully evaluated as static HTML**, with a strictly newer observed timestamp for the after version. Page ordering may change; the tool aligns URLs internally without revealing paths. Pages not in both samples are **not assumed added/deleted**.
- Changed finding IDs are split into `newly_observed_findings` and `findings_no_longer_observed`, explicitly **NOT "fixed"**. Metadata changes report only whether normalized title/description values differ; the values themselves are never copied.
- Output is limited to `page-1`, `page-2`, etc., per respective input file, finding IDs from an allowlist, status/reason codes and known limitation text. It excludes site origin, page paths, titles, meta descriptions, raw HTML, tokens and unknown upstream fields.
- If the after source is partial, the status remains `partial_sample_comparison`; comparisons apply only to eligible matched pages, and **never** imply whole-site coverage. If no page is eligible, `no_eligible_page_comparisons` is an unsuccessful status.

The tool emits JSON or Markdown to stdout; it does not write files. To save output locally, use a private destination with restrictive permissions and obtain site-owner approval before sharing results. A comparison does not establish a ranking/indexing improvement, page deployment, traffic change, or technical resolution.

## Reproducibility

```bash
python3 -m unittest discover -s tests -p test_site_audit_compare.py -v
python3 scripts/generate_skill_map.py --check
python3 scripts/portability_check.py --strict
```

All tests are offline and include consent suppression, same-origin mismatch, chronological UTC offsets, reordered matching pages, missing/unevaluated observations, input rejection, secret redaction, and actual no-network/no-file-write behavior. No live site was crawled to build the synthetic fixtures.
