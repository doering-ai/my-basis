############
### HEAD ###
############
"""Verify the Python release artifacts keep the Python/Typst boundary intact.

The checker reads, but never extracts, one or more wheels and source distributions. It removes
the conventional source-distribution package root before comparing archive members, rejects a
top-level ``typst/`` tree, and requires every source-controlled file in the packaged
``adopt-my-basis`` skill.

Deliberately depends only on the standard library so it remains usable while the package itself
is being built or repaired.
"""

### STANDARD
from __future__ import annotations
import argparse as ap
import stat
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath


############
### DATA ###
############
#: Repository root used when the script is run from its checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: Source and artifact location of the packaged agent skill.
SKILL_ROOT = PurePosixPath('my/skills/adopt-my-basis')

#: Generated source-tree entries that are not part of the skill's package contract.
IGNORED_SKILL_PARTS = frozenset({'__pycache__'})


class ArtifactKind(StrEnum):
    """Supported Python release artifact formats."""

    WHEEL = 'wheel'
    SDIST = 'sdist'


@dataclass(frozen=True)
class ArchiveMember:
    """One safe, normalized archive member."""

    path: PurePosixPath
    regular_file: bool


@dataclass(frozen=True)
class ArtifactReport:
    """Successful verification details for one artifact."""

    path: Path
    kind: ArtifactKind
    members: int
    skill_files: int


class ArtifactCheckError(RuntimeError):
    """Raised when release artifacts violate the package boundary."""


