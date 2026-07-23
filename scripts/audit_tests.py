############
### HEAD ###
############
"""Audit a PyTest tree for the house's compact, parameterized test style.

The audit is deliberately static: it parses test modules without importing either the tests or
the project under test.  It reports objective collection hazards separately from advisory
parameterization opportunities, so ``--check`` can be used as a stable gate without turning a
subjective preference for parametrization into a build failure.

Deliberately depends only on ``pydantic`` + stdlib -- never on ``my`` -- so it keeps working
while that library is mid-refactor.
"""

### STANDARD
from __future__ import annotations
import argparse as ap
import ast
import copy
import hashlib
import io
import json
import statistics
import subprocess as sbp
import sys
import tokenize
from collections import defaultdict
from pathlib import Path
from typing import Any, ClassVar

### EXTERNAL
import pydantic as pyd


############
### DATA ###
############
#: Machine-readable contract version.  Increment when a field changes meaning.
SCHEMA_VERSION = 1

#: Names longer than this remain valid, but are called out as navigation friction.
LONG_TEST_NAME = 64

#: PyTest's default Python module patterns.
TEST_FILE_PATTERNS = ('test_*.py', '*_test.py')

#: Section markers recognized by the house Python layout.
IMPORT_SECTIONS = ('STANDARD', 'EXTERNAL', 'INTERNAL')


############
### BODY ###
############
class _LiteralNormalizer(ast.NodeTransformer):
    """Replace literal values while retaining their types and surrounding syntax."""

    # ------------------
    # `*` Public Methods
    # ------------------
    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        """Return a stable marker for one literal value."""
        if node.value is None:
            marker = '<none>'
        elif node.value is Ellipsis:
            marker = '<ellipsis>'
        elif isinstance(node.value, bool):
            marker = '<bool>'
        elif isinstance(node.value, str):
            marker = '<str>'
        elif isinstance(node.value, bytes):
            marker = '<bytes>'
        elif isinstance(node.value, complex):
            marker = '<complex>'
        elif isinstance(node.value, float):
            marker = '<float>'
        elif isinstance(node.value, int):
            marker = '<int>'
        else:
            marker = f'<{type(node.value).__name__}>'
        return ast.copy_location(ast.Constant(value=marker), node)


