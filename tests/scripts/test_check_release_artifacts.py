############
### HEAD ###
############
### STANDARD
from __future__ import annotations
import io
import tarfile
import zipfile
from pathlib import Path

### EXTERNAL
import pytest as pyt

### INTERNAL
from scripts.check_release_artifacts import ArtifactCheckError, ArtifactKind, Worker, main


############
### DATA ###
############
SKILL_FILES = (
    'SKILL.md',
    'agents/openai.yaml',
    'assets/report.md.jinja',
    'assets/report.typ.jinja',
    'references/regexstore.md',
)


############
### BODY ###
############
def _create_project(tmp_path: Path) -> Path:
    """Create a source checkout containing one representative packaged skill."""
    root = tmp_path / 'project'
    skill = root / 'my' / 'skills' / 'adopt-my-basis'
    for name in SKILL_FILES:
        path = skill / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'{name}\n')
    return root


def _skill_members() -> dict[str, bytes]:
    """Return archive members for the representative packaged skill."""
    return {f'my/skills/adopt-my-basis/{name}': f'{name}\n'.encode() for name in SKILL_FILES}


def _write_wheel(path: Path, members: dict[str, bytes]) -> None:
    """Write one synthetic wheel ZIP with the requested members."""
    with zipfile.ZipFile(path, mode='w') as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def _write_sdist(path: Path, members: dict[str, bytes], root: str = 'my_basis-1.0.0') -> None:
    """Write one synthetic source distribution with a conventional package root."""
    with tarfile.open(path, mode='w:gz') as archive:
        for name, content in members.items():
            archive_name = name if name.startswith('/') else f'{root}/{name}'
            info = tarfile.TarInfo(archive_name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))


def _write_pair(
    tmp_path: Path,
    wheel_members: dict[str, bytes] | None = None,
    sdist_members: dict[str, bytes] | None = None,
) -> tuple[Path, Path]:
    """Write a wheel/sdist pair, using the complete skill inventory by default."""
    wheel = tmp_path / 'my_basis-1.0.0-py3-none-any.whl'
    sdist = tmp_path / 'my_basis-1.0.0.tar.gz'
    _write_wheel(wheel, _skill_members() if wheel_members is None else wheel_members)
    _write_sdist(sdist, _skill_members() if sdist_members is None else sdist_members)
    return wheel, sdist


