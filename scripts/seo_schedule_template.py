#!/usr/bin/env python3
"""Print (never install) a private weekly cron or macOS launchd template.

Only replays SAVED local JSON files. It cannot refresh Google API data, access
OAuth, call a network provider, modify a website, or schedule itself.
"""
from __future__ import annotations

import argparse
import plistlib
import shlex
import sys
from pathlib import Path


def build(platform: str, *, launcher: Path, history_dir: Path, sources: dict[str, Path]) -> str:
    if not sources:
        raise ValueError('Provide one or more saved JSON export paths')
    args = [str(launcher.expanduser().absolute()), 'run', 'seo_history.py', 'record',
            '--history-dir', str(history_dir.expanduser().absolute()), '--export-markdown']
    for name in ('gsc-current','gsc-previous','ga4-current','ga4-previous'):
        if name in sources:
            args.extend(['--'+name, str(sources[name].expanduser().absolute())])
    for path in sources.get('quick-audit', []):
        args.extend(['--quick-audit', str(path.expanduser().absolute())])
    if platform == 'cron':
        # local-time Monday 09:00; shell quoting prevents injection in paths.
        return '0 9 * * 1 umask 077; ' + ' '.join(shlex.quote(arg) for arg in args) + '\n'
    if platform == 'launchd':
        path = str(history_dir.expanduser().absolute())
        spec = {
            'Label':'com.codexseo.offline-history-weekly',
            'ProgramArguments':args,
            'StartCalendarInterval':{'Weekday':1,'Hour':9,'Minute':0},
            'RunAtLoad':False,
            'Umask':0o077,
            'StandardOutPath':path+'/scheduled-stdout.log',
            'StandardErrorPath':path+'/scheduled-stderr.log',
        }
        return plistlib.dumps(spec,fmt=plistlib.FMT_XML,sort_keys=True).decode('utf-8')
    raise ValueError('Only cron and launchd templates are supported')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=('cron','launchd'), required=True)
    parser.add_argument('--history-dir', type=Path, required=True,
                        help='Private 0700 history directory, previously created by a manual record run')
    parser.add_argument('--launcher', type=Path,
                        default=Path.home()/'.agents/skills/seo/scripts/codex-seo')
    for service in ('gsc','ga4'):
        for period in ('current','previous'):
            parser.add_argument('--'+service+'-'+period,type=Path)
    parser.add_argument('--quick-audit',type=Path,action='append',default=[])
    args=parser.parse_args(argv)
    sources={service+'-'+period:getattr(args,service+'_'+period)
             for service in ('gsc','ga4') for period in ('current','previous')
             if getattr(args,service+'_'+period)}
    if args.quick_audit:
        sources['quick-audit']=args.quick_audit
    if len(args.quick_audit)>10:
        parser.error('Maximum ten saved page audits')
    if not sources:
        parser.error('Provide at least one previously saved JSON export')
    print(build(args.platform,launcher=args.launcher,history_dir=args.history_dir,sources=sources),end='')
    return 0


if __name__=='__main__':
    sys.exit(main())
