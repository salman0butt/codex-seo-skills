#!/usr/bin/env python3
"""Install Claude SEO's Codex-compatible skills without installing runtime dependencies."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGE_MARKER = '.codex-seo-package.json'
COMPONENT_DIRS = ('skills', 'agents', 'scripts', 'extensions', 'data', 'docs', 'schema', 'plugins', 'assets')


def skill_sources(with_extensions: bool) -> tuple[list[tuple[str, Path]], list[str]]:
    core = sorted((p.parent.name, p.parent) for p in (REPO / 'skills').glob('*/SKILL.md'))
    if len(core) != 30:
        raise RuntimeError(f'Expected 30 bundled core SEO skills; found {len(core)}')
    result = list(core)
    skipped: list[str] = []
    if with_extensions:
        seen = {name for name, _ in result}
        for path in sorted((REPO / 'extensions').rglob('SKILL.md')):
            name = path.parent.name
            if name in seen:
                skipped.append(name)
                continue
            result.append((name, path.parent))
            seen.add(name)
    return result, skipped


def package_root() -> Path:
    # XDG_DATA_HOME is honored by the installer and the runtime launcher.
    xdg = os.environ.get('XDG_DATA_HOME')
    return (Path(xdg).expanduser() if xdg else Path.home() / '.local' / 'share') / 'codex-seo'


def conflict_check(root: Path, skills_dir: Path, requested: list[tuple[str, Path]]) -> None:
    if root.is_symlink() or (root.exists() and not (root / PACKAGE_MARKER).is_file()):
        raise RuntimeError(f'Refusing to overwrite an unrelated or unmanaged package directory: {root}')
    for name, _ in requested:
        dest = skills_dir / name
        if dest.is_symlink():
            resolved = dest.resolve(strict=False)
            if not resolved.is_relative_to(root.resolve(strict=False)):
                raise RuntimeError(f'Refusing to overwrite non-Codex-SEO symlink: {dest}')
        elif dest.exists():
            # A fallback copy from a prior installation is marked by this file.
            if not (dest / PACKAGE_MARKER).is_file():
                raise RuntimeError(f'Refusing to overwrite existing unrelated skill: {dest}')


def install(with_extensions: bool, dry_run: bool) -> int:
    root = package_root()
    target_skills = Path.home() / '.agents' / 'skills'
    requested, skipped = skill_sources(with_extensions)
    conflict_check(root, target_skills, requested)
    if dry_run:
        print(json.dumps({
            'dry_run': True,
            'package_root': str(root),
            'codex_skills_directory': str(target_skills),
            'skills_to_register': len(requested),
            'duplicate_extension_skipped': skipped,
            'dependencies_installed': False,
        }, indent=2))
        return 0

    root.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix='.codex-seo-install-', dir=root.parent))
    backup: Path | None = None
    link_backups: Path | None = None
    touched: list[Path] = []
    installed_root = False
    committed = False
    try:
        # Stage and validate the complete new package before moving any
        # existing installation or registered skill into a new location.
        for dirname in COMPONENT_DIRS:
            source = REPO / dirname
            if source.exists():
                shutil.copytree(source, tmp / dirname, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.pytest_cache', '.venv'))
        for file in ('LICENSE', 'requirements.txt', 'pyproject.toml', 'PRIVACY.md', 'README.md', 'plugin.json'):
            source = REPO / file
            if source.is_file():
                shutil.copy2(source, tmp / file)
        (tmp / PACKAGE_MARKER).write_text(json.dumps({
            'package': 'codex-seo-skills', 'source': 'https://github.com/AgriciDaniel/claude-seo'
        }) + '\n', encoding='utf-8')
        target_skills.mkdir(parents=True, exist_ok=True)
        link_backups = Path(tempfile.mkdtemp(prefix='.codex-seo-links-backup-', dir=target_skills))
        if root.exists():
            backup = Path(tempfile.mkdtemp(prefix='.codex-seo-backup-', dir=root.parent))
            backup.rmdir()
            root.rename(backup)
        tmp.rename(root)
        installed_root = True
        copied: list[str] = []
        for name, original in requested:
            relative = original.relative_to(REPO)
            source = root / relative
            dest = target_skills / name
            # Preserve previous registered entries (including fallback copies)
            # so failure to create even one new skill can restore them all.
            if dest.is_symlink() or dest.exists():
                dest.rename(link_backups / name)
            touched.append(dest)
            try:
                dest.symlink_to(source, target_is_directory=True)
            except (NotImplementedError, OSError):
                shutil.copytree(source, dest)
                (dest / PACKAGE_MARKER).write_text('codex-seo-skills fallback copy\n')
                copied.append(name)
        committed = True
        print(json.dumps({
            'installed': True,
            'package_root': str(root),
            'codex_skills_directory': str(target_skills),
            'skills_registered': len(requested),
            'fallback_copies': copied,
            'duplicate_extension_skipped': skipped,
            'dependencies_installed': False,
            'hint': 'Restart Codex if new skills are not detected. Run ~/.agents/skills/seo/scripts/codex-seo doctor --json before using Python scripts.',
        }, indent=2))
        return 0
    finally:
        if not committed:
            # Recovery must run before removing either backup. In the event
            # that recovery itself fails, preserve both backup directories
            # rather than silently destroying the previous working install.
            try:
                for dest in reversed(touched):
                    if dest.is_symlink() or dest.is_file():
                        dest.unlink()
                    elif dest.exists():
                        shutil.rmtree(dest)
                    previous = link_backups / dest.name if link_backups else None
                    if previous is not None and (previous.is_symlink() or previous.exists()):
                        previous.rename(dest)
                if installed_root and root.exists():
                    shutil.rmtree(root)
                if backup is not None and backup.exists():
                    backup.rename(root)
                    backup = None
            except BaseException:
                # Leave recoverable backup directories in place.
                raise
        if tmp != root and tmp.exists():
            shutil.rmtree(tmp)
        if committed:
            if backup is not None and backup.exists():
                shutil.rmtree(backup)
        if link_backups is not None and link_backups.exists():
            shutil.rmtree(link_backups)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Show destination and conflicts without writing files')
    parser.add_argument('--with-extensions', action='store_true', help='Register all unique optional extension skills')
    args = parser.parse_args()
    try:
        return install(args.with_extensions, args.dry_run)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f'codex-seo installer: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
