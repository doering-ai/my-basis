############
### HEAD ###
############
### STANDARD
from __future__ import annotations
import ast
import keyword
import sys
import textwrap
import tomllib
import argparse as ap
from pathlib import Path
from typing import ClassVar, Self
import more_itertools as mi

### EXTERNAL
import regex as re
import pydantic as pyd

### INTERNAL
from my import ut, PATHS


############
### DATA ###
############
TOCTREE_STUB = """\
```{toctree}
---
maxdepth: 2
---
```
"""


############
### BODY ###
############
def _validate_package_name(package: str) -> str:
    """Require one Python import name rather than a filesystem path."""
    if package.isidentifier() and not keyword.iskeyword(package):
        return package
    raise ValueError(f'Package {package!r} must be a single Python import name, not a path.')


def _validate_package_source(root: Path, package: str) -> None:
    """Require every package initializer to resolve within the selected source tree."""
    project_root = root.resolve()
    package_root = root / package
    resolved_package_root = package_root.resolve()
    if not resolved_package_root.is_relative_to(project_root):
        raise ValueError(
            f'Package {package!r} resolves outside project root {project_root}: '
            f'{resolved_package_root}.'
        )

    for init_path in package_root.rglob('__init__.py'):
        resolved_init = init_path.resolve()
        if not resolved_init.is_relative_to(resolved_package_root):
            raise ValueError(
                f'Package source {init_path} resolves outside package root '
                f'{resolved_package_root}: {resolved_init}.'
            )


def _discover_package(root: Path) -> str:
    """Resolve the docs source package from pyproject.toml, or legacy `my`."""
    pyproject = root / 'pyproject.toml'
    if pyproject.exists():
        meta = tomllib.loads(pyproject.read_text())
        tool = meta.get('tool', dict())
        if not isinstance(tool, dict):
            raise ValueError('pyproject.toml `[tool]` must be a table.')
        uv = tool.get('uv', dict())
        if not isinstance(uv, dict):
            raise ValueError('pyproject.toml `[tool.uv]` must be a table.')
        build_backend = uv.get('build-backend', dict())
        if not isinstance(build_backend, dict):
            raise ValueError('pyproject.toml `[tool.uv.build-backend]` must be a table.')

        if 'module-name' in build_backend:
            name = build_backend['module-name']
            if isinstance(name, list):
                if len(name) > 1:
                    raise ValueError(
                        'pyproject.toml declares multiple packages in '
                        '`[tool.uv.build-backend].module-name`; pass `--package` explicitly.'
                    )
                name = next(iter(name), '')
            if not isinstance(name, str):
                raise ValueError(
                    'pyproject.toml `[tool.uv.build-backend].module-name` must be a string '
                    'or one-item list of strings.'
                )
            if name:
                return _validate_package_name(name)
    if (root / 'my' / '__init__.py').is_file():
        return 'my'
    raise ValueError(f'Could not discover a package under {root}; pass `--package` explicitly.')


def _resolve_package_name(root: Path, explicit_package: str | None) -> str:
    """Resolve and validate the package import name before constructing the worker."""
    package = (
        _discover_package(root)
        if explicit_package is None
        else _validate_package_name(explicit_package)
    )
    init_path = root / package / '__init__.py'
    if init_path.is_file():
        _validate_package_source(root, package)
        return package
    if explicit_package is not None:
        raise ValueError(f'`--package {package}` has no package `__init__.py` at {init_path}.')
    raise ValueError(
        f'pyproject.toml `module-name` package {package!r} has no `__init__.py` at '
        f'{init_path}; fix the setting or pass `--package` explicitly.'
    )


