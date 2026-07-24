############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path
import hashlib
import textwrap

### EXTERNAL
import pytest as pyt

### INTERNAL
from my._adoption import scan_repository
from my.scripts.adopt_basis import prepare_repository


############
### DATA ###
############
def make_repository(
    root: Path,
    *,
    python: str | None = 'VALUE = 1\n',
    requires_python: str = '>=3.12',
    dependencies: tuple[str, ...] = (),
) -> Path:
    """Create a minimal Python repository for scanner tests."""
    root.mkdir()
    dependency_text = ', '.join(f'"{value}"' for value in dependencies)
    (root / 'pyproject.toml').write_text(
        textwrap.dedent(
            f"""\
            [project]
            name = "fixture"
            version = "0.1.0"
            requires-python = "{requires_python}"
            dependencies = [{dependency_text}]
            """
        )
    )
    if python is not None:
        package = root / 'fixture'
        package.mkdir()
        (package / '__init__.py').write_text(python)
    return root


############
### BODY ###
############
class TestScanRepository:
    # ------------------
    # `*` Public Methods
    # ------------------
    @pyt.mark.parametrize(
        'source',
        [
            'raise RuntimeError("target code was imported")\n',
            'import re\nPATTERN = re.compile(r"hello")\n',
        ],
    )
    def test_scan_repository__deterministic(self, tmp_path: Path, source: str):
        """Test scans are deterministic, non-importing, and artifact-independent."""
        root = make_repository(tmp_path / 'repo', python=source)
        source_path = root / 'fixture' / '__init__.py'
        before = source_path.read_bytes()

        first = scan_repository(root)
        prepare_repository(root)
        second = scan_repository(root)

        assert first.model_dump() == second.model_dump()
        assert source_path.read_bytes() == before
        assert sorted(path.name for path in (root / '.basis-adoption').iterdir()) == [
            'agent-prompt.md',
            'context.json',
            'intake.json',
            'proposal.template.json',
        ]

    def test_scan_repository__stable_bytes(
        self,
        tmp_path: Path,
        monkeypatch: pyt.MonkeyPatch,
    ):
        """Test evidence hashes and derived facts use the same source bytes."""
        root = make_repository(tmp_path / 'repo')
        source = root / 'fixture' / '__init__.py'
        before = source.read_bytes()
        after = b'import re\nVALUE = re.search(r"changed", "changed")\n'
        original = Path.read_bytes
        changed = False

        def read_bytes(path: Path) -> bytes:
            nonlocal changed
            data = original(path)
            if path == source and not changed:
                changed = True
                source.write_bytes(after)
            return data

        monkeypatch.setattr(Path, 'read_bytes', read_bytes)

        intake = scan_repository(root)
        evidence = next(item for item in intake.evidence if item.path == 'fixture/__init__.py')

        assert source.read_bytes() == after
        assert evidence.sha256 == hashlib.sha256(before).hexdigest()
        assert intake.regex['calls'] == 0

    @pyt.mark.parametrize(
        'python, requires_python, dependencies, expected_status, expected_signal',
        [
            ('VALUE = 1\n', '>=3.11', (), 'defer', 'adoption.python-floor'),
            ('VALUE = 1\n', '>=3.12', ('my-basis>=1.0',), 'no-op', 'basis.present'),
            ('VALUE = 1\n', '>=3.12', (), 'review', 'adoption.review'),
            (None, '>=3.12', (), 'no-op', 'adoption.no-python'),
        ],
    )
    def test_scan_repository__disposition(
        self,
        tmp_path: Path,
        python: str | None,
        requires_python: str,
        dependencies: tuple[str, ...],
        expected_status: str,
        expected_signal: str,
    ):
        """Test Python floors, existing adoption, candidates, and no-op repositories."""
        root = make_repository(
            tmp_path / 'repo',
            python=python,
            requires_python=requires_python,
            dependencies=dependencies,
        )

        intake = scan_repository(root)

        signal_ids = {signal.id for signal in intake.signals}
        assert intake.disposition['status'] == expected_status
        assert expected_signal in signal_ids
        assert 'detector.scope' in signal_ids
        assert ('adoption.zero-runtime-dependencies' in signal_ids) is not dependencies

    @pyt.mark.parametrize(
        'metadata, lockfile, workflow, expected_manager, expected_command',
        [
            (
                '[project.scripts]\nfixture = "fixture:main"\n',
                'uv.lock',
                'version: "3"\ntasks:\n    test:\n        cmd: uv run pytest\n',
                'uv',
                'task test',
            ),
            (
                '[tool.poetry.dependencies]\npython = ">=3.12"\n',
                'poetry.lock',
                'check:\n\tpython -m pytest\n',
                'poetry',
                'make check',
            ),
        ],
    )
    def test_scan_repository__workflow(
        self,
        tmp_path: Path,
        metadata: str,
        lockfile: str,
        workflow: str,
        expected_manager: str,
        expected_command: str,
    ):
        """Test package-manager and native workflow discovery."""
        root = make_repository(tmp_path / 'repo')
        with (root / 'pyproject.toml').open('a') as stream:
            stream.write(metadata)
        (root / lockfile).write_text('')
        if expected_command.startswith('task'):
            (root / 'Taskfile.yaml').write_text(workflow)
        else:
            (root / 'Makefile').write_text(workflow)

        intake = scan_repository(root)

        managers = intake.dependency['managers']
        assert isinstance(managers, list)
        assert expected_manager in managers
        assert expected_command in intake.commands['candidate_native_gates']

    @pyt.mark.parametrize(
        'declaration',
        [
            'git+https://gitlab.com/doering-ai/libs/basis.git@v1.0.0#egg=my-basis\n',
            '-e git+https://gitlab.com/doering-ai/libs/basis.git@main#egg=my-basis\n',
            'git+https://example.test/my-basis.git@v1#egg=my-basis\n',
            '-e git+ssh://example.test/tools/my_basis.git@main#egg=my_basis\n',
        ],
    )
    def test_scan_repository__requirements(self, tmp_path: Path, declaration: str):
        """Test direct and editable VCS requirements count as my-basis declarations."""
        root = make_repository(tmp_path / 'repo')
        (root / 'requirements.txt').write_text(declaration)

        intake = scan_repository(root)

        assert intake.dependency['my_basis_present'] is True
        expected = declaration.strip().removeprefix('-e ')
        assert intake.dependency['my_basis_declarations'] == [expected]

    @pyt.mark.parametrize(
        'source, expected_calls, expected_complex, expected_dynamic, signal',
        [
            (
                'import re\nVALUE = re.search(r"hello", "hello")\n',
                1,
                0,
                0,
                None,
            ),
            (
                'import regex as rx\nVALUE = rx.compile(r"(?P<word>\\p{L}+)(?P>word)")\n',
                1,
                1,
                0,
                'regexstore.complex-patterns',
            ),
            (
                'import re\nPATTERN = "x"\nVALUE = re.compile(PATTERN)\n',
                1,
                0,
                1,
                None,
            ),
            (
                'from regex import compile as make\nVALUE = make(r"(?P<word>\\p{L}+)(?P>word)")\n',
                1,
                1,
                0,
                'regexstore.complex-patterns',
            ),
        ],
    )
    def test_scan_repository__regex(
        self,
        tmp_path: Path,
        source: str,
        expected_calls: int,
        expected_complex: int,
        expected_dynamic: int,
        signal: str | None,
    ):
        """Test static regex inventory and complex-pattern signaling."""
        root = make_repository(tmp_path / 'repo', python=source)

        intake = scan_repository(root)

        assert intake.regex['calls'] == expected_calls
        assert intake.regex['production_calls'] == expected_calls
        assert intake.regex['test_calls'] == 0
        assert intake.regex['complex_calls'] == expected_complex
        assert intake.regex['dynamic_calls'] == expected_dynamic
        if signal:
            detected = next(item for item in intake.signals if item.id == signal)
            assert 'merit inspection' in detected.summary
            assert 'DSL example' not in detected.summary

    @pyt.mark.parametrize(
        'layout, requires_python, dependencies, expected_status, expected_signal, absent_signal',
        [
            ('test-only', '>=3.12', (), 'review', 'detector.scope', 'regexstore.consolidation'),
            (
                'unrelated',
                '>=3.12',
                ('my-basis>=1.0',),
                'no-op',
                'adoption.already-present',
                'regexstore.consolidation',
            ),
            (
                'clustered',
                '>=3.12',
                (),
                'review',
                'regexstore.consolidation',
                '',
            ),
            (
                'defer',
                '>=3.11',
                (),
                'defer',
                'adoption.python-floor',
                'regexstore.consolidation',
            ),
        ],
    )
    def test_scan_repository__opportunity_scope(
        self,
        tmp_path: Path,
        layout: str,
        requires_python: str,
        dependencies: tuple[str, ...],
        expected_status: str,
        expected_signal: str,
        absent_signal: str,
    ):
        """Test regex leads respect source clusters, test scope, and hard constraints."""
        root = make_repository(
            tmp_path / 'repo',
            requires_python=requires_python,
            dependencies=dependencies,
        )
        calls = (
            'import re\nA=re.search(r"a", "a")\nB=re.search(r"b", "b")\nC=re.search(r"c", "c")\n'
        )
        if layout == 'test-only':
            tests = root / 'tests'
            tests.mkdir()
            (tests / 'test_patterns.py').write_text(calls)
        elif layout == 'unrelated':
            for index in range(3):
                (root / f'module{index}.py').write_text(
                    f'import re\nVALUE = re.search(r"{index}", "{index}")\n'
                )
        else:
            (root / 'fixture' / '__init__.py').write_text(calls)

        intake = scan_repository(root)
        signal_ids = {item.id for item in intake.signals}

        assert intake.disposition['status'] == expected_status
        assert expected_signal in signal_ids
        if absent_signal:
            assert absent_signal not in signal_ids
        if layout == 'test-only':
            assert intake.regex['production_calls'] == 0
            assert intake.regex['test_calls'] == 3

    def test_scan_repository__sublime_host(self, tmp_path: Path):
        """Test Sublime host markers and copied myBasis seams become explicit evidence."""
        root = make_repository(
            tmp_path / 'repo',
            python='import sublime\nfrom myBasis import ut\nVALUE = ut.fn.identity(1)\n',
            requires_python='>=3.13',
        )
        (root / '.python-version').write_text('3.14\n')
        copied = root / 'myBasis'
        copied.mkdir()
        (copied / '__init__.py').write_text('from .infra import utils as ut\n')
        (copied / 'infra.py').write_text('class utils:\n    pass\n')

        intake = scan_repository(root)

        assert intake.schema_version == 2
        assert intake.sublime == {
            'detected': True,
            'host_python': '3.14',
            'imports': ['fixture/__init__.py'],
            'mybasis_imports': ['fixture/__init__.py'],
            'copied_mybasis_files': ['myBasis/__init__.py', 'myBasis/infra.py'],
        }
        signal_ids = {item.id for item in intake.signals}
        assert {'sublime.host', 'sublime.copied-mybasis'} <= signal_ids

    def test_scan_repository__regexstore_evidence(self, tmp_path: Path):
        """Test existing RegexStore idioms include exact source evidence paths."""
        root = make_repository(
            tmp_path / 'repo',
            python='from my import RegexStore\nSTORE = RegexStore()\n',
            dependencies=('my-basis>=1.0',),
        )

        intake = scan_repository(root)
        signal = next(item for item in intake.signals if item.id == 'regexstore.present')

        assert signal.evidence == ['fixture/__init__.py']

    def test_scan_repository__exclusions(self, tmp_path: Path):
        """Test secrets, generated trees, virtualenvs, and external links are excluded."""
        root = make_repository(tmp_path / 'repo')
        (root / '.env').write_text('SECRET=do-not-read\n')
        (root / 'api_token.py').write_text('TOKEN = "ordinary source"\n')
        (root / 'tokenizer.py').write_text('TOKENS = ["safe source"]\n')
        tokens = root / 'tokens'
        tokens.mkdir()
        (tokens / 'credentials.py').write_text('FIELDS = ["username"]\n')
        (root / 'oversized.py').write_text('X = "' + 'x' * 2_000_000 + '"\n')
        (root / '.venv').mkdir()
        (root / '.venv' / 'installed.py').write_text('import unwanted\n')
        (root / 'generated').mkdir()
        (root / 'generated' / 'model.py').write_text('import unwanted\n')
        (root / 'vendor').mkdir()
        (root / 'vendor' / 'library.py').write_text('import unwanted\n')
        external = tmp_path / 'external.py'
        external.write_text('import unwanted\n')
        (root / 'linked.py').symlink_to(external)

        intake = scan_repository(root)
        paths = {item.path for item in intake.evidence}

        assert not paths & {
            '.env',
            '.venv/installed.py',
            'generated/model.py',
            'linked.py',
            'oversized.py',
            'vendor/library.py',
        }
        assert {'api_token.py', 'tokenizer.py', 'tokens/credentials.py'} <= paths
        assert intake.exclusions['secrets'] == 1
        assert intake.exclusions['external_symlinks'] == 1
        assert intake.exclusions['directories'] >= 2
        assert intake.exclusions['generated'] == 1
        assert intake.exclusions['oversized'] == 1

    @pyt.mark.parametrize(
        'source, expected_module',
        [
            ('import collections\n', 'collections'),
            ('from pathlib import Path\n', 'pathlib'),
            ('from .local import VALUE\n', '.'),
        ],
    )
    def test_scan_repository__imports(
        self,
        tmp_path: Path,
        source: str,
        expected_module: str,
    ):
        """Test import inventory is normalized to top-level modules."""
        root = make_repository(tmp_path / 'repo', python=source)

        intake = scan_repository(root)

        assert expected_module in {item.module for item in intake.imports}