class TestWorker:
    """Test deterministic artifact inventory and boundary validation."""

    # -------------------
    # `+` Primary Methods
    # -------------------
    @pyt.mark.parametrize(
        'sdist_root',
        [
            'my_basis-1.0.0',
            'my-basis-1.0.0',
            'release',
        ],
    )
    def test_check__valid(self, tmp_path: Path, sdist_root: str):
        """Valid artifacts retain all skill files after sdist-root normalization."""
        project = _create_project(tmp_path)
        wheel = tmp_path / 'my_basis-1.0.0-py3-none-any.whl'
        sdist = tmp_path / 'my_basis-1.0.0.tar.gz'
        _write_wheel(wheel, _skill_members())
        _write_sdist(sdist, _skill_members(), root=sdist_root)

        reports = Worker(artifacts=(wheel, sdist), project_root=project)()

        assert [report.kind for report in reports] == [ArtifactKind.WHEEL, ArtifactKind.SDIST]
        assert all(report.skill_files == len(SKILL_FILES) for report in reports)
        assert all(report.members == len(SKILL_FILES) for report in reports)

    @pyt.mark.parametrize('kind', ArtifactKind)
    def test_check__rejects_typst(self, tmp_path: Path, kind: ArtifactKind):
        """Either artifact format fails when the independent Typst tree leaks in."""
        project = _create_project(tmp_path)
        members = _skill_members() | {'typst/src/lib.typ': b'#let value = 1\n'}
        wheel_members = members if kind is ArtifactKind.WHEEL else None
        sdist_members = members if kind is ArtifactKind.SDIST else None
        wheel, sdist = _write_pair(tmp_path, wheel_members, sdist_members)

        with pyt.raises(ArtifactCheckError, match=r'top-level typst/ tree'):
            Worker(artifacts=(wheel, sdist), project_root=project)()

    @pyt.mark.parametrize('kind', ArtifactKind)
    @pyt.mark.parametrize('missing', SKILL_FILES)
    def test_check__requires_skill(
        self,
        tmp_path: Path,
        kind: ArtifactKind,
        missing: str,
    ):
        """Every clean source file below the skill root is required in each artifact."""
        project = _create_project(tmp_path)
        missing_path = f'my/skills/adopt-my-basis/{missing}'
        members = _skill_members()
        del members[missing_path]
        wheel_members = members if kind is ArtifactKind.WHEEL else None
        sdist_members = members if kind is ArtifactKind.SDIST else None
        wheel, sdist = _write_pair(tmp_path, wheel_members, sdist_members)

        with pyt.raises(ArtifactCheckError, match=missing_path):
            Worker(artifacts=(wheel, sdist), project_root=project)()

    @pyt.mark.parametrize(
        'kind, unsafe, message',
        [
            (ArtifactKind.WHEEL, '../escape', 'traverses a parent'),
            (ArtifactKind.WHEEL, '/absolute', 'is absolute'),
            (ArtifactKind.WHEEL, r'bad\\path', 'backslash path'),
            (ArtifactKind.SDIST, '../escape', 'traverses a parent'),
            (ArtifactKind.SDIST, '/absolute', 'is absolute'),
            (ArtifactKind.SDIST, r'bad\\path', 'backslash path'),
        ],
    )
    def test_check__rejects_unsafe(
        self,
        tmp_path: Path,
        kind: ArtifactKind,
        unsafe: str,
        message: str,
    ):
        """Ambiguous or escaping archive paths fail before inventory comparison."""
        project = _create_project(tmp_path)
        wheel, sdist = _write_pair(tmp_path)
        if kind is ArtifactKind.WHEEL:
            members = _skill_members() | {unsafe: b'unsafe\n'}
            _write_wheel(wheel, members)
        else:
            members = _skill_members() | {unsafe: b'unsafe\n'}
            _write_sdist(sdist, members)

        with pyt.raises(ArtifactCheckError, match=message):
            Worker(artifacts=(wheel, sdist), project_root=project)()

    @pyt.mark.parametrize(
        'present, missing',
        [
            (ArtifactKind.WHEEL, ArtifactKind.SDIST),
            (ArtifactKind.SDIST, ArtifactKind.WHEEL),
        ],
    )
    def test_check__requires_formats(
        self,
        tmp_path: Path,
        present: ArtifactKind,
        missing: ArtifactKind,
    ):
        """A release check cannot pass without both distribution formats."""
        project = _create_project(tmp_path)
        wheel, sdist = _write_pair(tmp_path)
        artifact = wheel if present is ArtifactKind.WHEEL else sdist

        with pyt.raises(ArtifactCheckError, match=rf'no {missing.value} artifact supplied'):
            Worker(artifacts=(artifact,), project_root=project)()

    @pyt.mark.parametrize(
        'kind, filename, message',
        [
            (ArtifactKind.WHEEL, 'broken.whl', 'cannot read wheel'),
            (ArtifactKind.SDIST, 'broken.tar.gz', 'cannot read source distribution'),
        ],
    )
    def test_check__rejects_corrupt(
        self,
        tmp_path: Path,
        kind: ArtifactKind,
        filename: str,
        message: str,
    ):
        """Corrupt release containers produce artifact-specific diagnostics."""
        project = _create_project(tmp_path)
        wheel, sdist = _write_pair(tmp_path)
        broken = tmp_path / filename
        broken.write_bytes(b'not an archive')
        artifacts = (broken, sdist) if kind is ArtifactKind.WHEEL else (wheel, broken)

        with pyt.raises(ArtifactCheckError, match=message):
            Worker(artifacts=artifacts, project_root=project)()

    def test_check__ignores_generated(self, tmp_path: Path):
        """Generated cache and hidden files do not expand the package contract."""
        project = _create_project(tmp_path)
        skill = project / 'my' / 'skills' / 'adopt-my-basis'
        cache = skill / '__pycache__' / 'helper.pyc'
        cache.parent.mkdir()
        cache.write_bytes(b'generated')
        (skill / '.editor-state').write_text('generated\n')
        wheel, sdist = _write_pair(tmp_path)

        reports = Worker(artifacts=(wheel, sdist), project_root=project)()

        assert all(report.skill_files == len(SKILL_FILES) for report in reports)

    def test_check__rejects_source_symlink(self, tmp_path: Path):
        """A packaged skill contract cannot silently follow source-tree symlinks."""
        project = _create_project(tmp_path)
        skill = project / 'my' / 'skills' / 'adopt-my-basis'
        (skill / 'linked.md').symlink_to(skill / 'SKILL.md')
        wheel, sdist = _write_pair(tmp_path)

        with pyt.raises(ArtifactCheckError, match='must not contain symlinks'):
            Worker(artifacts=(wheel, sdist), project_root=project)()

    @pyt.mark.parametrize('filename', ['artifact.zip', 'artifact.tar', 'README.md'])
    def test_check__rejects_format(self, tmp_path: Path, filename: str):
        """Unsupported containers fail with the accepted suffixes in the diagnostic."""
        project = _create_project(tmp_path)
        artifact = tmp_path / filename
        artifact.write_bytes(b'unsupported')

        with pyt.raises(ArtifactCheckError, match=r'expected .whl, .tar.gz, or .tgz'):
            Worker(artifacts=(artifact,), project_root=project)()


class TestMain:
    """Test the shell-facing release gate."""

    # ------------------
    # `*` Public Methods
    # ------------------
    def test_main__success(self, tmp_path: Path, capsys: pyt.CaptureFixture[str]):
        """A valid pair produces concise format-level evidence on stdout."""
        project = _create_project(tmp_path)
        wheel, sdist = _write_pair(tmp_path)

        result = main(str(wheel), str(sdist), '--project-root', str(project))
        captured = capsys.readouterr()

        assert result == 0
        assert captured.err == ''
        assert '[check_release_artifacts]' in captured.out
        assert 'wheel ' in captured.out
        assert 'sdist ' in captured.out
        assert 'result: ok (2 artifacts)' in captured.out

    def test_main__failure(self, tmp_path: Path, capsys: pyt.CaptureFixture[str]):
        """A boundary violation returns nonzero and explains the failed path on stderr."""
        project = _create_project(tmp_path)
        wheel, sdist = _write_pair(
            tmp_path,
            wheel_members=_skill_members() | {'typst/src/lib.typ': b'forbidden\n'},
        )

        result = main(str(wheel), str(sdist), '--project-root', str(project))
        captured = capsys.readouterr()

        assert result == 1
        assert captured.out == '[check_release_artifacts]\n'
        assert 'error :' in captured.err
        assert 'top-level typst/ tree' in captured.err
