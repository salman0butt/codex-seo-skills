---
name: seo-performance
description: Evaluate performance using Core Web Vitals, page-load evidence and mobile diagnostics, distinguishing lab metrics from CrUX field data.
license: MIT
metadata:
  author: salman0butt
  version: "0.2.0"
  category: seo
---
# Performance and Core Web Vitals SEO checks

The specialist reference checklist is at `../seo/references/agent-guides/seo-performance.md` (upstream MIT). Follow its verified thresholds and reporting principles.

## Procedure
1. Verify the requested public URL, test device, location and date. Treat a URL or property requiring credentials as blocked until authorized.
2. For live PageSpeed Insights data run `"${HOME}/.agents/skills/seo/scripts/codex-seo" run pagespeed_check.py <url> --strategy mobile --json` only when the managed runtime and internet are available. Use `--crux-only` for field metrics when appropriate. Do not claim CrUX exists for every URL.
3. Interpret LCP, INP, CLS and diagnostics using `../seo/references/cwv-thresholds.md`. Split Lighthouse lab scores and browser field measurements into separate columns and cite the measured date.
4. Assess resource-loading delays, render blocking, images, lazy loading, caching and font strategies from inspected evidence. Avoid speculative performance savings.
5. If the API is unavailable, document that accurately and give manual Chrome/Lighthouse reproducibility steps. Do not invent scores.
6. Offer changes and verification only within the requested codebase; require authorization before external deployment.

## Output
Measured lab/field metric table (or an explicit `not measured` status), reproducible observations, prioritized hypotheses, code-level recommendations where source is available, and retest criteria.

## Live provider connection check (Codex v0.5)

Before promising PageSpeed or CrUX field metrics, run offline `integration_doctor.py`. With an authorized public URL and explicit one-call live consent, use `live_integration_verify.py pagespeed --url <public-url> --live` or `crux --url <public-url> --live`. A 429 / 404 / missing key is missing data, not performance evidence. For full Lighthouse lab detail use the existing `pagespeed_check.py` only when authorized.
