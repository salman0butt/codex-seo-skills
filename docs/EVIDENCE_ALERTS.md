# v0.9.0 — Evidence quality checks and offline advisory change alerts

`seo_evidence_alerts.py` is a **read-only, zero-network** local history inspector. It reads the latest two report snapshots saved by `seo_history.py`; it does not create a snapshot, refresh the underlying GSC/GA4 JSON, query any API, send an email/webhook/push alert, perform website changes, start a scheduler, or install any background task. It does **not** authenticate the origin of user-supplied JSON files.

## Quick checks

```bash
# Inspect latest saved evidence without authorizing comparisons
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_evidence_alerts.py \
  --history-dir "$HOME/seo-private-history" --format markdown

# Confirmed-property comparison of the two latest stored exports
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_evidence_alerts.py \
  --history-dir "$HOME/seo-private-history" \
  --confirm-history-same-property --format json

# Include a page finding comparison ONLY if each ordered audit slot
# is verified to represent the same exact page URL in both snapshots
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_evidence_alerts.py \
  --history-dir "$HOME/seo-private-history" \
  --confirm-history-same-property --confirm-same-page-set --format markdown
```

The input history directory must already exist, be mode 0700, and contain the owner-only v0.8 SQLite DB. The command is read-only and does **not create** empty history. It can inspect a specific earlier snapshot with `--id N` (its baseline is the immediately preceding stored snapshot). It never prints private property IDs, page paths, tokens or raw Google responses; it does show aggregate counts for qualified count-drop alerts. These counts may still be commercially sensitive, so only share output with authorized people.

## Evidence quality vs. alerts

The JSON document distinguishes:

- `quality_findings` — stale/future reporting windows, stale/future page observations, no-data responses, and unavailable providers. These **do not** establish zero clicks, search ranking problems or server issues.
- `alerts` — **local advisory review candidates** for meaningful aggregate count declines or newly observed high-priority raw-HTML issues.
- `suppressed_comparisons` — why a potentially tempting comparison was deliberately withheld (missing baseline, no same-property attestation, unverified metrics, stale evidence, nonadjacent/unequal windows, uncertain page identity, or non-newer page timestamps).

The CLI makes **no notifications**. It produces a stable `id` for each candidate based on snapshot IDs and issue/metric type. An external tool can use the stable ID to deduplicate *after separately authorized integration*, but this release does not implement notifications or acknowledgement state.

### Count-drop alert rules

Defaults (conjunctive; **all** gates required):

1. Both provider reports are marked verified, possess valid metric schemas and have adjacent, equal-length reporting windows.
2. The operator has checked both exports belong to the exact same provider property, and explicitly passed `--confirm-history-same-property`.
3. Current provider evidence ends no earlier than 14 days before the evaluation date and is not from the future.
4. The baseline count is at least **20**, the absolute decline at least **10**, and the relative decline at least **30%**.

Only two count metrics are eligible: **GSC web-search clicks** and **GA4 Organic Search sessions**. CTR or mean position are not alarmed automatically because interpretation requires richer context; Search Console clicks and GA4 sessions cannot be interchanged. Sensitivity is adjustable with `--min-baseline`, `--min-absolute-drop`, `--drop-percent` and `--max-age-days` (bounded values and finite percentages only). An alert is **not** evidence of a Google penalty, a technical incident, statistical significance, or a causal ranking loss.

### New high-priority page findings

Only a newly observed `missing-title` or `missing-h1` finding in the **static HTML** is considered, and only when the operator explicitly attests `--confirm-same-page-set` (same exact URLs, in the same order, in both snapshots). The current observation must be strictly newer and within the freshness window; the number and public origins of the page audits must match. A missing title may be generated dynamically in the rendered page, so verify the rendered DOM and page intent before acting. A previously visible finding disappearing is **not a confirmed fix** and never generates an automatic resolved notification.

### Offline synthetic replay

The following demonstrates both a *suppressed* comparison and a permitted advisory count-drop candidate using **fabricated sample data**. It creates files only under the explicit demonstration directory. The example GSC reports are not real website measurements.

```bash
mkdir -p "$HOME/seo-test-alert-history"
chmod 700 "$HOME/seo-test-alert-history"
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_history.py record \
  --history-dir "$HOME/seo-test-alert-history" \
  --gsc-current examples/synthetic/gsc-previous.json
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_history.py record \
  --history-dir "$HOME/seo-test-alert-history" \
  --gsc-current examples/synthetic/gsc-current-drop-example.json

# Suppressed: property identity is redacted and cannot be inferred
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_evidence_alerts.py \
  --history-dir "$HOME/seo-test-alert-history" --as-of 2026-10-23
# For this *known identical synthetic property*, an explicit operator attestation
# enables a count-drop advisory alert.
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_evidence_alerts.py \
  --history-dir "$HOME/seo-test-alert-history" --as-of 2026-10-23 \
  --confirm-history-same-property --format markdown
```

The `--as-of` option supports reproducible evaluation against a supplied UTC date (default is today UTC); it does not alter timestamps in input reports. The fixture produces a review notice only because all stated policy gates are satisfied; no real SEO measurement or external notification is implied.

## Validation and limitations

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests -p test_seo_evidence_alerts.py -v
python3 scripts/generate_skill_map.py --check
python3 scripts/portability_check.py --strict
```

The tests cover stale/future evidence, invalid input, explicit identity attestation, low-baseline suppression, proportional and absolute thresholds, response corruption, stable IDs, page freshness/order and read-only operation. The original local history can still be managed independently through `seo_history.py` with explicit destructive-operation approval. If no snapshots exist, report an error rather than inventing a healthy outcome.
