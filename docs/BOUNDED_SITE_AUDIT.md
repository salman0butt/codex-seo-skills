# v1.1.0 — Bounded, consent-gated public-site audit

This feature addresses a v1.0 limitation: a single-page static-HTML audit cannot show obvious issues on a small group of linked pages. The `site_audit.py` command follows a **small, explicitly bounded** sample of public links on **one exact origin**. The report gives per-page findings but makes **no assertion of comprehensive site coverage, indexing, search rank, user traffic, or actual SEO effect**.

## Safety and eligibility

- Run only against a public site you own, administer, or are authorized to audit. Confirm access rules and do not use this to scan unrelated third-party sites.
- The default CLI makes **zero network requests**. A run needs **both** `--live` and `--allow-public-crawl`, including when invoked by an automation or agent. It never acquires OAuth tokens, opens a paid API, edits the website, submits a form, or logs in.
- Only HTTP(S) URLs in the **exact same origin**, including protocol and port, can be requested. No cross-origin redirects, redirects to queries, private/reserved addresses, local/staging/Tailscale allowlist bypasses, credentials, JavaScript URLs, or HTML form submissions.
- It fetches `/robots.txt` *first*. It refuses a missing, non-plain-text, malformed or inaccessible robots policy; honors rules for the descriptive `CodexSEO-SiteAudit` user agent; enforces `Crawl-delay` (or minimum 1 second between request starts); and stops on 429/5xx without retry. A redirect to a disallowed URL is blocked **before** fetching that URL.
- Limits: **1–12 pages**, **1–2,097,152 decompressed HTML bytes** per page, **128 KiB robots policy**, **2 redirects per request**, **37 network requests maximum**, **120 discovered candidate links** and no concurrency. Times out requests and stops on exceeded response sizes. There is no sitemap or recursive crawling beyond the bounded queue. Robots rules are not equivalent to owner permission.
- Query strings and fragments in candidate page URLs and canonical link URLs are not requested or preserved; arbitrary visible page text may still contain sensitive content, so review generated reports before sharing. The parser ignores login, account, checkout, admin, search and common non-HTML paths; public pages may still contain proprietary information, so review output before sharing. `--max-pages` and `--max-bytes` can only **reduce** the baked-in limits.
- All fetches use the shared `url_safety.safe_requests_get` with strict DNS validation and pinning. Automatic redirects are disabled; each hop gets a policy check and a new DNS-validated request. Live fetches require the explicit managed Python runtime `codex-seo setup` to have been run.

## Usage

```bash
# No-network dry default: emits a blocked diagnostic with network_requests=0
"$HOME/.agents/skills/seo/scripts/codex-seo" run site_audit.py https://example.com/

# Only after confirming site ownership/permission and reading robots/access policy:
"$HOME/.agents/skills/seo/scripts/codex-seo" run site_audit.py \
  https://example.com/ --live --allow-public-crawl --max-pages 5 --format markdown

# Maximal bounded audit (never exceeds 12 pages):
"$HOME/.agents/skills/seo/scripts/codex-seo" run site_audit.py \
  https://example.com/ --live --allow-public-crawl --max-pages 12 --format json
```

The example URL is illustrative; **no live crawl of that site was performed during the offline regression suite**. Use a site you are permitted to audit, and follow its robots policy and rate limits. One-time public requests may still use network resources and be charged by the host.

## Interpreting results

- `scope`: `bounded-same-origin-static-html-crawl`, not full-site discovery.
- `robots_status`: whether an interpretable policy was loaded and the seed URL was permitted.
- `pages`: each reached page's status, title/description/H1/schema observations and evidence-linked `quick_audit` findings. `findings` are suggestions for human review; absent findings are not proof of healthy SEO or ranking.
- `stop_reason`: `page_limit_reached`, `discovery_queue_empty`, or a clear denial/error. `outcome=partial` indicates an early interruption; `outcome=blocked` indicates a denied crawl. Never market partial results as site-wide coverage.
- `network_requests`, `page_limit`, `discovered_candidate_count` and `skipped_robots_paths`: auditable budgets, not completeness metrics.
- `seo_score`: always `null`. No automatic Lighthouse, Core Web Vitals, Google Search Console, GA4, backlink or SEO ranking claims.

## Verification

```bash
# Needs only the project's isolated test prerequisites (bs4, requests)
python3 -m unittest discover -s tests -p test_site_audit.py -v
python3 scripts/portability_check.py --strict
python3 scripts/generate_skill_map.py --check
```

The tests mock all public fetches to exercise consent gates, DNS/private target rejection, robots fail-closed behavior, crawl-delay, same-origin redirects, blocked pages, link filtering, 429 stop, output redaction, hard budgets and the full static HTML parser. CI does not crawl an arbitrary target or call private APIs. The single-page `quick_audit.py` remains available when only one page needs checking.
