"""Inspect a Python repository without importing or modifying its source.

Deliberately depends only on ``pydantic`` and the standard library so the adoption
workflow remains usable while my-basis itself is being introduced or refactored.
"""

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from collections import Counter, defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal
import ast
import hashlib
import json
import os
import re
import tomllib

### INTERNAL
from .models import FileEvidence, ImportFact, Intake, RegexPatternFact, Signal


############
### DATA ###
############
#: Directories whose contents are generated, vendored, cached, or owned by this workflow.
EXCLUDED_DIRS = frozenset(
    {
        '.basis-adoption',
        '.git',
        '.hg',
        '.mypy_cache',
        '.nox',
        '.pytest_cache',
        '.ruff_cache',
        '.svn',
        '.tox',
        '.venv',
        '__pycache__',
        'build',
        'dist',
        'htmlcov',
        'node_modules',
        'site-packages',
        'vendor',
        'vendors',
        'vendored',
        'venv',
        'third_party',
    }
)

#: File-name fragments that are too likely to contain credentials to inspect or hash.
SECRET_NAME_RGX = re.compile(
    r'(^\.env(?:\.|$)|(?:^|[-_.])(?:credentials?|secrets?|tokens?|passwords?|'
    r'private[-_.]?key)(?:[-_.]|$)|\.(?:key|pem|p12|pfx|jks|kdbx|age)$)',
    re.IGNORECASE,
)

#: Generated Python files whose patterns and imports do not represent authored architecture.
GENERATED_FILE_RGX = re.compile(
    r'(^|/)(?:.*(?:_pb2|_generated|\.min)\.py|generated(?:/|$))',
    re.IGNORECASE,
)

#: Regular-expression operations worth inventorying.
REGEX_OPERATIONS = frozenset(
    {'compile', 'findall', 'finditer', 'fullmatch', 'match', 'search', 'split', 'sub', 'subn'}
)

#: Syntax that merits inspection before any example-backed RegexStore proposal.
COMPLEX_REGEX_MARKERS = (
    '(?P<',
    '(?P>',
    '(?=',
    '(?!',
    '(?<=',
    '(?<!',
    '(?(',
    '(?(DEFINE)',
    r'\p{',
    r'\P{',
    '(*',
)

#: Maximum bytes read from one source or metadata file.
MAX_SCAN_BYTES = 2_000_000

#: The Python floor required by my-basis 1.0.
MY_BASIS_PYTHON_FLOOR = (3, 12)

type FileKind = Literal['config', 'python', 'workflow']
type ScannedFile = tuple[Path, FileKind, bytes]


