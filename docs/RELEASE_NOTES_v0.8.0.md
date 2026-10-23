# Codex SEO Skills v0.8.0 — Private offline history and scheduled replay templates

## New

- `seo_history.py`: local SQLite **owner-only 0700/0600** history of sanitized v0.7 evidence reports. Same normalized input fingerprint replays are idempotent even under concurrent invocations; changed or reverted evidence is recorded as a new observation.
- Optional local Markdown report snapshot (`--export-markdown`) with no-clobber atomic creation and owner-only permissions, preserving original report content during repeat runs.
- `list` and `show` for explicit local inspection; bounded `prune --keep N` that deletes only with `--confirm-prune`. No automatic deletion; separately exported Markdown files remain until explicitly cleaned up.
- Safe change summaries with noncausal provider metric differences **only after explicit same-property attestation** and adjacent equal-duration windows. Checklist finding appearance/disappearance is compared only after an independent same-URL-set attestation, and is never labeled as a confirmed fix.
- `seo_schedule_template.py`: reviewable templates for weekly Monday 09:00 **cron** or **macOS launchd**. These print text, **do not install schedules**, and replay locally saved evidence. No automatic provider/API data acquisition, OAuth refresh, website crawling, index submission, email, telemetry, or paid operations.
- New tests for replay, concurrency and permissions, failure-safe malformed/corrupt history, symlink rejection, no-clobber exports, retention and scheduler templates. Run under Python 3.11/3.12 CI plus managed macOS/Linux smoke tests.
- Documentation: [offline history and schedules](OFFLINE_HISTORY.md), updated skills and risk boundaries, extra Git ignore rules.

## What is and is not verified

- Tests and demos use **synthetic** source JSON; no real Google Search Console or GA4 property was read in developing this version.
- A period-over-period comparison requires a human assertion of same-property identity; the redacted JSON itself cannot verify it. A missing checklist finding does **not** prove a developer fixed anything.
- Cron/launchd templates replay saved files only. You must **deliberately review and activate** any desired schedule. Stale files will not produce new snapshots or refreshed SEO reports.
- Data is saved locally and should be handled as commercially sensitive even after excluding identifiers and raw queries. No background job is enabled by this release.

## First run

```bash
git clone --branch v0.8.0 https://github.com/salman0butt/codex-seo-skills.git
cd codex-seo-skills
python3 scripts/install_codex.py
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_history.py record \
  --history-dir "$HOME/seo-private-history" \
  --gsc-current examples/synthetic/gsc-current.json \
  --quick-audit examples/synthetic/quick-audit.json --export-markdown
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_history.py list \
  --history-dir "$HOME/seo-private-history"
```

**The example metrics are fabricated test fixtures**, not website measurements. For real usage, use authorized saved exports and follow [the full guide](OFFLINE_HISTORY.md).
