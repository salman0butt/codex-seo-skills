# Codex SEO v0.8 — Private offline history and scheduled replay

**This workflow does not access Google, refresh tokens, fetch websites, create a real schedule, send email, or deploy changes.** It only processes **previously saved and authorized** JSON exports. A cron/launchd schedule will replay whatever files are at the paths you provide. It will **not** fetch fresh GSC/GA4 data, and replaying stale evidence will not produce a new snapshot. Configure private Google report export separately and only with property authorization.

## Record and inspect history

The `seo_history.py` runner uses SQLite in a **private 0700 directory** (default `~/.local/share/codex-seo-history`; database mode `0600`). It accepts the same source files as `seo_report_builder.py` and sanitizes them through that existing validation path. It records each distinct normalized evidence state, while omitting the report generation timestamp from its fingerprint so repeat invocations are idempotent.

```bash
# Demonstration using fictional, explicitly labeled synthetic inputs:
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_history.py record \
  --history-dir "$HOME/seo-private-history" \
  --gsc-current /path/to/saved/gsc-current.json \
  --quick-audit /path/to/saved/page.json \
  --export-markdown

"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_history.py list \
  --history-dir "$HOME/seo-private-history" --limit 20
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_history.py show \
  --history-dir "$HOME/seo-private-history" --id 1
```

`--export-markdown` is opt-in. It saves owner-only Markdown reports under `history-dir/reports/snapshot-000001.md`, etc. The exporter never overwrites an existing snapshot. Multiple processes performing an identical run concurrently create **only one** SQLite snapshot; historical reversion after an intervening change records a new observation. List/show only read local history.

Comparisons of private properties cannot be proven from redacted JSON. For adjacent equal-length reporting windows, compare with **both** underlying property exports independently confirmed as the same account property, then optionally supply `--confirm-history-same-property`. Page audit comparisons also require the operator to confirm that each ordered audit slot represents **the exact same page URL** via `--confirm-same-page-set`. Without this, the tool never claims that a previously reported finding disappeared. Even with the confirmation, a missing finding is **not proof of a fix**.

## Generate templates for weekly schedules (without installing them)

Run only after successfully recording once manually and ensuring your private history directory exists. These commands **print text**; they do not activate a schedule.

```bash
# macOS: launchd property-list template, Monday 09:00 local time
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_schedule_template.py \
  --platform launchd --history-dir "$HOME/seo-private-history" \
  --gsc-current "$HOME/seo-saved/gsc-current.json" > offline-seo-weekly.plist

# Linux/macOS cron line, Monday 09:00 local time
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_schedule_template.py \
  --platform cron --history-dir "$HOME/seo-private-history" \
  --gsc-current "$HOME/seo-saved/gsc-current.json" > offline-seo-weekly.cron.txt
```

After inspecting the resulting local file, you can **explicitly choose** to install the schedule through your OS's normal cron or launchd configuration. Installation, enabling, disabling, logging and troubleshooting remain user-controlled. The launchd sample uses an owner-only umask and private history log paths. The cron sample uses `umask 077`, shell-quotes paths, and has no network flags or paid-provider calls. **Do not commit local generated schedules** because they include local file paths. The generator does not use credentials or query the provider.

The weekly schedule replays stored evidence and is intentionally idempotent. It does **not** run an autonomous Google Search Console export, GA4 query, website crawl, indexation notification, or other API request. Any periodic acquisition of new data must be separately configured, consented to, and auditable; this v0.8 feature is solely history/analysis of local exports.

## Retention and privacy

History contains sanitized aggregate metrics and may still be commercially sensitive. Keep it off public version control and back it up only with an approved secure destination. The local DB and Markdown files are created with restrictive permissions. No source JSON, property identifiers, page paths, raw provider responses, tokens or credential values are deliberately copied into the stored report. Input-file **origin is not cryptographically verified**.

Deleting history is **always a separate explicit action**:

```bash
# Preview: prints confirmation required and makes no deletion
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_history.py prune \
  --history-dir "$HOME/seo-private-history" --keep 26

# If reviewed and authorized, delete older SQLite snapshots
"$HOME/.agents/skills/seo/scripts/codex-seo" run seo_history.py prune \
  --history-dir "$HOME/seo-private-history" --keep 26 --confirm-prune
```

**Important:** Pruning the SQLite database does not automatically delete separately exported Markdown files or external backups. Review retention separately for these files. There is no silent auto-prune or scheduled data deletion.

## Validation

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests -p test_seo_history.py -v
python3 -m unittest discover -s tests -p test_seo_schedule_template.py -v
python3 scripts/generate_skill_map.py --check
python3 scripts/portability_check.py --strict
```

All tests use temporary local data, simulate concurrent history writes, validate no-clobber exports, reject symlink outputs, exercise retention gates and ensure schedule generation is **not installation**. Any sample numbers under `examples/synthetic/` are fabricated, not client results.