############
### BODY ###
############
def _is_within(path: Path, root: Path) -> bool:
    """Return whether a resolved path remains within the repository root."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _file_kind(
    path: Path,
    root: Path,
) -> FileKind | None:
    """Return the evidence kind for a file the scanner is allowed to read."""
    relative = path.relative_to(root)
    posix = relative.as_posix()
    if GENERATED_FILE_RGX.search(posix):
        return None
    if path.suffix == '.py':
        return 'python'
    if path.name in {
        '.python-version',
        'Makefile',
        'Pipfile',
        'Pipfile.lock',
        'pdm.lock',
        'poetry.lock',
        'pylock.toml',
        'pyproject.toml',
        'setup.cfg',
        'setup.py',
        'sublime-package.json',
        'uv.lock',
    }:
        return 'config'
    if path.name.startswith('requirements') and path.suffix in {'.in', '.txt'}:
        return 'config'
    if path.name.startswith('Taskfile') and path.suffix in {'.yaml', '.yml'}:
        return 'workflow'
    if posix == '.gitlab-ci.yml' or (
        len(relative.parts) >= 3
        and relative.parts[:2] == ('.github', 'workflows')
        and path.suffix in {'.yaml', '.yml'}
    ):
        return 'workflow'
    return None


def _iter_files(root: Path, exclusions: Counter[str]) -> Iterator[tuple[Path, FileKind]]:
    """Yield sorted, allowed repository files without following directory links."""
    candidates: list[tuple[Path, FileKind]] = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for dirname in sorted(dirnames):
            directory = current_path / dirname
            if dirname in EXCLUDED_DIRS:
                if dirname != '.basis-adoption':
                    exclusions['directories'] += 1
            elif directory.is_symlink():
                exclusions['symlinks'] += 1
            else:
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            path = current_path / filename
            if path.is_symlink():
                category = 'symlinks' if _is_within(path.resolve(), root) else 'external_symlinks'
                exclusions[category] += 1
                continue
            kind = _file_kind(path, root)
            if kind != 'python' and SECRET_NAME_RGX.search(filename):
                exclusions['secrets'] += 1
                continue
            if kind is not None:
                try:
                    size = path.stat().st_size
                except OSError:
                    exclusions['unreadable'] += 1
                    continue
                if size > MAX_SCAN_BYTES:
                    exclusions['oversized'] += 1
                    continue
                candidates.append((path, kind))
            elif path.suffix == '.py' and GENERATED_FILE_RGX.search(
                path.relative_to(root).as_posix()
            ):
                exclusions['generated'] += 1

    yield from sorted(candidates, key=lambda item: item[0].relative_to(root).as_posix())


def _hash_bytes(data: bytes) -> str:
    """Return a lowercase SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def _minimum_python(specifier: str | None) -> tuple[int, int] | None:
    """Extract a conservative minimum Python version from a requirement specifier."""
    if not specifier:
        return None
    versions = [
        (int(match.group(1)), int(match.group(2)))
        for match in re.finditer(r'(?:>=|~=|==)\s*(\d+)\.(\d+)', specifier)
    ]
    return min(versions) if versions else None


def _target_python(version: str | None) -> tuple[int, int] | None:
    """Parse an explicit modernization target such as ``3.13`` or ``3.14.2``."""
    if version is None:
        return None
    match = re.fullmatch(r'\s*(\d+)\.(\d+)(?:\.\d+)?\s*', version)
    if match is None:
        raise ValueError(f'invalid target Python version: {version!r}')
    return int(match.group(1)), int(match.group(2))


def _load_pyproject(text: str | None) -> tuple[dict[str, Any], str | None]:
    """Load captured pyproject metadata, returning a parse error instead of raising."""
    if text is None:
        return {}, None
    try:
        return tomllib.loads(text), None
    except tomllib.TOMLDecodeError as exc:
        return {}, f'pyproject.toml: {type(exc).__name__}'


def _requirement_name(value: str) -> str:
    """Normalize the distribution name at the start of a requirement string."""
    match = re.match(r'\s*([A-Za-z0-9_.-]+)', value)
    return re.sub(r'[-_.]+', '-', match.group(1)).lower() if match else ''


def _is_my_basis_requirement(value: str) -> bool:
    """Recognize index, direct-reference, and VCS forms of my-basis."""
    normalized = _requirement_name(value)
    lowered = value.lower()
    return bool(
        normalized in {'my-basis', 'mybasis'}
        or 'doering-ai/libs/basis' in lowered
        or re.search(r'(?:^|[#&])egg=my[-_.]?basis(?:$|[&#])', lowered)
        or re.search(r'/my[-_.]?basis(?:\.git)?(?:@[^#\s]+)?(?:[#?\s]|$)', lowered)
    )


