# Codex SEO Skills v0.9.0 — Offline evidence quality and advisory alerts

## Added

- `seo_evidence_alerts.py`, a **strictly read-only**, zero-network inspector of the private local v0.8 history database, with JSON and Markdown output. It does not schedule tasks, send notifications, write files, access Google APIs, refresh OAuth or bill providers.
- Explicit `quality_findings` for stale/future windows, missing provider measurements, no-data responses and stale/future page audits, separate from actual `alerts` and `suppressed_comparisons`.
- Conservative advisory aggregate count-drop rules for Search Console web clicks and GA4 Organic Search sessions: default ≥20 baseline, ≥10 absolute decline and ≥30% relative drop, using verified, fresh, adjacent equal-length windows and explicit same-property operator attestation. No causal ranking claims or cross-metric equivalence.
- Optional high-priority static page finding alerts only for newly observed missing titles or H1 elements, where exact ordered URL identity has been independently attested and the current observation is newer and fresh. No automatic issue-resolution claims.
- Stable, locally derived alert IDs and bounded policy thresholds; no persisted acknowledgement, email, webhook or automatic notification.
- 18 regression tests for comparison gating, missing/zero data distinction, freshness, corrupt history, low sample suppression, chronological validation and read-only execution. A new explicitly fictional drop example is provided for independent CI smoke tests.
- Updated skills and documentation: [`docs/EVIDENCE_ALERTS.md`](EVIDENCE_ALERTS.md).

## Evidence and limitations

- GitHub CI must pass the exact tagged commit across Python 3.11/3.12, managed Linux Chromium, macOS runtime, existing SEO security contracts and the new history alert diagnostics.
- The source JSON is operator-supplied and schema-validated, **not cryptographically authenticated**. The only successful example trend is a **fictional synthetic fixture**. No real private Google property was accessed, no paid provider was queried and no website was modified.
- Even when permitted, an alert is an **advisory review item**, not a verified incident, actual ranking loss, statistical significance or automatic fix. No recurring task is installed or enabled.

## Example

```bash
git clone --branch v0.9.0 https://github.com/salman0butt/codex-seo-skills.git
cd codex-seo-skills
python3 scripts/install_codex.py
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_evidence_alerts.py \
  --history-dir "$HOME/seo-private-history" --format markdown
```

Existing snapshots are required; see [the evidence alert guide](EVIDENCE_ALERTS.md).
