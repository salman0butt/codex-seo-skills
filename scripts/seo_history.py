#!/usr/bin/env python3
"""Local-only, replay-safe SEO report history and evidence change tracking.

A scheduler can invoke `record` repeatedly with the *same saved JSON paths*.
Only new normalized evidence produces a new snapshot. No network, provider
calls, token reads, OAuth refresh, browser actions, or automatic schedules.

  codex-seo run seo_history.py record --history-dir ~/seo-private-history --gsc-current gsc.json
  codex-seo run seo_history.py list --history-dir ~/seo-private-history
  codex-seo run seo_history.py show --history-dir ~/seo-private-history --id 1
  codex-seo run seo_history.py prune --history-dir ~/seo-private-history --keep 26 --confirm-prune
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
import sqlite3
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from seo_report_builder import (
    ReportInputError, _comparison, _read_json, _markdown, compose,
)

MAX_LIST = 100
SCHEMA_VERSION = 1


def default_history_dir() -> Path:
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share') / 'codex-seo-history'


def _location(path: Path, *, create: bool) -> Path:
    # Reject symlink *endpoints* rather than following them. Other directories
    # are governed by their OS permissions; never print local paths on errors.
    path = path.expanduser()
    if path.is_symlink():
        raise ReportInputError('History symlink directory is not supported')
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir():
        raise ReportInputError('History directory is missing')
    mode = path.stat().st_mode
    if mode & 0o077:
        raise ReportInputError('History directory must have owner-only permissions (0700)')
    db = path / 'history.sqlite3'
    if db.is_symlink():
        raise ReportInputError('History database symlink is not allowed')
    if db.exists() and (not db.is_file() or db.stat().st_mode & 0o077):
        raise ReportInputError('History database must be an owner-only regular file (0600)')
    return db


def _connect(db: Path, *, readonly: bool = False):
    if readonly:
        # URI mode=ro ensures inspection never initializes a missing DB.
        return sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=8)
    # sqlite3.connect() would otherwise create a DB with mode 0644 before
    # chmod, racing a second cron invocation's permission check. Precreate
    # atomically and owner-only, without following a preexisting symlink.
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(db, flags, 0o600)
    except FileExistsError:
        descriptor = None
    if descriptor is not None:
        os.close(descriptor)
    connection = sqlite3.connect(db, timeout=8)
    try:
        if db.is_symlink() or not db.is_file() or db.stat().st_mode & 0o077:
            raise ReportInputError('History database must be an owner-only regular file (0600)')
        connection.execute('PRAGMA busy_timeout=8000')
        if connection.execute('PRAGMA user_version').fetchone()[0] not in (0, SCHEMA_VERSION):
            raise ReportInputError('Unsupported history schema version')
        connection.execute('''CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT NOT NULL,
            recorded_utc TEXT NOT NULL,
            report_json TEXT NOT NULL
        )''')
        connection.execute('PRAGMA user_version=1')
        connection.commit()
        return connection
    except BaseException:
        # A failed CREATE / corrupt DB must not leak a live SQLite connection.
        connection.close()
        raise


def _canonical_report(report: dict) -> str:
    # The builder adds generated_utc every invocation; exclude that transient
    # field so cron replays with unchanged source files do not create entries.
    content = {k:v for k,v in report.items() if k != 'generated_utc'}
    return json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _fingerprint(report: dict) -> str:
    return hashlib.sha256(_canonical_report(report).encode('utf-8')).hexdigest()


def _metadata(row) -> dict:
    id_, digest, recorded, payload = row
    report = json.loads(payload)
    return {'id':id_, 'recorded_utc':recorded, 'fingerprint':digest[:12],
            'providers': sorted(report.get('provider_reports',{})),
            'page_audit_count':len(report.get('page_audits',[])),
            'handoff_task_count':len(report.get('handoff_tasks',[]))}


def _changes(now: dict, before: dict | None, *, same_property: bool, same_page_set: bool) -> dict:
    if before is None:
        return {'status':'first_snapshot', 'providers':{},'page_findings':{'status':'no_previous_snapshot'},
                'note':'Only new evidence is saved; no historical claims can yet be made.'}
    old_providers=before.get('provider_reports',{})
    provider_changes={}
    for key in sorted(set(now['provider_reports'])|set(old_providers)):
        a=now['provider_reports'].get(key)
        b=old_providers.get(key)
        if a is None or b is None:
            provider_changes[key]={'status':'new_or_removed_provider','metric_changes':{}}
        else:
            comp = _comparison(a['current'],b['current'],same_property)
            provider_changes[key]={'status':comp['status'], 'metric_changes':comp['metrics']}
    page_comp={'status':'page_identity_not_attested'}
    old_pages=before.get('page_audits',[])
    new_pages=now.get('page_audits',[])
    # Because page paths are deliberately redacted, compare only if the
    # operator checked each ordered audit slot belongs to the same exact URL.
    if same_page_set:
        if (len(old_pages) != len(new_pages) or
                [x['page_origin'] for x in old_pages] != [x['page_origin'] for x in new_pages]):
            page_comp={'status':'different_audit_set','note':'Page-audit count/origin differs; cannot infer issues appeared or disappeared.'}
        else:
            appeared, absent = [], []
            for index,(a,b) in enumerate(zip(new_pages,old_pages),1):
                recent=set(a['finding_ids']); earlier=set(b['finding_ids'])
                appeared += [f'audit-{index}:{item}' for item in sorted(recent-earlier)]
                absent += [f'audit-{index}:{item}' for item in sorted(earlier-recent)]
            page_comp={'status':'compared_with_operator_page_attestation',
                       'now_present_only':appeared,'previously_present_only':absent,
                       'note':'A finding absent in the current audit is NOT proof the issue was fixed.'}
    return {'status':'new_evidence_snapshot','providers':provider_changes,'page_findings':page_comp,
            'note':'Changes use redacted supplied JSON; identity attestation is manual and no cause is inferred.'}


def _record(db: Path, report: dict, *, same_property: bool, same_page_set: bool) -> dict:
    stamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
    digest=_fingerprint(report)
    payload=json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))
    with closing(_connect(db)) as conn, conn:
        # SQLite write lock serializes concurrent cron/manual invocations.
        conn.execute('BEGIN IMMEDIATE')
        latest=conn.execute('SELECT id,fingerprint,recorded_utc,report_json FROM snapshots ORDER BY id DESC LIMIT 1').fetchone()
        if latest and latest[1]==digest:
            return {'status':'unchanged','snapshot':_metadata(latest),
                    'network_requests':0,'record_created':False,
                    'note':'Evidence matches latest snapshot. No duplicate written; source exports were not refreshed.'}
        old=json.loads(latest[3]) if latest else None
        changed=_changes(report,old,same_property=same_property,same_page_set=same_page_set)
        row=conn.execute('INSERT INTO snapshots(fingerprint,recorded_utc,report_json) VALUES (?,?,?)',
                         (digest,stamp,payload))
        return {'status':'created','snapshot':{'id':row.lastrowid,'recorded_utc':stamp,
                'fingerprint':digest[:12], 'providers':sorted(report['provider_reports']),
                'page_audit_count':len(report['page_audits']),
                'handoff_task_count':len(report['handoff_tasks'])},
                'previous_id':latest[0] if latest else None,
                'changes':changed, 'record_created':True,'network_requests':0}


def _export_markdown(directory: Path, record_id: int, report: dict) -> str:
    """Optionally write one 0600 Markdown report; never clobber prior evidence."""
    exports = directory / 'reports'
    if exports.is_symlink():
        raise ReportInputError('History report directory symlink is not allowed')
    exports.mkdir(mode=0o700, exist_ok=True)
    if exports.stat().st_mode & 0o077:
        raise ReportInputError('History report directory must be private (0700)')
    dest = exports / f'snapshot-{record_id:06d}.md'
    if dest.is_symlink():
        raise ReportInputError('History report output symlink is not allowed')
    if dest.exists():
        if not dest.is_file() or dest.stat().st_mode & 0o077:
            raise ReportInputError('History report must be owner-only (0600)')
        return 'already_exists'
    fd, temporary = tempfile.mkstemp(prefix='.seo-report-', dir=exports)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(_markdown(report))
        try:
            # Atomic and no-clobber; concurrent runs may race harmlessly.
            os.link(temporary, dest)
            return 'written'
        except FileExistsError:
            return 'already_exists'
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _open_existing(dirpath: Path):
    db=_location(dirpath,create=False)
    if not db.exists():
        raise ReportInputError('No history database in the selected directory')
    return _connect(db,readonly=True)


def run(argv: list[str] | None = None) -> dict:
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='action',required=True)
    for action in ('record','list','show','prune'):
        sp=subs.add_parser(action)
        sp.add_argument('--history-dir',type=Path,default=None,
                        help='Dedicated private directory; default ~/.local/share/codex-seo-history')
        if action=='record':
            for service in ('gsc','ga4'):
                for period in ('current','previous'):
                    sp.add_argument('--'+service+'-'+period,type=Path)
            sp.add_argument('--quick-audit',type=Path,action='append',default=[])
            sp.add_argument('--confirm-same-property',action='store_true',
                            help='Attest matching property for current/previous exports in this run')
            sp.add_argument('--confirm-history-same-property',action='store_true',
                            help='Attest latest stored exports and current exports belong to the same properties')
            sp.add_argument('--confirm-same-page-set',action='store_true',
                            help='Attest ordered audit slots contain the exact same page URLs in both snapshots')
            sp.add_argument('--export-markdown',action='store_true',
                            help='Save a private Markdown snapshot; disabled unless explicitly selected')
        if action=='list':
            sp.add_argument('--limit',type=int,default=20,help='1..100 latest snapshots')
        if action=='show':
            sp.add_argument('--id',type=int,required=True,help='Snapshot ID to display')
        if action=='prune':
            sp.add_argument('--keep',type=int,required=True,help='Number of newest snapshots to retain (1..10000)')
            sp.add_argument('--confirm-prune',action='store_true',help='Authorize permanent local history deletion')
    args=parser.parse_args(argv)
    basedir=args.history_dir if args.history_dir is not None else default_history_dir()
    if args.action=='record':
        paths={service+'_'+period:getattr(args,service+'_'+period) for service in ('gsc','ga4') for period in ('current','previous')}
        if not any(paths.values()) and not args.quick_audit:
            raise ReportInputError('Provide at least one previously saved report JSON')
        if len(args.quick_audit)>10:
            raise ReportInputError('At most ten public page audits allowed')
        obj={k:_read_json(p) if p else None for k,p in paths.items()}
        obj['quick_audits']=[_read_json(p) for p in args.quick_audit]
        report=compose(obj,confirm_same_property=args.confirm_same_property)
        db=_location(basedir,create=True)
        result = _record(db,report,same_property=args.confirm_history_same_property,
                         same_page_set=args.confirm_same_page_set)
        if args.export_markdown:
            # If this invocation is a replay, export the *stored* immutable
            # report instead of this run's differing generated_utc timestamp.
            with closing(_connect(db,readonly=True)) as conn:
                row=conn.execute('SELECT report_json FROM snapshots WHERE id=?',
                                 (result['snapshot']['id'],)).fetchone()
            if row is None:
                raise ReportInputError('History snapshot was not found for export')
            result['markdown_export']=_export_markdown(db.parent,result['snapshot']['id'],json.loads(row[0]))
            result['markdown_filename']=f"snapshot-{result['snapshot']['id']:06d}.md"
        return result
    if args.action=='prune':
        if not isinstance(args.keep,int) or not (1<=args.keep<=10000):
            raise ReportInputError('Retention must be between 1 and 10000 snapshots')
        if not args.confirm_prune:
            return {'status':'confirmation_required','network_requests':0,
                    'note':'Pruning is destructive. Pass --confirm-prune to delete older snapshots.'}
        db=_location(basedir,create=False)
        if not db.exists():
            raise ReportInputError('History database does not exist')
        with closing(_connect(db)) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            removed=conn.execute('''DELETE FROM snapshots WHERE id NOT IN (
                   SELECT id FROM snapshots ORDER BY id DESC LIMIT ?)''',(args.keep,)).rowcount
        return {'status':'pruned','removed_count':removed,'keep_latest':args.keep,'network_requests':0}
    with closing(_open_existing(basedir)) as conn:
        if args.action=='list':
            if not (1<=args.limit<=MAX_LIST):
                raise ReportInputError('List limit must be 1..100')
            rows=conn.execute('SELECT id,fingerprint,recorded_utc,report_json FROM snapshots ORDER BY id DESC LIMIT ?',
                              (args.limit,)).fetchall()
            return {'status':'ok','snapshots':[_metadata(row) for row in rows], 'network_requests':0}
        if args.id<1:
            raise ReportInputError('Snapshot ID must be positive')
        row=conn.execute('SELECT id,fingerprint,recorded_utc,report_json FROM snapshots WHERE id=?',(args.id,)).fetchone()
        if not row:
            raise ReportInputError('Snapshot ID does not exist')
        return {'status':'ok','snapshot':_metadata(row),'report':json.loads(row[3]),'network_requests':0}


def main(argv: list[str] | None=None) -> int:
    try:
        print(json.dumps(run(argv),indent=2,ensure_ascii=False))
        return 0
    except (ReportInputError, sqlite3.Error, OSError, ValueError) as exc:
        if isinstance(exc,ReportInputError):
            # Every ReportInputError above has a constant, non-sensitive message.
            message=str(exc)
        else:
            message='History file or database operation failed'
        print(json.dumps({'status':'error','reason':message,'network_requests':0}))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