def _dependency_facts(
    pyproject: dict[str, Any],
    texts: dict[str, str],
) -> dict[str, str | bool | list[str]]:
    """Discover dependency managers and any existing my-basis declaration."""
    managers = [
        manager
        for filename, manager in (
            ('uv.lock', 'uv'),
            ('poetry.lock', 'poetry'),
            ('pdm.lock', 'pdm'),
            ('Pipfile', 'pipenv'),
            ('pylock.toml', 'pip'),
        )
        if filename in texts
    ]

    declarations: list[str] = []
    explicit_zero_runtime_dependencies = False
    project = pyproject.get('project', {})
    if isinstance(project, dict):
        dependencies = project.get('dependencies')
        if isinstance(dependencies, list):
            declarations.extend(str(value) for value in dependencies)
            explicit_zero_runtime_dependencies = not dependencies
    poetry = pyproject.get('tool', {})
    if isinstance(poetry, dict):
        poetry = poetry.get('poetry', {})
        if isinstance(poetry, dict):
            dependencies = poetry.get('dependencies', {})
            if isinstance(dependencies, dict):
                declarations.extend(str(name) for name in dependencies)

    for path, text in sorted(texts.items()):
        name = Path(path).name
        if '/' in path or not (name.startswith('requirements') and name.endswith('.txt')):
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('-e '):
                line = line.removeprefix('-e ').strip()
            elif line.startswith('-'):
                continue
            declarations.append(line)
        if 'pip' not in managers:
            managers.append('pip')

    basis_declarations = sorted(value for value in declarations if _is_my_basis_requirement(value))
    if not managers and 'pyproject.toml' in texts:
        managers.append('pep-517')
    return {
        'managers': sorted(set(managers)),
        'my_basis_present': bool(basis_declarations),
        'my_basis_declarations': basis_declarations,
        'explicit_zero_runtime_dependencies': explicit_zero_runtime_dependencies,
    }


def _task_names(text: str) -> list[str]:
    """Extract top-level Task task names without requiring a YAML parser."""
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == 'tasks:')
    except StopIteration:
        return []
    matches: list[tuple[int, str]] = []
    for line in lines[start + 1 :]:
        match = re.match(r'^( +)([A-Za-z0-9][A-Za-z0-9_.:-]*):(?:\s*#.*)?$', line)
        if match:
            matches.append((len(match.group(1)), match.group(2)))
    if not matches:
        return []
    indentation = min(size for size, _ in matches)
    return sorted({name for size, name in matches if size == indentation})


def _command_facts(pyproject: dict[str, Any], texts: dict[str, str]) -> dict[str, list[str]]:
    """Discover task, make, project-script, and candidate native gate commands."""
    task_names: set[str] = set()
    for path, text in sorted(texts.items()):
        name = Path(path).name
        if '/' not in path and name.startswith('Taskfile') and name.endswith(('.yaml', '.yml')):
            task_names.update(_task_names(text))

    make_targets: set[str] = set()
    if makefile_text := texts.get('Makefile'):
        for line in makefile_text.splitlines():
            if match := re.match(r'^([A-Za-z0-9][A-Za-z0-9_.-]*):(?:\s|$)', line):
                make_targets.add(match.group(1))

    scripts: list[str] = []
    project = pyproject.get('project', {})
    if isinstance(project, dict) and isinstance(project.get('scripts'), dict):
        scripts = sorted(str(name) for name in project['scripts'])

    candidate_native_gates = [
        f'task {name}' for name in ('eval', 'test', 'test:cov', 'docs') if name in task_names
    ]
    if not candidate_native_gates:
        candidate_native_gates = [
            f'make {name}'
            for name in ('check', 'test', 'lint', 'typecheck', 'docs')
            if name in make_targets
        ]
    if not candidate_native_gates:
        declarations = json.dumps(pyproject, sort_keys=True)
        for marker, command in (
            ('pytest', 'uv run pytest'),
            ('ruff', 'uv run ruff check .'),
            ('pyrefly', 'uv run pyrefly check'),
            ('mypy', 'uv run mypy .'),
        ):
            if marker in declarations:
                candidate_native_gates.append(command)

    return {
        'task': sorted(task_names),
        'make': sorted(make_targets),
        'project_scripts': scripts,
        'candidate_native_gates': candidate_native_gates,
    }


