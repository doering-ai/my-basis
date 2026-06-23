"""Update `docs/X.md` intro sections from `my/X/__init__.py` module docstrings.

For each subpackage with a module docstring:
  - Rewrites the generated header (frontmatter, title, currentmodule, prose)
  - Preserves the existing {toctree} block and everything after it
  - If docs/X.md does not exist, creates it with an empty toctree template

Usage:
    ```zsh
    uv run python gen_module_docs.py           # update all
    uv run python gen_module_docs.py caches    # update one
    uv run python gen_module_docs.py --check   # dry-run, print diff
    ```
"""

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
import ast
import sys
import textwrap
from pathlib import Path

############
### DATA ###
############
ROOT = Path(__file__).parent.parent  # docs/ → basis/
MY_DIR = ROOT / 'my'
DOCS_DIR = ROOT / 'docs'

# Subpackages that are internal infrastructure — no public docs page.
SKIP = frozenset({'scripts', 'templates', 'infra'})

TOCTREE_STUB = """\
```{{toctree}}
---
maxdepth: 2
---
```
"""

############
### BODY ###
############


def get_docstring(init_path: Path) -> str | None:
    """Extract the module docstring from an __init__.py without importing it."""
    source = init_path.read_text(encoding='utf-8')
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    return ast.get_docstring(tree)


def split_docstring(docstring: str) -> tuple[str, str]:
    """Return (tagline, body) — tagline is the first non-empty line, body is the rest."""
    lines = docstring.strip().splitlines()
    tagline = lines[0].strip()
    body_lines = lines[1:]
    # Strip leading blank lines from body
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    body = textwrap.dedent('\n'.join(body_lines)).strip()
    return tagline, body


def get_preserved_section(doc_path: Path) -> str:
    """Return everything from the first {toctree} to EOF, or the stub if absent."""
    if not doc_path.exists():
        return TOCTREE_STUB
    content = doc_path.read_text(encoding='utf-8')
    idx = content.find('```{toctree}')
    if idx == -1:
        return TOCTREE_STUB
    # Preserve with a preceding blank line
    return content[idx:]


def render_page(pkg: str, tagline: str, body: str, preserved: str) -> str:
    """Assemble the full docs/X.md content."""
    body_section = f'\n\n{body}' if body else ''
    return (
        f'---\nnumbering:\n  title: true\n---\n\n'
        f'# `my.{pkg}`: {tagline}\n\n'
        f'```{{py:currentmodule}} my.{pkg}\n```'
        f'{body_section}\n\n'
        f'{preserved}'
    )


def sync_package(pkg: str, *, dry_run: bool = False) -> bool:
    """Sync one package. Returns True if a change was written (or would be)."""
    init = MY_DIR / pkg / '__init__.py'
    if not init.exists():
        print(f'  MISS  {pkg}: no __init__.py')
        return False

    docstring = get_docstring(init)
    if not docstring:
        print(f'  SKIP  {pkg}: no module docstring')
        return False

    tagline, body = split_docstring(docstring)
    doc_path = DOCS_DIR / f'{pkg}.md'
    preserved = get_preserved_section(doc_path)
    new_content = render_page(pkg, tagline, body, preserved)

    if doc_path.exists() and doc_path.read_text(encoding='utf-8') == new_content:
        print(f'  OK    {pkg}: up to date')
        return False

    if dry_run:
        print(f'  DIFF  {pkg}: would update docs/{pkg}.md')
        # Print a simple before/after summary
        if doc_path.exists():
            old_lines = doc_path.read_text().splitlines()
            new_lines = new_content.splitlines()
            print(f'        {len(old_lines)} → {len(new_lines)} lines')
        else:
            print('        (new file)')
        return True

    doc_path.write_text(new_content, encoding='utf-8')
    status = 'CREATE' if not doc_path.exists() else 'UPDATE'
    print(f'  {status} {pkg}: docs/{pkg}.md')
    return True


############
### MAIN ###
############
if __name__ == '__main__':
    args = sys.argv[1:]
    dry_run = '--check' in args
    targets = [a for a in args if not a.startswith('--')]

    if not targets:
        targets = sorted(
            p.name
            for p in MY_DIR.iterdir()
            if p.is_dir() and not p.name.startswith('_') and p.name not in SKIP
        )

    changed = 0
    for pkg in targets:
        if sync_package(pkg, dry_run=dry_run):
            changed += 1

    if dry_run:
        print(f'\n{changed} package(s) would be updated.')
    else:
        print(f'\n{changed} package(s) updated.')