class Tool(pyd.BaseModel):
    """Update docs/X.md intro sections from <package>/X/__init__.py module docstrings.

    For each subpackage with a module docstring:
      - Rewrites the generated header (frontmatter, title, currentmodule, prose)
      - Preserves the existing {toctree} block and everything after it
      - If docs/X.md does not exist, creates it with an empty toctree template

    Examples:
        ```sh
        uv run sync-docs           # update all
        uv run sync-docs caches    # update one
        uv run sync-docs --check   # dry-run, print diff
        uv run sync-docs --package means   # override package discovery
        ```
    """

    #: Subpackages that are internal infrastructure or deprecated shims -- no public docs page.
    SKIP: ClassVar[frozenset[str]] = frozenset(
        {'_adoption', 'scripts', 'templates', 'infra', 'text', 'type'}
    )

    #: The directory containing a local python project.
    root: pyd.DirectoryPath
    dry: bool = False
    #: The import name of the package whose subpackages feed the docs pages.
    #: Empty means: discover from the project's pyproject.toml (see `_resolve_package`).
    package: str = ''

    @pyd.model_validator(mode='before')
    @classmethod
    def _build_tool(cls, data: dict) -> dict:
        data['root'] = ut.path(data['root'])
        return data

    @pyd.model_validator(mode='after')
    def _resolve_package(self) -> Self:
        """Fill `package` from the project's pyproject.toml when not given explicitly.

        Discovery reads `[tool.uv.build-backend] module-name` (the fleet-standard uv build
        config), falling back to the legacy `my` package when `<root>/my/__init__.py` exists.
        """
        self.package = _resolve_package_name(self.root, self.package or None)
        return self

    def discover_package(self) -> str:
        """Resolve the docs source package from pyproject.toml, or legacy `my`."""
        return _discover_package(self.root)

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
        """Assemble the full docs/X.md content.

        The tagline's trailing period is dropped: docstring first lines end with one, but the
        page H1s (`` # `my.utils`: Pure, Typed Functional Utilities ``) do not.
        """
        tagline = tagline.strip().removesuffix('.')
        body_section = f'\n\n{body}' if body else ''
        return (
            f'---\nnumbering:\n  title: true\n---\n\n'
            f'# `{self.package}.{pkg}`: {tagline}\n\n'
            f'```{{py:currentmodule}} {self.package}.{pkg}\n```'
            f'{body_section}\n\n'
            f'{preserved}'
        )

    def pkg_name(self, init_path: Path) -> str:
        """Dotted subpackage name relative to `package` (e.g. `regex.meta`), keyed to docs/X.md."""
        return '.'.join(init_path.parent.relative_to(self.root / self.package).parts)

    def sync_readme(self, file: Path) -> bool:
        """Sync one (sub)package module with its README.md."""
        pkg = self.pkg_name(file)
        if not (docstring := self.get_docstring(file)):
            return False
        elif match := re.match(r'^([^\s\n\#].*)\n+', docstring):
            head = match[1]
            body = docstring[match.end() :]
        else:
            head = ''
            body = docstring
        body = textwrap.dedent(body.strip('\n'))

        doc_path = self.root / 'docs' / f'{pkg}.md'
        if doc_path.exists() and '```{toctree}' not in doc_path.read_text():
            # A page with no {toctree} block is hand-written (e.g. a command guide), not a
            # generated subpackage page -- rewriting it would destroy its content.
            print(f'\tSKIP {pkg}: docs/{pkg}.md is hand-written (no toctree)')
            return False
        preserved = self.get_preserved_section(doc_path)
        new_content = self.render_page(pkg, head, body, preserved)

        if doc_path.exists() and doc_path.read_text() == new_content:
            print(f'\tOK   {pkg}: up to date')
            return False

        if self.dry:
            print(f'\tDIFF {pkg}: would update docs/{pkg}.md')
            # Print a simple before/after summary
            z0 = doc_path.read_text().count('\n') if doc_path.exists() else 0
            z1 = new_content.count('\n')
            print(f'\t\t{z0} → {z1} lines')
            return True

        status = 'UPDATE' if doc_path.exists() else 'CREATE'
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(
            new_content,
        )
        print(f'\t{status} {pkg}: docs/{pkg}.md')
        return True

    def find_source_files(self) -> list[Path]:
        """Find all subpackage `__init__.py` files under `package`, excluding SKIP subtrees.

        Only the package source tree is crawled -- never the repo root, which would sweep up
        `.venv/` site-packages. The top-level `__init__.py` is excluded too (`docs/index.md` is
        hand-written, not generated).
        """
        pkg_dir = self.root / self.package
        return sorted(
            file
            for file in pkg_dir.rglob('__init__.py')
            if file.parent != pkg_dir
            and not any(part in self.SKIP for part in file.parent.relative_to(pkg_dir).parts)
        )


############
### MAIN ###
############
def _parse_args(*vargs: str) -> ap.Namespace:
    parser = ap.ArgumentParser(description='Sync module docstrings from subpackages to READMEs.')

    parser.add_argument(
        'root',
        type=Path,
        nargs='?',
        default=None,
        help='The directory containing a local python project.',
    )
    parser.add_argument(
        '-n',
        '--dry',
        '--dry-run',
        action='store_true',
        help="Don't actually change files, just print.",
    )
    parser.add_argument(
        '-p',
        '--package',
        default=None,
        help='The import package to document (default: discover from pyproject.toml).',
    )

    return parser.parse_args(vargs or None)


def main(*vargs: str) -> None:
    """Sync docs/X.md intro sections from <package>/X/__init__.py module docstrings."""
    args = _parse_args(*vargs)

    try:
        root = args.root if args.root is not None else PATHS.seek_project()
        if root is None:
            raise ValueError('Could not discover a project root; pass ROOT explicitly.')
        package = _resolve_package_name(root, args.package)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
        print(f'sync-docs: error: {error}', file=sys.stderr)
        raise SystemExit(2) from None

    tool = Tool(root=root, dry=args.dry, package=package)

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
