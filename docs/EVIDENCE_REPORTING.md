# Evidence-based SEO reports and developer handoffs (v0.7.0)

The `seo_report_builder.py` CLI is a **local, zero-network** report composer. It accepts bounded JSON exported by `private_seo_report.py` (GSC/GA4) and `quick_audit.py` (public HTML), validates the supported schemas, and produces Markdown or JSON. It never signs into an account, refreshes OAuth, calls an API, deploys anything, indexes a URL, or creates a paid request. It does not read credentials.

## 1. Generate source evidence

Only when you are explicitly authorized to read the property, run the existing private exporter with its two approval flags; for example:

```bash
# Example property values are placeholders: use only your authorized values.
"$HOME/.agents/skills/seo/scripts/codex-seo" run private_seo_report.py gsc \
  --property sc-domain:example.com --days 28 --live --allow-account-read > gsc-current.json
"$HOME/.agents/skills/seo/scripts/codex-seo" run private_seo_report.py ga4 \
  --property 123456789 --days 28 --live --allow-account-read > ga4-current.json

# One public page, read-only HTTP GET (or use a previously saved JSON report).
"$HOME/.agents/skills/seo/scripts/codex-seo" run quick_audit.py https://example.com/ --json > page-audit.json
```

`--live` is **not** a flag on the report builder. Any live/private API access belongs exclusively to the separate source-export step, with its own permission gate. Store input/output files locally and do not commit private exports to Git. These files contain aggregate metrics and may still be commercially sensitive.

## 2. Generate a report

```bash
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_report_builder.py \
  --gsc-current gsc-current.json --ga4-current ga4-current.json \
  --quick-audit page-audit.json --format markdown --output seo-report.md
```

For historical comparisons, provide an earlier **adjacent, same-length period** for each selected provider:

```bash
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_report_builder.py \
  --gsc-previous gsc-previous.json --gsc-current gsc-current.json \
  --ga4-previous ga4-previous.json --ga4-current ga4-current.json \
  --confirm-same-property --format json --output seo-report.json
```

The source exports intentionally redact property IDs. **`--confirm-same-property` is your explicit attestation**, after independently verifying that the current/previous exports for each provider belong to the same property; the builder cannot prove this. Without it, the builder displays current metrics but **does not calculate changes**. If periods overlap, differ in length, or have gaps, no historical comparison is computed even with the flag. Previous reports alone are not sufficient.

For safely shareable developer tickets, supply one or more public page audits with repeated `--quick-audit`, up to ten. Each issue becomes a *suggested*, not authorized, handoff task with source ID (`audit-1`, etc.), evidence type, priority, action, acceptance test, and verification. Public URL paths are redacted by default, but the original source JSON can be used by the authorized implementation team to identify an exact page. Do not use the generated tasks as approval to publish or deploy.

## 3. Interpret correctly

- GSC's `clicks`, `impressions`, `ctr_percent` and `average_position` describe Google search result activity. GA4's Organic Search `sessions`, `totalUsers`, and `engagedSessions` describe website activity. **Never add or equate them.** Different tracking consent, timezones, attribution and filters can yield differences.
- Relative percentage changes are computed only for count metrics with a nonzero baseline. GSC CTR changes are in **percentage points**. Average position changes are numerical differences, not a causal ranking-improvement claim.
- `no_data`, rate limits, permission errors, and empty reports do not establish zero traffic. No missing or invalid metrics are invented.
- **Source authenticity is not cryptographically verifiable:** the report builder checks schemas but cannot prove that supplied JSON originated from Google or from this tool. This limitation is written in every output. If data provenance matters, retain an authorized external audit trail.
- Raw HTML observations are not a whole-site crawl, rendered JavaScript audit, Core Web Vitals field report, or accessibility certification. A missing canonical is a review, not an automatic penalty. Decorative images can have empty alt text.
- Generated reports have **zero provider/API requests** and contain no input property IDs, visitor identifiers, raw queries, page paths, arbitrary HTML input, or provider response bodies. They can include aggregate traffic metrics; obtain client permission before sharing.

## 4. Safety and reproducibility

- Each JSON input is capped at 256 KiB; the command accepts at most 10 page audits. Invalid, blocked, unsupported and internally contradictory evidence is rejected with a sanitized error.
- Output files are created with owner-only permissions using an atomic write, and **existing reports are not overwritten unless you pass `--overwrite`**. An input file cannot be used as its own output path; symlink output paths are rejected.
- The CLI runs offline, has no local auto-scheduler or stateful tracker, and does not silently collect snapshots. Retain previous exports intentionally if you plan period-over-period reports.
- For a complete runnable illustration, see [`examples/synthetic/`](../examples/synthetic/README.md). The sample metrics are **fabricated fixtures**, not website performance results.

## 5. Validation

```bash
python3 -m unittest discover -s tests -p test_seo_report_builder.py -v
python3 scripts/generate_skill_map.py --check
python3 scripts/portability_check.py --strict
```

GitHub Actions also replays the synthetic sources through the production Codex CLI wrapper, asserting that historical comparisons and developer tickets render correctly with **zero network access**. Real private Google access is not part of CI.
