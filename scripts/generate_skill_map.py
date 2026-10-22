#!/usr/bin/env python3
"""Deterministic, source-derived Codex skill/agent/file traceability map.

Does not imply that Claude agent prompts, extensions, or optional scripts execute
without configured dependencies. Run `python3 scripts/generate_skill_map.py --check`
to verify the committed generated manifests have not drifted.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_GRAPH = 'docs/skill-agent-map.json'
OUT_TOPOLOGY = 'docs/SKILL_AGENT_MAP.md'
OUT_INVENTORY = 'docs/FILE_INVENTORY.md'
OUTPUTS = {OUT_GRAPH, OUT_TOPOLOGY, OUT_INVENTORY}


def repo_files() -> list[str]:
    output = subprocess.run(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        cwd=ROOT, check=True, capture_output=True,
    ).stdout
    paths = set(output.decode('utf-8').split('\0')) - {''}
    paths.update(OUTPUTS)
    return sorted(p for p in paths if p in OUTPUTS or (ROOT / p).is_file())


def classify(path: str) -> tuple[str, str]:
    parts = Path(path).parts
    if path in OUTPUTS:
        return 'generated-map', 'repository'
    if len(parts) >= 3 and parts[0] == 'skills':
        kind = ('skill-entrypoint' if parts[-1] == 'SKILL.md' else
                'codex-skill-metadata' if parts[-2:] == ('agents', 'openai.yaml') else
                'skill-support-file')
        return kind, parts[1]
    if parts[0] == 'agents':
        return 'specialist-agent-guide', Path(path).stem
    if parts[0] == 'scripts':
        return ('codex-installer-or-map-generator' if parts[1] in {'install_codex.py','generate_skill_map.py'}
                else 'execution-script-or-launcher'), 'runtime'
    if parts[0] == 'extensions':
        return ('extension-skill-entrypoint' if parts[-1] == 'SKILL.md' else
                'extension-support-or-setup'), 'extension:' + parts[1]
    if parts[0] == 'tests':
        return 'automated-test-or-fixture', 'testing'
    if parts[0] == 'docs':
        return 'documentation', 'documentation'
    if parts[0] == '.github':
        return 'ci-workflow', 'continuous-integration'
    if parts[0] == 'plugins':
        return 'upstream-claude-plugin-compatibility', 'legacy-plugin'
    if parts[0] == 'assets':
        return 'visual-asset', 'documentation'
    if parts[0] in {'schema','data'}:
        return 'shared-data-or-schema', 'runtime'
    return 'top-level-project-file', 'repository'


def known_words(source: str, names: set[str]) -> list[str]:
    # Match exact basenames only, not prefixes (seo != seo-geo).
    words = set(re.findall(r'(?<![a-zA-Z0-9_-])(?:[\w-]+\.py)(?![\w.-])', source))
    return sorted(words & names)


def related_tests(script_name: str, tests: list[str]) -> list[str]:
    stem = Path(script_name).stem
    relevant = []
    for path in tests:
        t = (ROOT / path).read_text(encoding='utf-8', errors='replace')
        if script_name in t or re.search(r'(?<!\w)' + re.escape(stem) + r'(?!\w)', t):
            relevant.append(path)
    return relevant


def build():
    paths = repo_files()
    if len(paths) != len(set(paths)):
        raise RuntimeError('duplicate paths in inventory')
    core = {Path(p).parts[1]: p for p in paths if p.startswith('skills/') and p.endswith('/SKILL.md')}
    agents = {Path(p).stem: p for p in paths if p.startswith('agents/') and p.endswith('.md')}
    scripts = {Path(p).name: p for p in paths if p.startswith('scripts/') and p.endswith('.py')}
    tests = [p for p in paths if p.startswith('tests/') and p.endswith('.py')]
    extensions = defaultdict(list)
    for p in paths:
        if p.startswith('extensions/'):
            extensions[Path(p).parts[1]].append(p)
    if len(core) != 30 or len(agents) != 19 or len(extensions) != 9:
        raise RuntimeError(f'unexpected source manifest counts: {len(core)} core, {len(agents)} agents, {len(extensions)} extension bundles')

    file_records = []
    for path in paths:
        kind, owner = classify(path)
        file_records.append({'path': path, 'kind': kind, 'owner': owner})
    edges = set()
    def edge(source: str, target: str, relation: str):
        if source not in paths or target not in paths:
            raise RuntimeError(f'dangling edge: {source} -> {target}')
        edges.add((source, target, relation))
    for path in paths:
        parts = Path(path).parts
        if len(parts) >= 3 and parts[0] == 'skills' and path != core.get(parts[1]):
            edge(core[parts[1]], path, 'owns-support-file')
    for name, path in agents.items():
        if name in core:
            edge(core[name], path, 'specialist-guide')
        mirror = f'skills/seo/references/agent-guides/{name}.md'
        if mirror in paths:
            edge(path, mirror, 'codex-readable-guide-mirror')
    # Every extension file belongs to its own bundle, including setup,
    # docs, scripts, agents, and skill resources (not only nested skill files).
    for bundle, bundle_paths in extensions.items():
        manifests = sorted(p for p in bundle_paths if p.endswith('/SKILL.md'))
        if manifests:
            manifest = manifests[0]
            for path in bundle_paths:
                if path != manifest:
                    edge(manifest, path, 'owns-extension-file')

    skill_details = []
    script_dependents = defaultdict(set)
    skill_names = set(core)
    for name, path in sorted(core.items()):
        text = (ROOT / path).read_text(encoding='utf-8')
        guide = agents.get(name)
        guide_text = (ROOT / guide).read_text(encoding='utf-8') if guide else ''
        scripts_used_in_skill = known_words(text, set(scripts))
        scripts_used_in_guide = known_words(guide_text, set(scripts))
        for item in scripts_used_in_skill:
            edge(path, scripts[item], 'mentions-script')
            script_dependents[item].add(path)
        if guide:
            for item in scripts_used_in_guide:
                edge(guide, scripts[item], 'mentions-script')
                script_dependents[item].add(guide)
        # Strong explicit cross-skill references only: $seo-<name> mentions
        # and exact `seo-<name>` tokens in orchestrator/audit documentation.
        invoked = sorted({x for x in re.findall(r'(?<![\w])\$(seo(?:-[a-z0-9-]+)?)(?![\w-])', text) if x in skill_names and x != name})
        for child in invoked:
            edge(path, core[child], 'references-codex-skill')
        owned = sorted(p for p in paths if p.startswith(f'skills/{name}/') and p != path)
        skill_details.append({
            'name': name, 'manifest': path, 'agent_guide': guide,
            'reference_guide_mirror': f'skills/seo/references/agent-guides/{name}.md' if guide else None,
            'mentioned_scripts_skill': scripts_used_in_skill,
            'mentioned_scripts_agent': scripts_used_in_guide,
            'related_skill_mentions': invoked,
            'owned_support_files': owned,
        })

    for name, path in agents.items():
        if name in core: continue
        text = (ROOT / path).read_text(encoding='utf-8')
        for item in known_words(text, set(scripts)):
            edge(path, scripts[item], 'mentions-script')
            script_dependents[item].add(path)

    # End-to-end dispatch chain. Links below are grounded in the actual
    # installer/launcher/runtime source, not inferred execution results.
    launcher_chain = [
        ('skills/seo/scripts/codex-seo', 'scripts/codex-seo'),
        ('scripts/codex-seo', 'scripts/claude-seo'),
        ('scripts/claude-seo', 'scripts/runtime.py'),
    ]
    for source, target in launcher_chain:
        edge(source, target, 'launcher-dispatches-to')
    runtime_source = (ROOT / 'scripts/runtime.py').read_text(encoding='utf-8')
    allowlist_match = re.search(r'ALLOWED_CORE_SCRIPTS\s*=\s*frozenset\(\s*\{(?P<values>.*?)\}\s*\)',runtime_source,re.S)
    if not allowlist_match:
        raise RuntimeError('Runtime script allowlist not found: inspect scripts/runtime.py')
    allowed = set(re.findall(r'"([A-Za-z_][A-Za-z0-9_-]*\.py)"', allowlist_match.group('values')))
    for name in sorted(allowed):
        if name not in scripts:
            raise RuntimeError(f'Allowed Python script missing: {name}')
        edge('scripts/runtime.py', scripts[name], 'runtime-allowlisted-script')
    for name, skill_path in sorted(core.items()):
        edge('scripts/install_codex.py', skill_path, 'installer-registers-core-skill')
    for source, item in sorted(((x['bundle'], x) for x in [
        {'bundle': ext, 'files': paths_for} for ext, paths_for in extensions.items()
    ])):
        manifest = next((p for p in item['files'] if p.endswith('/SKILL.md')), None)
        if manifest and Path(manifest).parent.name not in core:
            edge('scripts/install_codex.py', manifest, 'installer-registers-optional-extension')
    # Source text explicitly mentions specialist agent guide names; distinguish
    # that from native agent registration (which Codex does not provide here).
    for name, path in sorted(core.items()):
        text = (ROOT / path).read_text(encoding='utf-8')
        for guide_name, guide_path in sorted(agents.items()):
            if guide_name != name and re.search(r'(?<![\w-])' + re.escape(guide_name) + r'(?![\w-])', text):
                edge(path, guide_path, 'mentions-specialist-agent-guide')

    # Links between scripts and tests here mean the test source *mentions*
    # the script/import; they do not claim test-level runtime coverage.
    # Source imports are verified against *existing* Python module filenames.
    # This is static import inspection (not runtime call tracing).
    module_names = {Path(name).stem: path for name, path in scripts.items()}
    for script_name, script_path in sorted(scripts.items()):
        try:
            module = ast.parse((ROOT / script_path).read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(module):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split('.')[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = ([node.module.split('.')[0]] if node.module else []) + [alias.name for alias in node.names]
            for imported in names:
                if imported in module_names and module_names[imported] != script_path:
                    edge(script_path, module_names[imported], 'static-python-import')

    tests_for = {}
    for name, path in sorted(scripts.items()):
        matches = related_tests(name, tests)
        tests_for[name] = matches
        for test in matches:
            edge(test, path, 'test-source-mentions-script')

    script_details = [{
        'script': name, 'path': path,
        'mentioned_by': sorted(script_dependents[name]),
        'test_sources_mentioning': tests_for[name],
    } for name, path in sorted(scripts.items())]

    ext_details = []
    for ext, ext_paths in sorted(extensions.items()):
        manifests = sorted(p for p in ext_paths if p.endswith('/SKILL.md'))
        ext_name = Path(manifests[0]).parent.name if manifests else None
        ext_details.append({
            'bundle': ext, 'manifest': manifests[0] if manifests else None,
            'skill_name': ext_name,
            'core_name_collision': ext_name in core,
            'registered_with_with_extensions': bool(ext_name) and ext_name not in core,
            'files': sorted(ext_paths),
        })

    # Enrich every individual file record with its own incoming/outgoing links.
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for src, target, relation in sorted(edges):
        outgoing[src].append({'path': target, 'relation': relation})
        incoming[target].append({'path': src, 'relation': relation})
    for item in file_records:
        item['incoming'] = incoming[item['path']]
        item['outgoing'] = outgoing[item['path']]

    uncovered = [x for x in paths if x not in {f['path'] for f in file_records}]
    assert not uncovered
    graph = {
        'schema_version': 1,
        'generator': 'scripts/generate_skill_map.py',
        'scope': 'source-derived inventory, not proof of runtime execution',
        'counts': {
            'total_repo_files': len(paths), 'core_skills': len(core),
            'specialist_guides': len(agents),
            'agent_only_guides': len(set(agents) - set(core)),
            'extension_bundles': len(extensions),
            'unique_extension_skills': sum(x['registered_with_with_extensions'] for x in ext_details),
            'python_scripts': len(scripts),
            'test_python_files': len(tests), 'graph_edges': len(edges),
        },
        'agent_only': [{'name': n, 'path': agents[n], 'codex_skill': False} for n in sorted(set(agents)-set(core))],
        'skills': skill_details,
        'extensions': ext_details,
        'scripts': script_details,
        'files': file_records,
        'edges': [{'from': s, 'to': t, 'relation': r} for s,t,r in sorted(edges)],
    }
    return graph


def md_link(path: str, prefix: str = '../') -> str:
    # Relative links rather than GitHub URLs: work in forks and downloaded archives.
    return f'[`{path}`]({prefix}{path})'


def markdown(graph: dict) -> tuple[str, str]:
    counts = graph['counts']
    out = [
        '# End-to-end SEO skill and agent map', '',
        'Generated by `python3 scripts/generate_skill_map.py`. Source-derived references and exact paths; **a mentioned script is not proof that it executes successfully**. Optional API credentials, MCP integrations and Python/Chromium setup are separate.', '',
        '## System execution path', '',
        '```mermaid', 'flowchart TD',
        ' U[User SEO request] --> R[Codex skill discovery: AGENTS.md / SKILL.md]',
        ' R --> H[seo hub or matching leaf skill]',
        ' H --> D{Does a specialist guide exist?}',
        ' D -->|Yes| A[Agent guide checklist, inline or delegated if supported]',
        ' D -->|No| C[Execute skill instructions directly]',
        ' A --> C',
        ' C --> E{Bundled script required?}',
        ' E -->|Yes| L[codex-seo launcher]',
        ' L --> P[Managed Python runtime and scripts]',
        ' E -->|No| O[Read-only evidence gathering / content analysis]',
        ' P --> O',
        ' O --> V[Verified observations and limitations]',
        ' V --> X[Recommendations / evidence / optional report]',
        ' H --> Q[Optional extension skill]',
        ' Q --> K[External MCP service or API, if configured]',
        ' K --> V', '```', '',
        '## Coverage and meanings', '',
        f'- **{counts["total_repo_files"]}** repository files catalogued in {md_link(OUT_INVENTORY)} and machine-readable {md_link(OUT_GRAPH)}.',
        f'- **{counts["core_skills"]}** core skill manifests; **{counts["specialist_guides"]}** specialist agent guides; **{counts["agent_only_guides"]}** guide-only specialties.',
        f'- **{counts["extension_bundles"]}** optional extension bundles, **{counts["unique_extension_skills"]}** unique additional skill names that can be registered.',
        f'- **{counts["python_scripts"]}** Python scripts and **{counts["test_python_files"]}** Python test/fixture sources; **{counts["graph_edges"]}** explicit graph relationships.',
        '- **Launcher-dispatches-to** and **runtime-allowlisted-script** represent source-verified CLI plumbing; they do not assert dependencies are installed. **Static-python-import** means an actual import of a local Python module. **Owns-support-file** means packaged under that skill folder. **Mentions-script** means a literal script filename appears in instructions (not a verified invocation). **Test-source-mentions-script** does not establish test coverage.',
        '- Claude agent guides are reference checklists unless the running Codex harness supports delegation; agent-only guides do not represent installable skills.', '',
        '## Core skill → guide → script references → packaged resources', '',
        '| Codex skill | Agent guide | Script names mentioned in skill/guide | Support files |',
        '|---|---|---|---:|',
    ]
    for item in graph['skills']:
        agent = md_link(item['agent_guide']) if item['agent_guide'] else '— (skill-only)'
        names = sorted(set(item['mentioned_scripts_skill']) | set(item['mentioned_scripts_agent']))
        script_str = ', '.join(f'`{name}`' for name in names) if names else '— (content/API/tool-based)'
        out.append(f'| {md_link(item["manifest"])} | {agent} | {script_str} | {len(item["owned_support_files"])} |')
    out += ['', '## Agent-only guides (not separate `$...` skills)', '']
    for guide in graph['agent_only']:
        out.append(f'- **`{guide["name"]}`** — {md_link(guide["path"])}; usable as an orchestrator checklist (no native `skills/{guide["name"]}/SKILL.md`).')
    out += ['', '## Optional extensions', '', '| Bundle | Skill manifest | Registration | Packaged files |', '|---|---|---|---:|']
    for item in graph['extensions']:
        role='Duplicate of core skill; do not register twice' if item['core_name_collision'] else 'Opt-in via `--with-extensions`'
        out.append(f'| `{item["bundle"]}` | {md_link(item["manifest"])} | {role} | {len(item["files"])} |')
    out += ['', '## Script → referencing skills/guides → tests that mention it', '',
            'Each test association below is a textual match in test source, **not an assertion of full functional coverage**.', '',
            '| Runtime file | Referenced by | Tests containing filename/import reference |', '|---|---|---|']
    for item in graph['scripts']:
        referenced = ', '.join(f'`{Path(path).parent.name if path.startswith("skills/") else Path(path).stem}`' for path in item['mentioned_by']) or '— (utility/internal/unreferenced)'
        tests = ', '.join(f'`{Path(path).name}`' for path in item['test_sources_mentioning']) or '—'
        out.append(f'| {md_link(item["path"])} | {referenced} | {tests} |')
    out += ['', '## How to audit / update this map', '',
            '1. Run `python3 scripts/generate_skill_map.py` after adding, moving or removing repository files.',
            '2. Run `python3 scripts/generate_skill_map.py --check`, `python3 scripts/portability_check.py --strict` and `python3 -m unittest discover -s tests -p test_codex_installer.py`.',
            '3. Read `docs/FILE_INVENTORY.md` for **each file**, its kind and owning domain; read `docs/skill-agent-map.json` for directed relationships.',
            '4. Do not interpret a Markdown mention, extension catalog entry or agent checklist as runtime capability or verified live SEO data.', '']
    inventory = [
        '# Complete repository file inventory', '',
        'Generated by `python3 scripts/generate_skill_map.py`. Includes tracked and newly added source files and the three generated map files. Paths are repo-relative and clickable. `owner` is a classification, not an inferred runtime execution relationship.', '',
        f'**Files:** {counts["total_repo_files"]}. See {md_link(OUT_TOPOLOGY)} for process flow and {md_link(OUT_GRAPH)} for machine-readable edges.', '',
        '| File | Role | Owner | Relations (in / out) |', '|---|---|---|---|',
    ]
    for item in graph['files']:
        inventory.append(f'| {md_link(item["path"])} | `{item["kind"]}` | `{item["owner"]}` | {len(item["incoming"])} / {len(item["outgoing"])} |')
    inventory.append('')
    return '\n'.join(out), '\n'.join(inventory)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Report drift; do not change generated files')
    args = parser.parse_args()
    graph = build()
    topology, inventory = markdown(graph)
    results = {
        OUT_GRAPH: json.dumps(graph, indent=2, ensure_ascii=False) + '\n',
        OUT_TOPOLOGY: topology,
        OUT_INVENTORY: inventory,
    }
    drift = [path for path, content in results.items() if not (ROOT / path).exists() or (ROOT / path).read_text(encoding='utf-8') != content]
    if args.check:
        if drift:
            print('Skill map generation drift: ' + ', '.join(drift), file=sys.stderr)
            return 1
        print(f'Skill map current: {graph["counts"]["total_repo_files"]} files, {graph["counts"]["graph_edges"]} links')
        return 0
    for path, content in results.items():
        dest = ROOT / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding='utf-8')
    print(f'Generated skill map: {graph["counts"]["total_repo_files"]} files, {graph["counts"]["graph_edges"]} links; files: {", ".join(results)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