############
### BODY ###
############
@dataclass(frozen=True)
class Worker:
    """Check built Python artifacts against the repository's release boundary."""

    artifacts: tuple[Path, ...]
    project_root: Path = PROJECT_ROOT

    # -------------------
    # `-` Private Methods
    # -------------------
    @staticmethod
    def _kind(path: Path) -> ArtifactKind:
        """Return the artifact kind encoded by a release filename."""
        if path.suffix == '.whl':
            return ArtifactKind.WHEEL
        if path.name.endswith(('.tar.gz', '.tgz')):
            return ArtifactKind.SDIST
        raise ArtifactCheckError(
            f'unsupported artifact format: {path} (expected .whl, .tar.gz, or .tgz)'
        )

    @staticmethod
    def _member_path(name: str) -> PurePosixPath | None:
        """Normalize one POSIX archive path without permitting traversal ambiguity."""
        if not name or name == '.':
            return None
        if '\x00' in name:
            raise ArtifactCheckError('archive member contains a NUL byte')
        if '\\' in name:
            raise ArtifactCheckError(f'archive member uses a backslash path: {name!r}')

        path = PurePosixPath(name)
        if path.is_absolute():
            raise ArtifactCheckError(f'archive member is absolute: {name!r}')
        if '..' in path.parts:
            raise ArtifactCheckError(f'archive member traverses a parent directory: {name!r}')
        if not path.parts:
            return None
        return path

    @classmethod
    def _wheel_members(cls, path: Path) -> tuple[ArchiveMember, ...]:
        """Read normalized wheel members without extracting the archive."""
        try:
            with zipfile.ZipFile(path) as archive:
                members: list[ArchiveMember] = []
                for info in archive.infolist():
                    member_path = cls._member_path(info.filename)
                    if member_path is None:
                        continue
                    mode = info.external_attr >> 16
                    members.append(
                        ArchiveMember(
                            path=member_path,
                            regular_file=not info.is_dir() and not stat.S_ISLNK(mode),
                        )
                    )
        except (OSError, zipfile.BadZipFile) as error:
            raise ArtifactCheckError(f'cannot read wheel {path}: {error}') from error
        return tuple(members)

    @classmethod
    def _sdist_members(cls, path: Path) -> tuple[ArchiveMember, ...]:
        """Read source-distribution members and remove their single package-root prefix."""
        try:
            with tarfile.open(path, mode='r:*') as archive:
                raw: list[ArchiveMember] = []
                for info in archive.getmembers():
                    member_path = cls._member_path(info.name)
                    if member_path is not None:
                        raw.append(ArchiveMember(path=member_path, regular_file=info.isfile()))
        except (OSError, tarfile.TarError) as error:
            raise ArtifactCheckError(f'cannot read source distribution {path}: {error}') from error

        roots = sorted({member.path.parts[0] for member in raw})
        if len(roots) != 1:
            rendered = ', '.join(roots) if roots else '<none>'
            raise ArtifactCheckError(
                f'source distribution {path} must contain one package-root directory; '
                f'found: {rendered}'
            )

        root = roots[0]
        members: list[ArchiveMember] = []
        for member in raw:
            relative = PurePosixPath(*member.path.parts[1:])
            if not relative.parts:
                if member.regular_file:
                    raise ArtifactCheckError(
                        f'source distribution {path} uses its package root as a file: {root!r}'
                    )
                continue
            members.append(ArchiveMember(path=relative, regular_file=member.regular_file))
        return tuple(members)

    def _expected_skill_files(self) -> frozenset[PurePosixPath]:
        """Derive the complete packaged-skill contract from clean source files."""
        source = self.project_root / Path(*SKILL_ROOT.parts)
        if not source.is_dir():
            raise ArtifactCheckError(f'packaged skill source directory is missing: {source}')
        if not (source / 'SKILL.md').is_file():
            raise ArtifactCheckError(f'packaged skill entrypoint is missing: {source / "SKILL.md"}')

        expected: set[PurePosixPath] = set()
        for path in sorted(source.rglob('*')):
            relative = path.relative_to(source)
            if any(part.startswith('.') or part in IGNORED_SKILL_PARTS for part in relative.parts):
                continue
            if path.is_symlink():
                raise ArtifactCheckError(f'packaged skill source must not contain symlinks: {path}')
            if path.is_file() and path.suffix != '.pyc':
                expected.add(SKILL_ROOT / PurePosixPath(*relative.parts))

        if SKILL_ROOT / 'SKILL.md' not in expected:
            raise ArtifactCheckError(f'packaged skill entrypoint is not a regular file: {source}')
        return frozenset(expected)

    @staticmethod
    def _check_member_paths(
        path: Path,
        kind: ArtifactKind,
        members: tuple[ArchiveMember, ...],
        expected_skill: frozenset[PurePosixPath],
    ) -> ArtifactReport:
        """Check one normalized member inventory and return its success report."""
        problems: list[str] = []
        forbidden = sorted(
            str(member.path)
            for member in members
            if member.path.parts and member.path.parts[0] == 'typst'
        )
        if forbidden:
            problems.append(
                'contains the independently released top-level typst/ tree: ' + ', '.join(forbidden)
            )

        regular_files = {member.path for member in members if member.regular_file}
        missing = sorted(str(expected) for expected in expected_skill - regular_files)
        if missing:
            problems.append('missing packaged adopt-my-basis skill files: ' + ', '.join(missing))

        if problems:
            detail = '\n'.join(f'  - {problem}' for problem in problems)
            raise ArtifactCheckError(f'{path} ({kind.value}) failed:\n{detail}')
        return ArtifactReport(
            path=path,
            kind=kind,
            members=len(members),
            skill_files=len(expected_skill),
        )

    # ------------------
    # `*` Public Methods
    # ------------------
    def __call__(self) -> tuple[ArtifactReport, ...]:
        """Verify every artifact and require both wheel and source-distribution coverage."""
        expected_skill = self._expected_skill_files()
        reports: list[ArtifactReport] = []
        problems: list[str] = []
        kinds: set[ArtifactKind] = set()

        for raw_path in self.artifacts:
            path = raw_path.expanduser()
            try:
                kind = self._kind(path)
                kinds.add(kind)
                if not path.is_file():
                    raise ArtifactCheckError(f'artifact does not exist or is not a file: {path}')
                if kind is ArtifactKind.WHEEL:
                    members = self._wheel_members(path)
                else:
                    members = self._sdist_members(path)
                reports.append(self._check_member_paths(path, kind, members, expected_skill))
            except ArtifactCheckError as error:
                problems.append(str(error))

        problems.extend(
            f'no {required.value} artifact supplied'
            for required in ArtifactKind
            if required not in kinds
        )

        if problems:
            raise ArtifactCheckError('\n'.join(problems))
        return tuple(reports)


############
### MAIN ###
############
def _cli(*vargs: str) -> ap.Namespace:
    """Parse release-artifact checker arguments."""
    parser = ap.ArgumentParser(
        description=(
            'Check wheel and sdist contents for the Python/Typst boundary and packaged skill.'
        )
    )
    parser.add_argument(
        'artifacts',
        type=Path,
        nargs='+',
        metavar='ARTIFACT',
        help='built wheel or source distribution to inspect (supply at least one of each)',
    )
    parser.add_argument(
        '--project-root',
        type=Path,
        default=PROJECT_ROOT,
        help='source checkout used to derive the packaged skill file contract',
    )
    return parser.parse_args(vargs or None)


def main(*vargs: str) -> int:
    """Check release artifacts and return a shell-friendly status code."""
    args = _cli(*vargs)
    print('[check_release_artifacts]')
    try:
        reports = Worker(
            artifacts=tuple(args.artifacts),
            project_root=args.project_root.expanduser(),
        )()
    except ArtifactCheckError as error:
        print(f'  error : {error}', file=sys.stderr)
        return 1

    for report in reports:
        print(
            f'  {report.kind.value:<6}: {report.path} '
            f'({report.members} members; {report.skill_files} skill files)'
        )
    print(f'  result: ok ({len(reports)} artifacts)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