class Worker(pyd.BaseModel):
    """Inspect one PyTest tree and optionally compare it with a Git revision."""

    tests: Path
    baseline: str | None = None

    model_config: ClassVar[pyd.ConfigDict] = pyd.ConfigDict(arbitrary_types_allowed=True)

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyd.field_validator('tests')
    @classmethod
    def _validate_tests(cls, value: Path) -> Path:
        """Require an existing Python file or directory."""
        value = value.expanduser()
        if not value.exists():
            raise ValueError(f'test path does not exist: {value}')
        if value.is_file() and value.suffix != '.py':
            raise ValueError(f'test file is not Python: {value}')
        return value

    @property
    def project_root(self) -> Path:
        """Return the nearest Git root, or the test tree's parent when Git is absent."""
        anchor = self.tests if self.tests.is_dir() else self.tests.parent
        root, _message = self._git_root(anchor)
        if root is not None:
            return root
        return self.tests.parent

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    def _git_root(anchor: Path) -> tuple[Path | None, str]:
        """Resolve the containing Git root without mutating repository state."""
        try:
            result = sbp.run(
                ['git', '-C', str(anchor), 'rev-parse', '--show-toplevel'],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            return None, 'git executable is unavailable'
        except sbp.TimeoutExpired:
            return None, 'git root lookup timed out'
        if result.returncode:
            detail = result.stderr.strip()
            message = 'path is not inside a Git worktree'
            if detail:
                message = f'{message}: {detail}'
            return None, message
        return Path(result.stdout.strip()).resolve(), 'ok'

    @staticmethod
    def _run_git(root: Path, *args: str) -> tuple[int, str, str]:
        """Run one bounded, read-only Git query."""
        try:
            result = sbp.run(
                ['git', '-C', str(root), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            return 127, '', 'git executable is unavailable'
        except sbp.TimeoutExpired:
            return 124, '', f'git {" ".join(args[:2])} timed out'
        return result.returncode, result.stdout, result.stderr

    def _display_path(self, path: Path) -> str:
        """Render a stable project-relative path where possible."""
        try:
            return path.resolve().relative_to(self.project_root.resolve()).as_posix()
        except ValueError:
            return path.resolve().as_posix()

    def _current_sources(self) -> list[tuple[str, str]]:
        """Read current PyTest modules in deterministic path order."""
        if self.tests.is_file():
            files = [self.tests]
        else:
            files = sorted(
                {
                    file
                    for pattern in TEST_FILE_PATTERNS
                    for file in self.tests.rglob(pattern)
                    if file.is_file()
                }
            )
        return [(self._display_path(file), file.read_text()) for file in files]

    def _internal_roots(self) -> set[str]:
        """Discover high-confidence project import roots for section classification."""
        roots: set[str] = set()
        for child in self.project_root.iterdir():
            if child.name.startswith('.') or child.name in {'tests', 'test'}:
                continue
            if child.is_dir() and (child / '__init__.py').exists():
                roots.add(child.name)
            elif child.is_file() and child.suffix == '.py':
                roots.add(child.stem)
        return roots

    @staticmethod
    def _attribute_chain(node: ast.expr) -> str | None:
        """Return a dotted name for a simple attribute expression."""
        parts: list[str] = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
            return '.'.join(reversed(parts))
        return None

    @classmethod
    def _is_parametrize(cls, decorator: ast.expr) -> ast.Call | None:
        """Return the call node when a decorator is a PyTest parametrization."""
        if not isinstance(decorator, ast.Call):
            return None
        chain = cls._attribute_chain(decorator.func)
        if chain == 'parametrize' or (chain and chain.endswith('.mark.parametrize')):
            return decorator
        return None

    @staticmethod
    def _literal_sequence(node: ast.expr | None) -> list[ast.expr] | None:
        """Return statically enumerable elements, or ``None`` for dynamic values."""
        if isinstance(node, ast.List | ast.Tuple | ast.Set):
            return list(node.elts)
        return None

    @classmethod
    def _parametrize_info(cls, function: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
        """Describe all parametrization decorators and their statically known cases."""
        decorators: list[dict[str, Any]] = []
        case_count = 1
        exact = True

        for decorator in function.decorator_list:
            call = cls._is_parametrize(decorator)
            if call is None:
                continue
            names_node = call.args[0] if call.args else None
            rows_node = call.args[1] if len(call.args) > 1 else None
            ids_node: ast.expr | None = None
            for keyword in call.keywords:
                if keyword.arg == 'argnames' and names_node is None:
                    names_node = keyword.value
                elif keyword.arg == 'argvalues' and rows_node is None:
                    rows_node = keyword.value
                elif keyword.arg == 'ids':
                    ids_node = keyword.value

            if isinstance(names_node, ast.Constant) and isinstance(names_node.value, str):
                names = [name.strip() for name in names_node.value.split(',')]
            elif isinstance(names_node, ast.List | ast.Tuple):
                names = [
                    element.value
                    for element in names_node.elts
                    if isinstance(element, ast.Constant) and isinstance(element.value, str)
                ]
                if len(names) != len(names_node.elts):
                    names = []
            else:
                names = []

            rows = cls._literal_sequence(rows_node)
            row_ids: list[str | None] = []
            if rows is not None:
                for row in rows:
                    row_id: str | None = None
                    if isinstance(row, ast.Call):
                        chain = cls._attribute_chain(row.func)
                        if chain == 'param' or (chain and chain.endswith('.param')):
                            for keyword in row.keywords:
                                if (
                                    keyword.arg == 'id'
                                    and isinstance(keyword.value, ast.Constant)
                                    and isinstance(keyword.value.value, str)
                                ):
                                    row_id = keyword.value.value
                    row_ids.append(row_id)

            ids = cls._literal_sequence(ids_node)
            if ids is not None:
                id_values = [
                    element.value
                    for element in ids
                    if isinstance(element, ast.Constant) and isinstance(element.value, str)
                ]
                ids_kind = 'literal' if len(id_values) == len(ids) else 'partly-dynamic'
                ids_count: int | None = len(ids)
            elif ids_node is None:
                id_values = []
                ids_kind = 'none'
                ids_count = 0
            else:
                id_values = []
                ids_kind = 'dynamic'
                ids_count = None

            row_count = len(rows) if rows is not None else None
            if row_count is None:
                exact = False
            else:
                case_count *= row_count
            decorators.append(
                {
                    'line': decorator.lineno,
                    'parameters': names,
                    'rows': row_count,
                    'ids': {
                        'kind': ids_kind,
                        'count': ids_count,
                        'values': id_values,
                        'row_values': row_ids,
                    },
                }
            )

        return {
            'decorators': decorators,
            'parameterized': bool(decorators),
            'cases': case_count if exact else None,
            'minimum_cases': case_count,
        }

    @staticmethod
    def _literal_shape(function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Hash a function body after replacing literals, for refactor candidate grouping."""
        body = copy.deepcopy(function.body)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)
        module = ast.Module(body=body, type_ignores=[])
        normalized = _LiteralNormalizer().visit(module)
        shape = f'{type(function).__name__}:{ast.dump(normalized, include_attributes=False)}'
        return hashlib.sha256(shape.encode()).hexdigest()[:16]

    @staticmethod
    def _name_depth(name: str) -> int:
        """Count the method and optional scenario levels in one test name."""
        return len(name.removeprefix('test_').split('__'))

    @classmethod
    def _test_record(
        cls,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        scope: str,
    ) -> dict[str, Any]:
        """Build the stable report record for one collectable function."""
        parameterization = cls._parametrize_info(function)
        qualified_name = function.name if scope == 'module' else f'{scope}.{function.name}'
        return {
            'scope': scope,
            'name': function.name,
            'qualified_name': qualified_name,
            'line': function.lineno,
            'async': isinstance(function, ast.AsyncFunctionDef),
            'name_depth': cls._name_depth(function.name),
            'name_length': len(function.name),
            'parameterization': parameterization,
            'literal_shape': cls._literal_shape(function),
        }

    @staticmethod
    def _binding_name(statement: ast.stmt) -> tuple[str, str] | None:
        """Return a directly bound name and binding kind when it is unambiguous."""
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            return statement.name, 'function'
        if isinstance(statement, ast.ClassDef):
            return statement.name, 'class'
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                return target.id, 'assignment'
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            return statement.target.id, 'assignment'
        if isinstance(statement, ast.Import):
            if len(statement.names) == 1:
                alias = statement.names[0]
                return alias.asname or alias.name.split('.')[0], 'import'
        if isinstance(statement, ast.ImportFrom) and len(statement.names) == 1:
            alias = statement.names[0]
            return alias.asname or alias.name, 'import'
        return None

    @classmethod
    def _shadow_violations(
        cls,
        statements: list[ast.stmt],
        path: str,
        scope: str,
        prefix: str = 'test_',
    ) -> list[dict[str, Any]]:
        """Find duplicate or later-shadowed test bindings in one direct scope."""
        bindings: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for statement in statements:
            binding = cls._binding_name(statement)
            if binding is None:
                continue
            name, kind = binding
            if name.startswith(prefix):
                bindings[name].append((statement.lineno, kind))

        violations: list[dict[str, Any]] = []
        for name, events in sorted(bindings.items()):
            if len(events) < 2:
                continue
            lines = [line for line, _kind in events]
            kinds = [kind for _line, kind in events]
            violations.append(
                {
                    'code': 'shadowed-test',
                    'path': path,
                    'line': lines[-1],
                    'scope': scope,
                    'name': name,
                    'message': (
                        f'{name} is bound {len(events)} times at lines '
                        f'{", ".join(map(str, lines))} ({", ".join(kinds)})'
                    ),
                }
            )
        return violations

    @classmethod
    def _nested_test_helpers(
        cls,
        tree: ast.Module,
        collected: set[int],
        path: str,
    ) -> list[dict[str, Any]]:
        """Find test-like functions that PyTest does not collect from a direct test scope."""
        helpers: list[dict[str, Any]] = []

        def descend(node: ast.AST, scopes: tuple[str, ...]) -> None:
            for child in ast.iter_child_nodes(node):
                next_scopes = scopes
                if isinstance(child, ast.ClassDef):
                    next_scopes = (*scopes, child.name)
                elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                    if child.name.startswith('test_') and id(child) not in collected:
                        scope = '.'.join(scopes) or 'module'
                        helpers.append(
                            {
                                'code': 'nested-test-helper',
                                'path': path,
                                'line': child.lineno,
                                'scope': scope,
                                'name': child.name,
                                'message': (
                                    f'{child.name} is test-like but is not a direct module '
                                    'function or direct method on a module-level Test* class'
                                ),
                            }
                        )
                    next_scopes = (*scopes, child.name)
                descend(child, next_scopes)

        descend(tree, ())
        return helpers

    @staticmethod
    def _line_sections(source: str) -> tuple[dict[int, str | None], list[tuple[int, str]]]:
        """Map lines to their active import subsection and return seen markers."""
        active: str | None = None
        mapping: dict[int, str | None] = {}
        markers: list[tuple[int, str]] = []
        comments = {
            token.start[0]: token.string.strip()
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type == tokenize.COMMENT
        }
        for number in range(1, len(source.splitlines()) + 1):
            comment = comments.get(number, '')
            if comment in {f'### {section}' for section in IMPORT_SECTIONS}:
                active = comment.removeprefix('### ')
                markers.append((number, active))
            elif comment in {'### DATA ###', '### BODY ###', '### MAIN ###'}:
                active = None
            mapping[number] = active
        return mapping, markers

    @staticmethod
    def _import_name(node: ast.Import | ast.ImportFrom) -> str:
        """Return the root module represented by an import node."""
        if isinstance(node, ast.Import):
            return node.names[0].name.split('.')[0] if node.names else ''
        return (node.module or '').split('.')[0]

    @classmethod
    def _import_report(
        cls,
        tree: ast.Module,
        source: str,
        path: str,
        internal_roots: set[str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Classify direct imports and return objective section/style violations."""
        line_sections, markers = cls._line_sections(source)
        imports: list[dict[str, Any]] = []
        violations: list[dict[str, Any]] = []

        marker_names = [name for _line, name in markers]
        expected_order = [name for name in IMPORT_SECTIONS if name in marker_names]
        if marker_names != expected_order or len(marker_names) != len(set(marker_names)):
            line = markers[-1][0] if markers else 1
            violations.append(
                {
                    'code': 'import-section-order',
                    'path': path,
                    'line': line,
                    'scope': 'module',
                    'name': None,
                    'message': (
                        'import subsection markers must be unique and ordered '
                        'STANDARD, EXTERNAL, INTERNAL'
                    ),
                }
            )

        for statement in tree.body:
            if not isinstance(statement, ast.Import | ast.ImportFrom):
                continue
            module = cls._import_name(statement)
            section = line_sections.get(statement.lineno)
            if isinstance(statement, ast.ImportFrom) and statement.level:
                classification = 'internal'
                expected = 'INTERNAL'
            elif module in {'__future__'} or module in sys.stdlib_module_names:
                classification = 'standard'
                expected = 'STANDARD'
            elif module == 'pytest':
                classification = 'external'
                expected = 'EXTERNAL'
            elif module in internal_roots:
                classification = 'internal'
                expected = 'INTERNAL'
            else:
                classification = 'unknown'
                expected = None

            record = {
                'line': statement.lineno,
                'module': module,
                'classification': classification,
                'section': section,
                'expected_section': expected,
            }
            imports.append(record)
            if expected is not None and section != expected:
                violations.append(
                    {
                        'code': 'import-section',
                        'path': path,
                        'line': statement.lineno,
                        'scope': 'module',
                        'name': module,
                        'message': f'{module or "relative import"} belongs in ### {expected}',
                    }
                )

            if module != 'pytest':
                continue
            valid_style = (
                isinstance(statement, ast.Import)
                and len(statement.names) == 1
                and statement.names[0].name == 'pytest'
                and statement.names[0].asname == 'pyt'
            )
            if not valid_style:
                violations.append(
                    {
                        'code': 'pytest-import-style',
                        'path': path,
                        'line': statement.lineno,
                        'scope': 'module',
                        'name': 'pytest',
                        'message': 'import pytest exactly as `import pytest as pyt`',
                    }
                )

        return imports, violations

    @classmethod
    def _scan_source(
        cls,
        path: str,
        source: str,
        internal_roots: set[str],
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """Parse one source string without importing it."""
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as error:
            diagnostic = {
                'code': 'syntax-error',
                'path': path,
                'line': error.lineno or 1,
                'message': error.msg,
            }
            return None, [diagnostic]

        tests: list[dict[str, Any]] = []
        violations: list[dict[str, Any]] = []
        collected: set[int] = set()

        module_functions = [
            statement
            for statement in tree.body
            if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef)
            and statement.name.startswith('test_')
        ]
        for function in module_functions:
            collected.add(id(function))
            tests.append(cls._test_record(function, 'module'))
        violations.extend(cls._shadow_violations(tree.body, path, 'module'))

        test_classes = [
            statement
            for statement in tree.body
            if isinstance(statement, ast.ClassDef) and statement.name.startswith('Test')
        ]
        class_bindings: dict[str, list[int]] = defaultdict(list)
        for test_class in test_classes:
            class_bindings[test_class.name].append(test_class.lineno)
            methods = [
                statement
                for statement in test_class.body
                if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef)
                and statement.name.startswith('test_')
            ]
            for method in methods:
                collected.add(id(method))
                tests.append(cls._test_record(method, test_class.name))
            violations.extend(cls._shadow_violations(test_class.body, path, test_class.name))
        for name, lines in sorted(class_bindings.items()):
            if len(lines) > 1:
                violations.append(
                    {
                        'code': 'shadowed-test-class',
                        'path': path,
                        'line': lines[-1],
                        'scope': 'module',
                        'name': name,
                        'message': (
                            f'{name} is defined {len(lines)} times at lines '
                            f'{", ".join(map(str, lines))}'
                        ),
                    }
                )

        violations.extend(cls._nested_test_helpers(tree, collected, path))
        imports, import_violations = cls._import_report(tree, source, path, internal_roots)
        violations.extend(import_violations)

        violations.extend(
            [
                {
                    'code': 'test-name-depth',
                    'path': path,
                    'line': test['line'],
                    'scope': test['scope'],
                    'name': test['name'],
                    'message': (
                        f'{test["name"]} has {test["name_depth"]} levels; '
                        'the maximum is method plus one scenario'
                    ),
                }
                for test in tests
                if test['name_depth'] > 2
            ]
        )

        return {
            'path': path,
            'tests': sorted(tests, key=lambda item: (item['line'], item['qualified_name'])),
            'imports': imports,
            'violations': sorted(
                violations,
                key=lambda item: (
                    item['line'],
                    item['code'],
                    item.get('name') or '',
                ),
            ),
        }, []

    @staticmethod
    def _clusters(files: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Group same-stem and same-literal-shape functions within direct scopes."""
        stems: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        shapes: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for file in files:
            for test in file['tests']:
                stem = test['name'].split('__', maxsplit=1)[0]
                stems[(file['path'], test['scope'], stem)].append(test)
                shapes[(file['path'], test['scope'], test['literal_shape'])].append(test)

        def render(
            groups: dict[tuple[str, str, str], list[dict[str, Any]]],
            key_name: str,
        ) -> list[dict[str, Any]]:
            rendered: list[dict[str, Any]] = []
            for (path, scope, key), members in sorted(groups.items()):
                if len(members) < 2:
                    continue
                rendered.append(
                    {
                        'path': path,
                        'scope': scope,
                        key_name: key,
                        'members': [
                            {
                                'name': member['name'],
                                'line': member['line'],
                                'parameterized': member['parameterization']['parameterized'],
                            }
                            for member in members
                        ],
                    }
                )
            return rendered

        return {
            'same_stem': render(stems, 'stem'),
            'literal_shape': render(shapes, 'shape'),
        }

    @classmethod
    def _summary(
        cls,
        files: list[dict[str, Any]],
        diagnostics: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Summarize function, case, naming, and violation counts."""
        tests = [test for file in files for test in file['tests']]
        violations = [violation for file in files for violation in file['violations']]
        exact_cases = [
            test['parameterization']['cases']
            for test in tests
            if test['parameterization']['cases'] is not None
        ]
        unknown_cases = sum(test['parameterization']['cases'] is None for test in tests)
        minimum_cases = sum(test['parameterization']['minimum_cases'] for test in tests)
        names = [test['name_length'] for test in tests]
        qualified = [test['qualified_name'] for test in tests]

        return {
            'files': len(files),
            'functions': len(tests),
            'unique_functions': len(set(qualified)),
            'parameterized_functions': sum(
                test['parameterization']['parameterized'] for test in tests
            ),
            'cases': {
                'exact': sum(exact_cases) if not unknown_cases else None,
                'minimum': minimum_cases,
                'unknown_functions': unknown_cases,
            },
            'names': {
                'maximum_length': max(names, default=0),
                'median_length': statistics.median(names) if names else 0,
                'longer_than_64': sum(length > LONG_TEST_NAME for length in names),
                'maximum_depth': max((test['name_depth'] for test in tests), default=0),
            },
            'violations': len(violations),
            'diagnostics': len(diagnostics),
        }

    @classmethod
    def _scan_sources(
        cls,
        sources: list[tuple[str, str]],
        internal_roots: set[str],
    ) -> dict[str, Any]:
        """Audit source strings into a deterministic report fragment."""
        files: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        for path, source in sorted(sources):
            file, file_diagnostics = cls._scan_source(path, source, internal_roots)
            if file is not None:
                files.append(file)
            diagnostics.extend(file_diagnostics)
        violations = sorted(
            [violation for file in files for violation in file['violations']],
            key=lambda item: (
                item['path'],
                item['line'],
                item['code'],
                item.get('name') or '',
            ),
        )
        diagnostics.sort(key=lambda item: (item['path'], item['line'], item['code']))
        return {
            'summary': cls._summary(files, diagnostics),
            'files': files,
            'clusters': cls._clusters(files),
            'violations': violations,
            'diagnostics': diagnostics,
        }

    def _baseline_report(self, current: dict[str, Any]) -> dict[str, Any]:
        """Read and audit the requested Git revision, degrading to a clear status."""
        if self.baseline is None:
            return {
                'requested': None,
                'available': False,
                'message': 'no baseline requested',
            }

        git_root, message = self._git_root(self.tests if self.tests.is_dir() else self.tests.parent)
        if git_root is None:
            return {
                'requested': self.baseline,
                'available': False,
                'message': message,
            }
        try:
            relative_tests = self.tests.resolve().relative_to(git_root).as_posix()
        except ValueError:
            return {
                'requested': self.baseline,
                'available': False,
                'message': 'test path is outside its containing Git worktree',
            }

        returncode, revision, error = self._run_git(
            git_root,
            'rev-parse',
            '--verify',
            '--end-of-options',
            f'{self.baseline}^{{commit}}',
        )
        if returncode:
            return {
                'requested': self.baseline,
                'available': False,
                'message': error.strip() or f'unknown Git revision: {self.baseline}',
            }
        revision = revision.strip()

        returncode, listing, error = self._run_git(
            git_root,
            'ls-tree',
            '-r',
            '--name-only',
            revision,
            '--',
            relative_tests,
        )
        if returncode:
            return {
                'requested': self.baseline,
                'available': False,
                'revision': revision,
                'message': error.strip() or 'unable to list baseline tests',
            }

        paths = sorted(
            path
            for path in listing.splitlines()
            if any(Path(path).match(pattern) for pattern in TEST_FILE_PATTERNS)
        )
        sources: list[tuple[str, str]] = []
        for path in paths:
            returncode, source, error = self._run_git(git_root, 'show', f'{revision}:{path}')
            if returncode:
                return {
                    'requested': self.baseline,
                    'available': False,
                    'revision': revision,
                    'message': error.strip() or f'unable to read {path} at baseline',
                }
            sources.append((path, source))

        baseline = self._scan_sources(sources, self._internal_roots())
        fields = ('functions', 'parameterized_functions', 'violations')
        delta = {field: current['summary'][field] - baseline['summary'][field] for field in fields}
        delta['minimum_cases'] = (
            current['summary']['cases']['minimum'] - baseline['summary']['cases']['minimum']
        )
        return {
            'requested': self.baseline,
            'available': True,
            'revision': revision,
            'message': 'ok',
            'summary': baseline['summary'],
            'delta': delta,
        }

    # ------------------
    # `*` Public Methods
    # ------------------
    def __call__(self) -> dict[str, Any]:
        """Return the complete current and optional-baseline audit."""
        current = self._scan_sources(self._current_sources(), self._internal_roots())
        return {
            'schema_version': SCHEMA_VERSION,
            'tests_root': self._display_path(self.tests),
            **current,
            'baseline': self._baseline_report(current),
        }


def render_markdown(report: dict[str, Any]) -> str:
    """Render an audit as compact, deterministic MyST-compatible Markdown."""

    def clean(value: object) -> str:
        return str(value).replace('|', '\\|').replace('\n', ' ')

    summary = report['summary']
    cases = summary['cases']
    lines = [
        '# PyTest style audit',
        '',
        f'**Test tree:** `{report["tests_root"]}`  ',
        f'**Schema:** `{report["schema_version"]}`',
        '',
        '## Summary',
        '',
        '| Files | Functions | Parameterized | Cases | Violations | Diagnostics |',
        '| ---: | ---: | ---: | ---: | ---: | ---: |',
        (
            f'| {summary["files"]} | {summary["functions"]} | '
            f'{summary["parameterized_functions"]} | '
            f'{cases["exact"] if cases["exact"] is not None else f"≥{cases['minimum']}"} | '
            f'{summary["violations"]} | {summary["diagnostics"]} |'
        ),
        '',
        (
            f'Names: median length `{summary["names"]["median_length"]}`, maximum length '
            f'`{summary["names"]["maximum_length"]}`, maximum depth '
            f'`{summary["names"]["maximum_depth"]}`. Names over `{LONG_TEST_NAME}` characters '
            'are advisory only.'
        ),
        '',
        '## Baseline',
        '',
    ]

    baseline = report['baseline']
    if baseline['available']:
        delta = baseline['delta']
        lines.extend(
            [
                (
                    f'Compared with `{clean(baseline["requested"])}` at '
                    f'`{baseline["revision"][:12]}`.'
                ),
                '',
                '| Functions Δ | Parameterized Δ | Minimum cases Δ | Violations Δ |',
                '| ---: | ---: | ---: | ---: |',
                (
                    f'| {delta["functions"]:+d} | {delta["parameterized_functions"]:+d} | '
                    f'{delta["minimum_cases"]:+d} | {delta["violations"]:+d} |'
                ),
            ]
        )
    else:
        requested = (
            f' for `{clean(baseline["requested"])}`' if baseline['requested'] is not None else ''
        )
        lines.append(f'Baseline unavailable{requested}: {clean(baseline["message"])}.')

    lines.extend(['', '## Objective violations', ''])
    if report['violations']:
        lines.extend(
            [
                '| File | Line | Code | Test/scope | Detail |',
                '| --- | ---: | --- | --- | --- |',
            ]
        )
        for violation in report['violations']:
            subject = violation.get('name') or violation.get('scope') or ''
            lines.append(
                f'| `{clean(violation["path"])}` | {violation["line"]} | '
                f'`{violation["code"]}` | `{clean(subject)}` | '
                f'{clean(violation["message"])} |'
            )
    else:
        lines.append('No objective violations.')

    lines.extend(['', '## Parameterization candidates', ''])
    same_stem = report['clusters']['same_stem']
    literal_shape = report['clusters']['literal_shape']
    if not same_stem and not literal_shape:
        lines.append('No repeated same-stem or literal-shape clusters.')
    else:
        if same_stem:
            lines.extend(['### Same stem', ''])
            for cluster in same_stem:
                members = ', '.join(
                    f'`{member["name"]}:{member["line"]}`' for member in cluster['members']
                )
                lines.append(
                    f'- `{cluster["path"]}::{cluster["scope"]}` / `{cluster["stem"]}`: {members}'
                )
        if literal_shape:
            lines.extend(['', '### Same literal-normalized shape', ''])
            for cluster in literal_shape:
                members = ', '.join(
                    f'`{member["name"]}:{member["line"]}`' for member in cluster['members']
                )
                lines.append(
                    f'- `{cluster["path"]}::{cluster["scope"]}` / `{cluster["shape"]}`: {members}'
                )

    lines.extend(['', '## Files', ''])
    lines.extend(
        [
            '| File | Functions | Parameterized | Minimum cases | Violations |',
            '| --- | ---: | ---: | ---: | ---: |',
        ]
    )
    for file in report['files']:
        tests = file['tests']
        lines.append(
            f'| `{clean(file["path"])}` | {len(tests)} | '
            f'{sum(test["parameterization"]["parameterized"] for test in tests)} | '
            f'{sum(test["parameterization"]["minimum_cases"] for test in tests)} | '
            f'{len(file["violations"])} |'
        )

    if report['diagnostics']:
        lines.extend(['', '## Diagnostics', ''])
        lines.extend(
            [
                f'- `{clean(diagnostic["path"])}:{diagnostic["line"]}` '
                f'`{diagnostic["code"]}`: {clean(diagnostic["message"])}'
                for diagnostic in report['diagnostics']
            ]
        )

    return '\n'.join(lines).rstrip() + '\n'


############
### MAIN ###
############
def _cli(*vargs: str) -> ap.Namespace:
    """Parse command-line arguments."""
    parser = ap.ArgumentParser(
        description=(
            'Statically audit direct PyTest functions and Test* methods for compact naming, '
            'parameterization opportunities, and objective collection hazards.'
        )
    )
    parser.add_argument(
        '--tests',
        type=Path,
        default=Path('tests'),
        help='PyTest directory or one Python test module (default: tests).',
    )
    parser.add_argument(
        '--baseline',
        help='Optional Git revision whose matching test tree should be compared read-only.',
    )
    parser.add_argument(
        '--json',
        type=Path,
        metavar='PATH',
        help='Write deterministic JSON to PATH; use - for stdout.',
    )
    parser.add_argument(
        '--markdown',
        type=Path,
        metavar='PATH',
        help='Write deterministic MyST-compatible Markdown to PATH; use - for stdout.',
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Exit 1 only for objective naming, collection, or import-section violations.',
    )
    args = parser.parse_args(vargs or None)
    if args.json == Path('-') and args.markdown == Path('-'):
        parser.error('--json - and --markdown - cannot both own stdout')
    return args


def _write_output(path: Path, content: str) -> None:
    """Write one requested format, or emit it to stdout for ``-``."""
    if path == Path('-'):
        print(content, end='')
    else:
        path.write_text(content)


def main(*vargs: str) -> int:
    """Audit a test tree, render requested outputs, and return the check status."""
    args = _cli(*vargs)
    report = Worker(tests=args.tests, baseline=args.baseline)()
    json_output = json.dumps(report, indent=2, sort_keys=True) + '\n'
    markdown_output = render_markdown(report)

    if args.json is not None:
        _write_output(args.json, json_output)
    if args.markdown is not None:
        _write_output(args.markdown, markdown_output)
    if args.json is None and args.markdown is None:
        print(markdown_output, end='')

    return int(bool(args.check and report['violations']))


if __name__ == '__main__':
    raise SystemExit(main())
