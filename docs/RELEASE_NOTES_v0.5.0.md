# Codex SEO Skills v0.5.0 — Explicit Google API connectivity probes

## New functionality

- New opt-in live `live_integration_verify.py`: single-request, read-only PageSpeed Insights SEO lab probe, CrUX field metrics probe, Google Search Console property metadata access check, and GA4 property metadata access check.
- Two access gates: `--live` is mandatory before **any HTTP request**, and `--allow-account-read` plus an explicitly provided, validated property is mandatory for GSC/GA4 lookups. OAuth credential refresh can occur only after both private-access gates. All network calls are absent by default.
- Bounded response bodies and timeout, no auto-retry; HTTP 429, 401/403, 404 (CrUX data not found) and malformed responses become explicit status labels. No invented scores, indexed URLs or traffic.
- No credential values, personal account identifiers, property names, raw API errors, URLs containing query tokens or Google API response bodies are written to the output.
- 14 isolated regression tests that mock Google APIs: private-access gating, public metrics structure, key availability, 404/429 cases, URL/secret rejection, bounded response, and no-network-by-default.
- GitHub CI performs a no-network CLI smoke test and mocks all provider responses; no paid or private API queries execute in CI.
- Updated documentation and skills. The original 30 core skills, 19 guide references and optional source extensions are preserved.

## Actual observed results (2026-10-22)

- The connected Mac reached Google's PageSpeed Insights v5 endpoint with one explicit anonymous `https://example.com/` mobile request, but Google returned **HTTP 429**. No Lighthouse scores were returned or claimed. This is API rate limiting, not an SEO result. The new tool correctly returned `rate_limited` with empty metrics and nonzero exit status.
- The live CrUX API requires a configured Google API key; no such key was verified for this environment. CrUX live metrics were not measured.
- GSC and GA4 property access remain **not verified** because a suitable authorized property and account have not been established for testing. The CLI provides safe, explicit metadata-only probes for when the user configures them.
- No DataForSEO/Firecrawl paid calls, Indexing API notifications, OAuth sign-in or credential copying occurred.

## Install and use

```bash
git clone --branch v0.5.0 https://github.com/salman0butt/codex-seo-skills.git
cd codex-seo-skills
python3 scripts/install_codex.py
"$HOME/.agents/skills/seo/scripts/codex-seo" run integration_doctor.py --markdown
"$HOME/.agents/skills/seo/scripts/codex-seo" run live_integration_verify.py pagespeed --url https://example.com/ --live
```

See [Codex Google integrations](CODEX_INTEGRATIONS.md) for CrUX, Search Console and GA4. The status `verified` means only that the specifically requested endpoint returned the expected response structure, not that other account scopes, measurement types or properties work. Published results are subject to API quotas and access permissions.