class _PythonVisitor(ast.NodeVisitor):
    """Collect import and regular-expression facts from one syntax tree."""

    def __init__(self, path: str, *, test: bool) -> None:
        self.path = path
        self.test = test
        self.imports: Counter[str] = Counter()
        self.regex_aliases: dict[str, Literal['re', 'regex']] = {}
        self.regex_functions: dict[str, tuple[Literal['re', 'regex'], str]] = {}
        self.regex_store_aliases: set[str] = set()
        self.regex_store_references = 0
        self.patterns: list[RegexPatternFact] = []
        self.dynamic_calls = 0

    def visit_Import(self, node: ast.Import) -> None:
        """Collect ordinary imports and regex engine aliases."""
        for alias in node.names:
            module = alias.name.split('.')[0]
            self.imports[module] += 1
            if module in {'re', 'regex'}:
                self.regex_aliases[alias.asname or module] = module
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Collect from-imports, direct regex calls, and RegexStore aliases."""
        module = '.' if node.level else (node.module or '').split('.')[0] or '.'
        self.imports[module] += 1
        if module in {'re', 'regex'}:
            for alias in node.names:
                if alias.name in REGEX_OPERATIONS:
                    self.regex_functions[alias.asname or alias.name] = (module, alias.name)
        if module == 'my':
            for alias in node.names:
                if alias.name == 'RegexStore':
                    self.regex_store_aliases.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """Count uses of an imported RegexStore symbol."""
        if node.id in self.regex_store_aliases:
            self.regex_store_references += 1
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Collect regex engine calls and literal patterns."""
        function = node.func
        resolved: tuple[Literal['re', 'regex'], str] | None = None
        if (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id in self.regex_aliases
            and function.attr in REGEX_OPERATIONS
        ):
            resolved = (self.regex_aliases[function.value.id], function.attr)
        elif isinstance(function, ast.Name):
            resolved = self.regex_functions.get(function.id)
        if resolved is not None:
            engine, operation = resolved
            pattern: str | None = None
            if (
                node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                pattern = node.args[0].value
            else:
                self.dynamic_calls += 1
            self.patterns.append(
                RegexPatternFact(
                    path=self.path,
                    line=node.lineno,
                    engine=engine,
                    operation=operation,
                    pattern=pattern,
                    pattern_sha256=_hash_bytes(pattern.encode()) if pattern is not None else None,
                    complex=bool(
                        pattern
                        and (
                            len(pattern) >= 80
                            or sum(marker in pattern for marker in COMPLEX_REGEX_MARKERS) > 0
                            or pattern.count('(') >= 4
                        )
                    ),
                    test=self.test,
                )
            )
        self.generic_visit(node)


def _python_facts(
    root: Path,
    files: list[ScannedFile],
) -> tuple[
    list[ImportFact],
    list[RegexPatternFact],
    int,
    list[str],
    int,
    list[str],
    dict[str, int],
]:
    """Parse captured Python bytes and aggregate architecture facts."""
    import_counts: Counter[str] = Counter()
    import_files: defaultdict[str, set[str]] = defaultdict(set)
    patterns: list[RegexPatternFact] = []
    regex_store_references = 0
    regex_store_paths: set[str] = set()
    dynamic_calls = 0
    parse_errors: list[str] = []
    counts = {'files': 0, 'test_files': 0, 'lines': 0}

    for path, kind, data in files:
        if kind != 'python':
            continue
        relative = path.relative_to(root).as_posix()
        source = data.decode(errors='replace')
        is_test = relative.startswith(('test/', 'tests/'))
        counts['files'] += 1
        counts['test_files'] += is_test
        counts['lines'] += source.count('\n') + bool(source)
        try:
            tree = ast.parse(source, filename=relative)
        except (SyntaxError, ValueError) as exc:
            parse_errors.append(
                f'{relative}:{getattr(exc, "lineno", 0) or 0}: {type(exc).__name__}'
            )
            continue
        visitor = _PythonVisitor(relative, test=is_test)
        visitor.visit(tree)
        import_counts.update(visitor.imports)
        for module in visitor.imports:
            import_files[module].add(relative)
        patterns.extend(visitor.patterns)
        regex_store_references += visitor.regex_store_references
        if visitor.regex_store_references:
            regex_store_paths.add(relative)
        dynamic_calls += visitor.dynamic_calls

    imports = [
        ImportFact(module=module, occurrences=count, files=sorted(import_files[module]))
        for module, count in sorted(import_counts.items())
    ]
    return (
        imports,
        sorted(patterns, key=lambda item: (item.path, item.line, item.operation)),
        regex_store_references,
        sorted(regex_store_paths),
        dynamic_calls,
        sorted(parse_errors),
        counts,
    )


def _signals(
    *,
    python_count: int,
    python_specifier: str | None,
    target_python: tuple[int, int] | None,
    dependency_present: bool,
    explicit_zero_runtime_dependencies: bool,
    regex_store_references: int,
    regex_store_paths: list[str],
    patterns: list[RegexPatternFact],
) -> tuple[dict[str, str], list[Signal]]:
    """Derive conservative adoption signals from scanner facts."""
    output = [
        Signal(
            id='detector.scope',
            level='info',
            summary=(
                'Deterministic opportunity detection is regex-focused; inspect the other '
                'inventories and opportunity-map categories manually.'
            ),
        )
    ]
    minimum = _minimum_python(python_specifier)
    production_patterns = [pattern for pattern in patterns if not pattern.test]
    complex_patterns = [pattern for pattern in production_patterns if pattern.complex]
    calls_by_path = Counter(pattern.path for pattern in production_patterns)
    consolidation_paths = sorted(path for path, count in calls_by_path.items() if count >= 3)
    has_regex_opportunity = bool(
        complex_patterns or (consolidation_paths and not regex_store_references)
    )

    if not python_count:
        disposition = {
            'status': 'no-op',
            'reason': 'No authored Python files were found in the scanned repository.',
        }
        output.append(
            Signal(
                id='adoption.no-python',
                level='info',
                summary=disposition['reason'],
            )
        )
    elif (
        minimum is not None
        and minimum < MY_BASIS_PYTHON_FLOOR
        and (target_python is None or target_python < MY_BASIS_PYTHON_FLOOR)
    ):
        disposition = {
            'status': 'defer',
            'reason': (
                f'The declared Python floor {minimum[0]}.{minimum[1]} is below '
                'my-basis 1.0 floor 3.12; no compatible modernization target was supplied.'
            ),
        }
        output.append(
            Signal(
                id='adoption.python-floor',
                level='constraint',
                summary=disposition['reason'],
                evidence=['pyproject.toml'],
            )
        )
    elif minimum is not None and minimum < MY_BASIS_PYTHON_FLOOR:
        assert target_python is not None
        disposition = {
            'status': 'review',
            'reason': (
                f'The declared Python floor {minimum[0]}.{minimum[1]} is below my-basis 1.0, '
                f'but the requested {target_python[0]}.{target_python[1]} target makes a '
                'floor-raising refactor reviewable.'
            ),
        }
        output.append(
            Signal(
                id='adoption.python-modernization',
                level='opportunity',
                summary=disposition['reason'],
                evidence=['pyproject.toml'],
            )
        )
    elif dependency_present and not has_regex_opportunity:
        disposition = {
            'status': 'no-op',
            'reason': 'my-basis is already declared and no new bounded scanner lead was found.',
        }
        output.append(
            Signal(
                id='adoption.already-present',
                level='info',
                summary=disposition['reason'],
                evidence=['pyproject.toml'],
            )
        )
    else:
        disposition = {
            'status': 'review',
            'reason': 'Review the evidence before selecting or declining bounded adoptions.',
        }
        output.append(
            Signal(
                id='adoption.review',
                level='opportunity',
                summary=disposition['reason'],
            )
        )

    if dependency_present:
        output.append(
            Signal(
                id='basis.present',
                level='info',
                summary='The repository already declares a my-basis dependency.',
                evidence=['pyproject.toml'],
            )
        )
    if explicit_zero_runtime_dependencies:
        output.append(
            Signal(
                id='adoption.zero-runtime-dependencies',
                level='constraint',
                summary=(
                    'The project explicitly declares zero runtime dependencies; confirm its '
                    'dependency budget and startup or failure-path contract before adoption.'
                ),
                evidence=['pyproject.toml'],
            )
        )
    if regex_store_references:
        output.append(
            Signal(
                id='regexstore.present',
                level='info',
                summary='RegexStore is already referenced; preserve its established local idiom.',
                evidence=regex_store_paths,
            )
        )
    if disposition['status'] != 'defer':
        if complex_patterns:
            output.append(
                Signal(
                    id='regexstore.complex-patterns',
                    level='opportunity',
                    summary=(
                        f'{len(complex_patterns)} production literal regex call(s) merit '
                        'inspection; the detector does not establish a reusable grammar.'
                    ),
                    evidence=sorted({pattern.path for pattern in complex_patterns}),
                )
            )
        elif consolidation_paths and not regex_store_references:
            output.append(
                Signal(
                    id='regexstore.consolidation',
                    level='opportunity',
                    summary='Repeated regex calls in one source module merit inspection.',
                    evidence=consolidation_paths,
                )
            )
    return disposition, sorted(output, key=lambda item: item.id)


def scan_repository(
    repository: Path | str,
    *,
    target_python: str | None = None,
) -> Intake:
    """Return deterministic adoption facts for a local repository.

    Args:
        repository: Repository root to inspect.
        target_python: Optional operator-requested modernization target.
    Returns:
        Content-derived facts with relative evidence paths and stable hashes.
    Raises:
        FileNotFoundError: If the repository directory does not exist.
        NotADirectoryError: If the repository path is not a directory.
    """
    root = Path(repository).expanduser().resolve()
    target = _target_python(target_python)
    if not root.exists():
        raise FileNotFoundError(f'repository does not exist: {root}')
    if not root.is_dir():
        raise NotADirectoryError(f'repository is not a directory: {root}')

    exclusions: Counter[str] = Counter()
    files: list[ScannedFile] = []
    for path, kind in _iter_files(root, exclusions):
        try:
            data = path.read_bytes()
        except OSError:
            exclusions['unreadable'] += 1
            continue
        if len(data) > MAX_SCAN_BYTES:
            exclusions['oversized'] += 1
            continue
        files.append((path, kind, data))

    evidence = [
        FileEvidence(
            path=path.relative_to(root).as_posix(),
            kind=kind,
            sha256=_hash_bytes(data),
        )
        for path, kind, data in files
    ]
    texts = {
        path.relative_to(root).as_posix(): data.decode(errors='replace') for path, _, data in files
    }
    source_digest = _hash_bytes(
        json.dumps(
            [(item.path, item.sha256) for item in evidence],
            ensure_ascii=False,
            separators=(',', ':'),
        ).encode()
    )

    pyproject, pyproject_error = _load_pyproject(texts.get('pyproject.toml'))
    project = pyproject.get('project', {})
    if not isinstance(project, dict):
        project = {}
    python_specifier = (
        str(project['requires-python']) if project.get('requires-python') is not None else None
    )
    minimum = _minimum_python(python_specifier)
    dependencies = _dependency_facts(pyproject, texts)
    commands = _command_facts(pyproject, texts)
    (
        imports,
        patterns,
        regex_store_references,
        regex_store_paths,
        dynamic_calls,
        parse_errors,
        counts,
    ) = _python_facts(root, files)
    if pyproject_error:
        parse_errors.append(pyproject_error)
    disposition, signals = _signals(
        python_count=counts['files'],
        python_specifier=python_specifier,
        target_python=target,
        dependency_present=bool(dependencies['my_basis_present']),
        explicit_zero_runtime_dependencies=bool(dependencies['explicit_zero_runtime_dependencies']),
        regex_store_references=regex_store_references,
        regex_store_paths=regex_store_paths,
        patterns=patterns,
    )

    imports_by_module = {item.module: item for item in imports}
    sublime_imports = imports_by_module.get('sublime')
    mybasis_imports = imports_by_module.get('myBasis') or imports_by_module.get('mybasis')
    copied_mybasis_files = sorted(
        item.path for item in evidence if item.path.startswith(('myBasis/', 'mybasis/'))
    )
    host_python = texts.get('.python-version', '').strip() or None
    sublime: dict[str, str | bool | list[str] | None] = {
        'detected': bool(sublime_imports or host_python or copied_mybasis_files),
        'host_python': host_python,
        'imports': sublime_imports.files if sublime_imports else [],
        'mybasis_imports': mybasis_imports.files if mybasis_imports else [],
        'copied_mybasis_files': copied_mybasis_files,
    }
    if sublime['detected']:
        signals.append(
            Signal(
                id='sublime.host',
                level='info',
                summary=(
                    'Sublime plugin-host repository detected; marker is '
                    f'{host_python or "not set"}.'
                ),
                evidence=(['.python-version'] if host_python else [])
                + (sublime_imports.files if sublime_imports else []),
            )
        )
    if copied_mybasis_files:
        signals.append(
            Signal(
                id='sublime.copied-mybasis',
                level='opportunity',
                summary=(
                    f'{len(copied_mybasis_files)} local myBasis file(s) may duplicate canonical '
                    'my-basis structures; compare behavior before replacement.'
                ),
                evidence=copied_mybasis_files,
            )
        )
    signals = sorted(signals, key=lambda item: item.id)

    distribution = str(project['name']) if project.get('name') is not None else None
    python: dict[str, str | int | bool | None | list[str]] = {
        'requires_python': python_specifier,
        'minimum': f'{minimum[0]}.{minimum[1]}' if minimum else None,
        'target': f'{target[0]}.{target[1]}' if target else None,
        'my_basis_floor_compatible': minimum is not None and minimum >= MY_BASIS_PYTHON_FLOOR,
        'files': counts['files'],
        'test_files': counts['test_files'],
        'lines': counts['lines'],
    }
    production_patterns = [pattern for pattern in patterns if not pattern.test]
    test_patterns = [pattern for pattern in patterns if pattern.test]
    regex: dict[str, int | bool | list[RegexPatternFact]] = {
        'calls': len(patterns),
        'dynamic_calls': dynamic_calls,
        'complex_calls': sum(pattern.complex for pattern in patterns),
        'production_calls': len(production_patterns),
        'production_dynamic_calls': sum(pattern.pattern is None for pattern in production_patterns),
        'production_complex_calls': sum(pattern.complex for pattern in production_patterns),
        'test_calls': len(test_patterns),
        'test_dynamic_calls': sum(pattern.pattern is None for pattern in test_patterns),
        'test_complex_calls': sum(pattern.complex for pattern in test_patterns),
        'regex_store_references': regex_store_references,
        'patterns': patterns,
    }
    exclusion_counts = {
        key: exclusions.get(key, 0)
        for key in (
            'directories',
            'external_symlinks',
            'generated',
            'oversized',
            'secrets',
            'symlinks',
            'unreadable',
        )
    }
    return Intake(
        repository={'name': root.name, 'distribution': distribution},
        source_digest=source_digest,
        python=python,
        dependency=dependencies,
        commands=commands,
        imports=imports,
        regex=regex,
        sublime=sublime,
        exclusions=exclusion_counts,
        parse_errors=sorted(parse_errors),
        disposition=disposition,
        signals=signals,
        evidence=evidence,
    )
