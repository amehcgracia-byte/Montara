"""Rebuild the source index behind the parity audit; presence is not verification."""
import ast
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def inventory(folder, ref):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(folder), *args], text=True)
    commit = git('rev-parse', ref).strip()
    result = {'commit': commit, 'routes': [], 'modules': [], 'interface': []}
    for name in git('ls-tree', '-r', '--name-only', commit).splitlines():
        if name.startswith(('tests/', 'vendor/')) or (name.startswith('tools/') and not name.startswith('tools/qa/')):
            continue
        python = name.endswith('.py') and (name.startswith(('core/', 'server/')) or '/' not in name)
        interface = name.endswith(('.html', '.js')) and name.startswith(('web/', 'static/', 'templates/', 'tools/qa/')) and '/vendor/' not in name
        if not python and not interface:
            continue
        source = git('show', f'{commit}:{name}')
        if interface:
            controls = sorted(set(re.findall(r'\bid=["\x27]([^"\x27]+)', source)))
            result['interface'].append({'file': name, 'ids': controls,
                'functions': sorted(set(re.findall(r'\bfunction\s+([\w$]+)\s*\(', source)))})
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        result['modules'].append({'file': name, 'description': (ast.get_docstring(tree) or '').split('\n')[0],
            'functions': [{'name': n.name, 'line': n.lineno} for n in tree.body
                          if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith('_')]})
        for n in ast.walk(tree):
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for d in n.decorator_list:
                if not isinstance(d, ast.Call) or not isinstance(d.func, ast.Attribute) or d.func.attr not in ('route','get','post','put','patch','delete') or not d.args:
                    continue
                try:
                    route = ast.literal_eval(d.args[0])
                    methods = next((ast.literal_eval(k.value) for k in d.keywords if k.arg == 'methods'),
                                   ['GET'] if d.func.attr == 'route' else [d.func.attr.upper()])
                except (ValueError, TypeError):
                    continue
                result['routes'].append({'path': route, 'methods': methods, 'handler': n.name,
                                         'file': name, 'line': n.lineno})
    return result


if __name__ == '__main__':
    result = {
        'scope': 'Static source inventory, not an end-to-end verification or a count of product features.',
        'editor_installed_2_6_20': inventory(ROOT / 'engine', 'c30a1d407e63be9b647726562a1b96fdd4cd8c77'),
        'editor_montara': inventory(ROOT / 'engine', 'HEAD'),
        'mixer_montara': inventory(ROOT / 'mixer', 'HEAD'),
        'mixer_public_master': inventory(ROOT / 'mixer', 'origin/master'),
        'montara': inventory(ROOT, 'HEAD'),
    }
    target = ROOT / 'docs/audit/capabilities.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    for name, item in result.items():
        if isinstance(item, dict):
            print(name, item['commit'][:12], len(item['routes']), 'routes,', len(item['interface']), 'interface files')
