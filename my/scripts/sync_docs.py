############
### HEAD ###
############
### STANDARD
from __future__ import annotations
import ast
import textwrap
import argparse as ap
from pathlib import Path
import more_itertools as mi

### EXTERNAL
import regex as re
import pydantic as pyd

### INTERNAL
from my import ut, PATHS


############
### BODY ###
############
class Tool(pyd.BaseModel):
    """Update docs/X.md intro sections from my/X/__init__.py module docstrings.

    For each subpackage with a module docstring:
      - Rewrites the generated header (frontmatter, title, currentmodule, prose)
      - Preserves the existing {toctree} block and everything after it
      - If docs/X.md does not exist, creates it with an empty toctree template

    Examples:
        ```sh
        uv run sync-docs           # update all
        uv run sync-docs caches    # update one
        uv run sync-docs --check   # dry-run, print diff
        ```
    """

    #: The directory containing a local python project.
    root: pyd.DirectoryPath
    dry: bool = False

    @pyd.model_validator(mode='before')
    @classmethod
    def _build_tool(cls, data: dict) -> dict:
        data['root'] = ut.path(data['root'])
        return data

    def get_docstring(self, init_path: Path) -> str | None:
        """Extract the module docstring from an __init__.py without importing it."""
        source = init_path.read_text()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        return ast.get_docstring(tree)

    def split_docstring(self, docstring: str) -> tuple[str, str]:
        """Return (tagline, body) — tagline is the first non-empty line, body is the rest."""
        head, *body = re.split(r'(?:\s*\n)+', docstring.strip('\n'))
        body = list(mi.strip(body, lambda s: not s))

        # Strip leading blank lines from body
        while body and not body[0].strip():
            body.pop(0)
        body = textwrap.dedent('\n'.join(body)).strip()
        return head, body

    def get_preserved_section(self, doc_path: Path) -> str:
        """Return everything from the first {toctree} to EOF, or the stub if absent."""
        if not doc_path.exists():
            return TOCTREE_STUB
        content = doc_path.read_text()
        idx = content.find('```{toctree}')
        if idx == -1:
            return TOCTREE_STUB
        # Preserve with a preceding blank line
        return content[idx:]

    def render_page(self, pkg: str, tagline: str, body: str, preserved: str) -> str:
        """Assemble the full docs/X.md content."""
        body_section = f'\n\n{body}' if body else ''
        return (
            f'---\nnumbering:\n  title: true\n---\n\n'
            f'# `my.{pkg}`: {tagline}\n\n'
            f'```{{py:currentmodule}} my.{pkg}\n```'
            f'{body_section}\n\n'
            f'{preserved}'
        )

    def sync_readme(self, file: Path) -> bool:
        """Sync one (sub)package module with its README.md."""
        if not (docstring := self.get_docstring(file)):
            return False
        elif match := re.match(r'^([^\s\n\#].*)\n+', docstring):
            head = match[1]
            body = docstring[match.end() :]
        else:
            head = ''
            body = docstring
        body = textwrap.dedent(body.strip('\n'))

        doc_path = Path()
        preserved = self.get_preserved_section(doc_path)
        new_content = self.render_page(pkg, head, body, preserved)

        if doc_path.exists() and doc_path.read_text() == new_content:
            print(f'\tOK   {pkg}: up to date')
            return False

        if dry_run:
            print(f'\tDIFF {pkg}: would update docs/{pkg}.md')
            # Print a simple before/after summary
            z0 = doc_path.read_text().count('\n') if doc_path.exists() else 0
            z1 = new_content.count('\n')
            print(f'\t\t{z0} → {z1} lines')
            return True

        doc_path.write_text(
            new_content,
        )
        status = 'CREATE' if not doc_path.exists() else 'UPDATE'
        print(f'\t{status} {pkg}: docs/{pkg}.md')
        return True

    def find_source_files(self) -> list[Path]:
        """Find all `__init__.py` files in subpackages, excluding SKIP."""
        return sorted(
            file for file in self.root.rglob('__init__.py') if file.parent.name not in self.SKIP
        )


############
### MAIN ###
############
def _parse_args(*vargs: str) -> ap.Namespace:
    parser = ap.ArgumentParser(description='Sync module docstrings from subpackages to READMEs.')

    parser.add_argument(
        'root',
        type=Path,
        default=PATHS.seek_project(),
        help='The directory containing a local python project.',
    )
    parser.add_argument(
        '-n',
        '--dry',
        '--dry-run',
        help="Don't actually change files, just print.",
    )

    return parser.parse_args(vargs or None)


def main(*vargs: str) -> None:
    args = _parse_args(*vargs)

    tool = Tool(**vars(args))

    changed = 0
    for file in tool.find_source_files():
        if tool.sync_readme(file):
            changed += 1

    if tool.dry:
        print(f'\n{changed} package(s) would be updated.')
    else:
        print(f'\n{changed} package(s) updated.')


if __name__ == '__main__':
    main()
