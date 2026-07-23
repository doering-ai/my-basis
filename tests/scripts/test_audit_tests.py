############
### HEAD ###
############
### STANDARD
from __future__ import annotations
import json
import subprocess as sbp
from collections.abc import Callable
from pathlib import Path
from typing import Any

### EXTERNAL
import pytest as pyt

### INTERNAL
from scripts.audit_tests import Worker, main, render_markdown


############
### DATA ###
############
type ProjectFactory = Callable[[str], Path]


############
### BODY ###
############
class TestWorker:
    """Test static collection and test-style analysis."""

    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.fixture
    def project(self, tmp_path: Path) -> ProjectFactory:
        """Build a minimal project around one synthetic PyTest module."""

        def build(source: str) -> Path:
            root = tmp_path / 'repo'
            package = root / 'pkg'
            tests = root / 'tests'
            package.mkdir(parents=True, exist_ok=True)
            tests.mkdir(parents=True, exist_ok=True)
            (package / '__init__.py').write_text('VALUE = 1\n')
            (tests / 'test_sample.py').write_text(source)
            return tests

        return build

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'source, expected',
        [
            (
                """\
def test_plain():
    assert True
""",
                {
                    'functions': 1,
                    'parameterized': 0,
                    'cases': 1,
                    'minimum': 1,
                    'unknown': 0,
                    'depth': 1,
                    'async': False,
                    'rows': [],
                },
            ),
            (
                """\
import pytest as pyt

class TestValue:
    @pyt.mark.parametrize('value', [1, 2], ids=['one', 'two'])
    def test_value(self, value):
        assert value
""",
                {
                    'functions': 1,
                    'parameterized': 1,
                    'cases': 2,
                    'minimum': 2,
                    'unknown': 0,
                    'depth': 1,
                    'async': False,
                    'rows': [2],
                    'ids': ['one', 'two'],
                },
            ),
            (
                """\
import pytest as pyt

@pyt.mark.parametrize('left', [1, 2])
@pyt.mark.parametrize('right', [3, 4, 5])
def test_product__matrix(left, right):
    assert left < right
""",
                {
                    'functions': 1,
                    'parameterized': 1,
                    'cases': 6,
                    'minimum': 6,
                    'unknown': 0,
                    'depth': 2,
                    'async': False,
                    'rows': [2, 3],
                },
            ),
            (
                """\
import pytest as pyt

CASES = [(1, 2)]

@pyt.mark.parametrize('value, expected', CASES)
def test_dynamic(value, expected):
    assert value != expected
""",
                {
                    'functions': 1,
                    'parameterized': 1,
                    'cases': None,
                    'minimum': 1,
                    'unknown': 1,
                    'depth': 1,
                    'async': False,
                    'rows': [None],
                },
            ),
            (
                """\
import pytest as pyt

@pyt.mark.parametrize(
    'value',
    [pyt.param(1, id='one'), pyt.param(2), pyt.param(3, id='three')],
)
def test_row_ids(value):
    assert value
""",
                {
                    'functions': 1,
                    'parameterized': 1,
                    'cases': 3,
                    'minimum': 3,
                    'unknown': 0,
                    'depth': 1,
                    'async': False,
                    'rows': [3],
                    'row_ids': ['one', None, 'three'],
                },
            ),
            (
                """\
async def test_async__direct():
    assert True
""",
                {
                    'functions': 1,
                    'parameterized': 0,
                    'cases': 1,
                    'minimum': 1,
                    'unknown': 0,
                    'depth': 2,
                    'async': True,
                    'rows': [],
                },
            ),
        ],
    )
    def test_collection(self, project: ProjectFactory, source: str, expected: dict[str, Any]):
        """Test direct collection and static parametrization arithmetic."""
        tests = project(source)

        report = Worker(tests=tests)()
        summary = report['summary']
        test = report['files'][0]['tests'][0]
        parameterization = test['parameterization']

        assert summary['functions'] == expected['functions']
        assert summary['parameterized_functions'] == expected['parameterized']
        assert summary['cases']['exact'] == expected['cases']
        assert summary['cases']['minimum'] == expected['minimum']
        assert summary['cases']['unknown_functions'] == expected['unknown']
        assert test['name_depth'] == expected['depth']
        assert test['async'] is expected['async']
        assert [item['rows'] for item in parameterization['decorators']] == expected['rows']
        if ids := expected.get('ids'):
            assert parameterization['decorators'][0]['ids']['values'] == ids
        if row_ids := expected.get('row_ids'):
            assert parameterization['decorators'][0]['ids']['row_values'] == row_ids

    @pyt.mark.parametrize(
        'source, code',
        [
            (
                """\
def test_load__json__empty():
    assert True
""",
                'test-name-depth',
            ),
            (
                """\
def test_same():
    assert True

def test_same():
    assert False
""",
                'shadowed-test',
            ),
            (
                """\
def test_outer():
    def test_inner():
        return True
    assert test_inner()
""",
                'nested-test-helper',
            ),
            (
                """\
############
### HEAD ###
############
### EXTERNAL
from pytest import mark

@mark.parametrize('value', [1])
def test_value(value):
    assert value
""",
                'pytest-import-style',
            ),
            (
                """\
############
### HEAD ###
############
### STANDARD
import pytest as pyt

def test_value():
    assert pyt
""",
                'import-section',
            ),
            (
                """\
############
### HEAD ###
############
### EXTERNAL
from pathlib import Path

def test_value():
    assert Path
""",
                'import-section',
            ),
            (
                """\
############
### HEAD ###
############
### EXTERNAL
from pkg import VALUE

def test_value():
    assert VALUE
""",
                'import-section',
            ),
            (
                """\
############
### HEAD ###
############
### INTERNAL
from pkg import VALUE
### STANDARD
from pathlib import Path

def test_value():
    assert VALUE and Path
""",
                'import-section-order',
            ),
            (
                """\
class TestSame:
    def test_first(self):
        assert True

class TestSame:
    def test_second(self):
        assert True
""",
                'shadowed-test-class',
            ),
        ],
    )
    def test_violations(self, project: ProjectFactory, source: str, code: str):
        """Test that only objective collection and layout hazards enter the gate."""
        tests = project(source)

        report = Worker(tests=tests)()

        assert code in {violation['code'] for violation in report['violations']}
        assert main('--tests', str(tests), '--check', '--json', str(tests / 'audit.json')) == 1

    def test_clusters(self, project: ProjectFactory):
        """Test same-stem and literal-normalized candidate grouping."""
        tests = project(
            """\
class TestLoad:
    def test_load__json(self):
        assert load('one') == 'ONE'

    def test_load__yaml(self):
        assert load('two') == 'TWO'
"""
        )

        clusters = Worker(tests=tests)()['clusters']

        assert len(clusters['same_stem']) == 1
        assert clusters['same_stem'][0]['stem'] == 'test_load'
        assert len(clusters['literal_shape']) == 1
        assert [member['name'] for member in clusters['literal_shape'][0]['members']] == [
            'test_load__json',
            'test_load__yaml',
        ]

    def test_imports(self, project: ProjectFactory):
        """Test high-confidence standard, external, and internal import classification."""
        tests = project(
            """\
############
### HEAD ###
############
### STANDARD
from pathlib import Path

### EXTERNAL
import pytest as pyt

### INTERNAL
from pkg import VALUE
from .conftest import helper

############
### BODY ###
############
def test_value():
    assert Path and pyt and VALUE and helper
"""
        )

        report = Worker(tests=tests)()
        imports = report['files'][0]['imports']

        assert [(item['module'], item['classification']) for item in imports] == [
            ('pathlib', 'standard'),
            ('pytest', 'external'),
            ('pkg', 'internal'),
            ('conftest', 'internal'),
        ]
        assert report['violations'] == []

    def test_baseline(self, project: ProjectFactory):
        """Test read-only comparison with a committed Git baseline."""
        tests = project(
            """\
def test_first():
    assert True
"""
        )
        root = tests.parent
        sbp.run(['git', 'init', '-q', str(root)], check=True)
        sbp.run(['git', '-C', str(root), 'add', '.'], check=True)
        sbp.run(
            [
                'git',
                '-C',
                str(root),
                '-c',
                'user.name=Test',
                '-c',
                'user.email=test@example.invalid',
                'commit',
                '-qm',
                'baseline',
            ],
            check=True,
        )
        (tests / 'test_sample.py').write_text(
            """\
def test_first():
    assert True

def test_second():
    assert True
"""
        )

        baseline = Worker(tests=tests, baseline='HEAD')()['baseline']

        assert baseline['available'] is True
        assert len(baseline['revision']) == 40
        assert baseline['summary']['functions'] == 1
        assert baseline['delta']['functions'] == 1

    @pyt.mark.parametrize(
        'source, expected_diagnostic, expected_code',
        [
            ('def test_broken(:\n', 'syntax-error', 0),
            ('def test_plain():\n    assert True\n', None, 0),
            (
                'def test_this_name_is_deliberately_long_but_remains_an_advisory_only_signal():\n'
                '    assert True\n',
                None,
                0,
            ),
        ],
    )
    def test_advisories(
        self,
        project: ProjectFactory,
        source: str,
        expected_diagnostic: str | None,
        expected_code: int,
    ):
        """Test that syntax, long names, and low parametrization remain advisory."""
        tests = project(source)
        output = tests / 'audit.json'

        result = main('--tests', str(tests), '--check', '--json', str(output))
        report = json.loads(output.read_text())

        assert result == expected_code
        assert report['violations'] == []
        assert [item['code'] for item in report['diagnostics']] == (
            [expected_diagnostic] if expected_diagnostic else []
        )

    def test_without_git(self, project: ProjectFactory):
        """Test that a requested baseline degrades clearly outside Git."""
        tests = project('def test_plain():\n    assert True\n')

        baseline = Worker(tests=tests, baseline='HEAD')()['baseline']

        assert baseline['available'] is False
        assert baseline['requested'] == 'HEAD'
        assert 'Git worktree' in baseline['message']


class TestRendering:
    """Test deterministic JSON and Markdown presentation."""

    @pyt.fixture
    def report(self, tmp_path: Path) -> dict[str, Any]:
        """Return a small valid report."""
        tests = tmp_path / 'tests'
        tests.mkdir()
        (tests / 'test_render.py').write_text(
            """\
def test_render():
    assert True
"""
        )
        return Worker(tests=tests)()

    @pyt.mark.parametrize(
        'needle',
        [
            '# PyTest style audit',
            '## Summary',
            '## Baseline',
            'No objective violations.',
            'No repeated same-stem or literal-shape clusters.',
            '`tests/test_render.py`',
        ],
    )
    def test_markdown(self, report: dict[str, Any], needle: str):
        """Test stable narrative sections and no-baseline disclosure."""
        first = render_markdown(report)
        second = render_markdown(report)

        assert first == second
        assert needle in first
