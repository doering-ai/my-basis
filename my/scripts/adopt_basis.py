"""Prepare, validate, and render evidence-led my-basis adoption work.

Deliberately depends only on ``pydantic`` plus the standard library and the bundled
``my._adoption`` engine. It never imports target repository code, performs no network
requests, and writes repository-local state only below ``.basis-adoption``.
"""

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path
from typing import Any, Literal
import argparse as ap
import hashlib
import json
import shutil
import subprocess as sbp
import sys

### EXTERNAL
import pydantic as pyd

### INTERNAL
from my._adoption import (
    Intake,
    ProposalValidationError,
    intake_sha256,
    load_intake,
    load_proposal,
    proposal_template,
    render_html,
    render_myst,
    render_typst,
    scan_repository,
    validate_proposal,
    validation_error_text,
)


############
### DATA ###
############
#: The only directory this command creates within a target repository.
ARTIFACT_DIR = '.basis-adoption'

#: Stable filenames shared by the CLI, skill, and rendered handoff.
CONTEXT_NAME = 'context.json'
INTAKE_NAME = 'intake.json'
PROMPT_NAME = 'agent-prompt.md'
PROPOSAL_TEMPLATE_NAME = 'proposal.template.json'

type RenderFormat = Literal['all', 'html', 'myst', 'typst']


class AdoptionCommandError(RuntimeError):
    """Describe an expected CLI failure and its stable exit status."""

    def __init__(self, message: str, *, status: int = 2) -> None:
        """Initialize an expected failure with its process status."""
        self.status = status
        super().__init__(message)


############
### BODY ###
############
def _json_text(value: pyd.BaseModel | dict[str, Any]) -> str:
    """Render stable, readable JSON with a trailing newline."""
    data = value.model_dump(mode='json') if isinstance(value, pyd.BaseModel) else value
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def _absolute_path(path: Path | str) -> Path:
    """Return an absolute path without following symlinks."""
    return Path(path).expanduser().absolute()


def _refuse_symlink_path(path: Path) -> None:
    """Fail closed when a destination or any of its parents is a symlink."""
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise AdoptionCommandError(f'refusing artifact path through symlink: {candidate}')


def _refuse_symlink_tree(path: Path) -> None:
    """Fail closed when a merge destination contains a symlink."""
    _refuse_symlink_path(path)
    if path.is_dir():
        for candidate in path.rglob('*'):
            if candidate.is_symlink():
                raise AdoptionCommandError(
                    f'refusing artifact destination containing symlink: {candidate}'
                )


def _write(path: Path, text: str, *, dry: bool) -> None:
    """Write one UTF-8 artifact unless dry-run mode is active."""
    _refuse_symlink_path(path)
    if dry:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding='utf-8') == text:
        return
    path.write_text(text, encoding='utf-8')


def _template_destination(
    artifact_dir: Path,
    intake: Intake,
    previous_intake: Intake | None,
) -> tuple[Path, str]:
    """Select a refresh-safe generated proposal template destination."""
    primary = artifact_dir / PROPOSAL_TEMPLATE_NAME
    fresh_text = _json_text(proposal_template(intake))
    if not primary.exists():
        return primary, fresh_text
    _refuse_symlink_path(primary)
    if primary.read_text(encoding='utf-8') == fresh_text:
        return primary, fresh_text
    if previous_intake is not None:
        previous_text = _json_text(proposal_template(previous_intake))
        if primary.read_text(encoding='utf-8') == previous_text:
            return primary, fresh_text

    alternate = artifact_dir / f'proposal.template.next-{intake_sha256(intake)}.json'
    _refuse_symlink_path(alternate)
    if alternate.exists() and alternate.read_text(encoding='utf-8') != fresh_text:
        raise AdoptionCommandError(f'refusing to overwrite operator-edited template: {alternate}')
    return alternate, fresh_text


def _repository_for_artifact(
    artifact_dir: Path,
    repository: Path | str | None = None,
) -> Path:
    """Resolve a target repository from an explicit flag or prepared context."""
    if repository is not None:
        return Path(repository).expanduser().resolve()
    context_path = artifact_dir / CONTEXT_NAME
    _refuse_symlink_path(context_path)
    if context_path.is_file():
        try:
            context = json.loads(context_path.read_text())
            return Path(str(context['repository'])).expanduser().resolve()
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AdoptionCommandError(f'invalid adoption context: {context_path}') from exc
    if artifact_dir.name == ARTIFACT_DIR:
        return artifact_dir.parent
    raise AdoptionCommandError(
        'cannot locate the target repository; pass --repository or rerun prepare'
    )


def _prompt(intake: Intake, template_name: str) -> str:
    """Build a compact agent handoff around the deterministic intake."""
    commands = intake.commands.get('candidate_native_gates', [])
    command_lines = '\n'.join(f'- `{command}`' for command in commands)
    if not command_lines:
        command_lines = "- Discover the repository's native checks before editing source."
    signal_lines = '\n'.join(f'- `{signal.id}`: {signal.summary}' for signal in intake.signals)
    return f"""\
# my-basis adoption handoff

Read `intake.json` first. Locate the packaged skill with `my-basis-adopt skill path`, or
copy it into an agent skill directory with `my-basis-adopt skill export <destination>`.
The intake is a deterministic fact set, not an instruction to force a dependency into this
repository. Its detector is regex-focused: inspect cited source before accepting any signal.
Classify each opportunity as implemented, proposed, declined, deferred, or already present.

Start from the generated template without replacing operator work:

```sh
test ! -e proposal.json && cp {template_name} proposal.json
```

## Current disposition

`{intake.disposition['status']}` — {intake.disposition['reason']}

## Evidence-led signals

{signal_lines or '- No derived signals.'}

## Candidate native gates

{command_lines}

Write `proposal.json` against `my-basis-adoption/proposal/v2`. Its `intake_sha256` hashes
the intake's canonical JSON model, not the source digest or the pretty-printed file bytes.
Each evidence reference carries a path and full-file SHA-256 from the intake; an optional
`signal_id` must name a signal that cites that same path. Every `regexstore` change needs a
concrete `dsl_example`; complex expressions also need positive and negative examples plus
caveats. Implemented results also require a clean committed patch captured with
`my-basis-adopt capture`; copy its manifest into `vcs.diffs`. Run
`my-basis-adopt validate <proposal.json>` before rendering.
"""


def prepare_repository(
    repository: Path | str,
    *,
    output_dir: Path | str | None = None,
    target_python: str | None = None,
    dry: bool = False,
) -> dict[str, Any]:
    """Create or refresh deterministic adoption artifacts for a repository.

    Args:
        repository: Repository root to scan.
        output_dir: Explicit artifact directory. Defaults to ``.basis-adoption`` in the root.
        target_python: Optional floor to reach as part of the requested refactor.
        dry: Report paths without writing artifacts.
    Returns:
        Machine-readable summary of the scan and artifact paths.
    """
    root = Path(repository).expanduser().resolve()
    artifact_dir = _absolute_path(output_dir) if output_dir is not None else root / ARTIFACT_DIR
    _refuse_symlink_path(artifact_dir)
    if artifact_dir.is_relative_to(root) and artifact_dir != root / ARTIFACT_DIR:
        raise AdoptionCommandError(
            f'an in-repository output must be exactly {root / ARTIFACT_DIR}; '
            'choose an external --output-dir for fleet dogfooding'
        )

    context_path = artifact_dir / CONTEXT_NAME
    intake_path = artifact_dir / INTAKE_NAME
    prompt_path = artifact_dir / PROMPT_NAME
    previous_intake: Intake | None = None
    if intake_path.is_file():
        _refuse_symlink_path(intake_path)
        try:
            previous_intake = load_intake(intake_path)
        except (OSError, pyd.ValidationError):
            previous_intake = None

    if target_python is None and previous_intake is not None:
        saved_target = previous_intake.python.get('target')
        target_python = saved_target if isinstance(saved_target, str) else None
    try:
        intake = scan_repository(root, target_python=target_python)
    except ValueError as exc:
        raise AdoptionCommandError(str(exc)) from exc
    template_path, template_text = _template_destination(
        artifact_dir,
        intake,
        previous_intake,
    )
    for path in (context_path, intake_path, prompt_path, template_path):
        _refuse_symlink_path(path)

    _write(
        context_path,
        _json_text({'repository': str(root), 'target_python': target_python}),
        dry=dry,
    )
    _write(intake_path, _json_text(intake), dry=dry)
    _write(prompt_path, _prompt(intake, template_path.name), dry=dry)
    _write(template_path, template_text, dry=dry)
    return {
        'repository': str(root),
        'disposition': intake.disposition,
        'target_python': target_python,
        'source_digest': intake.source_digest,
        'written': not dry,
        'template': str(template_path),
        'artifacts': [
            str(context_path),
            str(intake_path),
            str(prompt_path),
            str(template_path),
        ],
    }


def refresh_intake(
    path: Path | str,
    *,
    repository: Path | str | None = None,
    target_python: str | None = None,
    dry: bool = False,
) -> dict[str, Any]:
    """Refresh an intake in place using explicit or prepared repository context."""
    intake_path = _absolute_path(path)
    _refuse_symlink_path(intake_path)
    if intake_path.name != INTAKE_NAME:
        raise AdoptionCommandError(f'expected an {INTAKE_NAME!r} path: {intake_path}')
    root = _repository_for_artifact(intake_path.parent, repository)
    return prepare_repository(
        root,
        output_dir=intake_path.parent,
        target_python=target_python,
        dry=dry,
    )


def validate_file(
    proposal_path: Path | str,
    *,
    intake_path: Path | str | None = None,
    repository: Path | str | None = None,
    allow_stale: bool = False,
) -> dict[str, Any]:
    """Validate a proposal against saved and current evidence."""
    proposal_file = _absolute_path(proposal_path)
    intake_file = (
        _absolute_path(intake_path)
        if intake_path is not None
        else proposal_file.parent / INTAKE_NAME
    )
    proposal = load_proposal(proposal_file)
    intake = load_intake(intake_file)
    current_root = None if allow_stale else _repository_for_artifact(intake_file.parent, repository)
    validate_proposal(proposal, intake, repository=current_root)
    return {
        'valid': True,
        'proposal': str(proposal_file),
        'intake': str(intake_file),
        'freshness_checked': not allow_stale,
        'changes': len(proposal.changes),
    }


def render_file(
    proposal_path: Path | str,
    *,
    intake_path: Path | str | None = None,
    repository: Path | str | None = None,
    output_format: RenderFormat = 'all',
    build: bool = False,
    allow_stale: bool = False,
    dry: bool = False,
) -> dict[str, Any]:
    """Validate and render a proposal into repository-local narrative artifacts."""
    proposal_file = _absolute_path(proposal_path)
    artifact_dir = proposal_file.parent
    validate_file(
        proposal_file,
        intake_path=intake_path,
        repository=repository,
        allow_stale=allow_stale,
    )
    proposal = load_proposal(proposal_file)

    renderers = {
        'myst': ('report.md', render_myst),
        'html': ('report.html', render_html),
        'typst': ('report.typ', render_typst),
    }
    selected = list(renderers) if output_format == 'all' else [output_format]
    if build and 'typst' not in selected:
        raise AdoptionCommandError('--build requires --format typst or --format all')

    outputs = [artifact_dir / renderers[name][0] for name in selected]
    pdf = artifact_dir / 'report.pdf' if build else None
    for output in (*outputs, *([pdf] if pdf is not None else [])):
        _refuse_symlink_path(output)
    for name, output in zip(selected, outputs, strict=True):
        renderer = renderers[name][1]
        _write(output, renderer(proposal), dry=dry)

    if build:
        executable = shutil.which('typst')
        if executable is None:
            raise AdoptionCommandError(
                'Typst source was rendered, but `typst` is not installed; '
                'install Typst or rerun without --build',
                status=3,
            )
        source = artifact_dir / 'report.typ'
        assert pdf is not None
        if not dry:
            result = sbp.run(
                [executable, 'compile', str(source), str(pdf)],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode:
                detail = result.stderr.strip() or result.stdout.strip() or 'unknown error'
                raise AdoptionCommandError(f'Typst compilation failed: {detail}', status=3)
        outputs.append(pdf)

    return {
        'proposal': str(proposal_file),
        'format': output_format,
        'written': not dry,
        'outputs': [str(path) for path in outputs],
    }


def _git(
    repository: Path,
    *args: str,
) -> str:
    """Run one read-only Git query and return its standard output."""
    result = sbp.run(
        ['git', *args],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or 'unknown Git error'
        raise AdoptionCommandError(f'git {" ".join(args)} failed: {detail}', status=3)
    return result.stdout


def capture_atomic_diff(
    repository: Path | str,
    *,
    base: str,
    head: str = 'HEAD',
    output_dir: Path | str,
    summary: str,
    dry: bool = False,
) -> dict[str, Any]:
    """Capture one clean, committed transformation as a SHA-bound patch corpus entry."""
    root = Path(repository).expanduser().resolve()
    if not root.is_dir():
        raise AdoptionCommandError(f'repository does not exist: {root}')
    if not summary.strip():
        raise AdoptionCommandError('--summary must be non-empty')
    if _git(root, 'status', '--porcelain', '--untracked-files=no').strip():
        raise AdoptionCommandError('refusing to capture a dirty tracked worktree; commit first')

    base_commit = _git(root, 'rev-parse', '--verify', f'{base}^{{commit}}').strip()
    head_commit = _git(root, 'rev-parse', '--verify', f'{head}^{{commit}}').strip()
    if base_commit == head_commit:
        raise AdoptionCommandError('base and head resolve to the same commit')
    patch = _git(
        root,
        'diff',
        '--no-ext-diff',
        '--no-color',
        '--find-renames',
        '--patch',
        base_commit,
        head_commit,
    )
    if not patch:
        raise AdoptionCommandError('the selected revisions have no textual diff')
    patch_bytes = patch.encode()
    if len(patch_bytes) > 2_000_000:
        raise AdoptionCommandError('atomic diff exceeds the 2 MB corpus limit', status=3)
    diff_stat = _git(root, 'diff', '--stat', '--no-color', base_commit, head_commit).rstrip()

    target = _absolute_path(output_dir)
    patch_path = target / 'change.patch'
    manifest_path = target / 'manifest.json'
    for path in (target, patch_path, manifest_path):
        _refuse_symlink_path(path)
    manifest = {
        'schema_version': 'my-basis-adoption/diff/v1',
        'repository': str(root),
        'base_commit': base_commit,
        'head_commit': head_commit,
        'patch_path': patch_path.name,
        'patch_sha256': hashlib.sha256(patch_bytes).hexdigest(),
        'bytes': len(patch_bytes),
        'diff_stat': diff_stat,
        'summary': summary.strip(),
    }
    _write(patch_path, patch, dry=dry)
    _write(manifest_path, _json_text(manifest), dry=dry)
    return {
        **manifest,
        'patch': str(patch_path),
        'manifest': str(manifest_path),
        'written': not dry,
    }


def skill_root() -> Path:
    """Return the packaged adopt-my-basis skill directory."""
    path = Path(__file__).resolve().parents[1] / 'skills' / 'adopt-my-basis'
    if not (path / 'SKILL.md').is_file():
        raise AdoptionCommandError(
            'the packaged adopt-my-basis skill is missing; reinstall my-basis',
            status=4,
        )
    return path


def export_skill(
    destination: Path | str,
    *,
    force: bool = False,
    dry: bool = False,
) -> dict[str, Any]:
    """Copy the packaged adoption skill to an explicit destination."""
    source = skill_root()
    target = _absolute_path(destination)
    _refuse_symlink_tree(target)
    if target.exists() and not force:
        raise AdoptionCommandError(
            f'destination exists: {target}; pass --force to merge packaged files'
        )
    if not dry:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, dirs_exist_ok=force)
    return {'source': str(source), 'destination': str(target), 'written': not dry}


def _emit(result: dict[str, Any], *, json_output: bool) -> None:
    """Print command results in human or stable JSON form."""
    if json_output:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return
    if artifacts := result.get('artifacts'):
        print('[my-basis-adopt]')
        for path in artifacts:
            print(f'  prepared  {path}')
        template = Path(str(result['template']))
        print(f'  next      copy {template} to {template.with_name("proposal.json")}')
    elif outputs := result.get('outputs'):
        print('[my-basis-adopt]')
        for path in outputs:
            print(f'  rendered  {path}')
    elif result.get('valid'):
        print(f'valid: {result["proposal"]} ({result["changes"]} change(s))')
    elif result.get('skill'):
        print(result['skill'])
    elif result.get('source') and result.get('destination'):
        print(f'exported: {result["source"]} -> {result["destination"]}')
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


############
### MAIN ###
############
def _cli(*vargs: str) -> ap.Namespace:
    """Parse command-line arguments."""
    parser = ap.ArgumentParser(
        prog='my-basis-adopt',
        description=(
            'Prepare deterministic evidence, validate an adoption proposal, and render its '
            'beginner-facing handoff.'
        ),
        epilog=(
            'Example: my-basis-adopt prepare . && '
            'my-basis-adopt validate .basis-adoption/proposal.json'
        ),
    )
    commands = parser.add_subparsers(dest='command')

    prepare = commands.add_parser('prepare', help='scan a repository and prepare agent inputs')
    prepare.add_argument('repository', nargs='?', default='.', type=Path)
    prepare.add_argument(
        '--output-dir',
        type=Path,
        help='write artifacts outside the target repository (recommended for fleet scans)',
    )
    prepare.add_argument(
        '--target-python',
        help='review adoption together with a requested Python floor migration (for example 3.13)',
    )
    prepare.add_argument('-n', '--dry-run', action='store_true')
    prepare.add_argument('--json', action='store_true')

    capture = commands.add_parser(
        'capture',
        help='capture a clean committed refactor as a SHA-bound atomic patch',
    )
    capture.add_argument('repository', nargs='?', default='.', type=Path)
    capture.add_argument('--base', required=True, help='baseline commit or ref')
    capture.add_argument('--head', default='HEAD', help='result commit or ref')
    capture.add_argument('--output-dir', required=True, type=Path)
    capture.add_argument('--summary', required=True)
    capture.add_argument('-n', '--dry-run', action='store_true')
    capture.add_argument('--json', action='store_true')

    refresh = commands.add_parser('refresh', help='refresh an existing intake from current source')
    refresh.add_argument('intake', type=Path)
    refresh.add_argument('--repository', type=Path)
    refresh.add_argument('--target-python', help='replace the saved modernization target')
    refresh.add_argument('-n', '--dry-run', action='store_true')
    refresh.add_argument('--json', action='store_true')

    validate = commands.add_parser('validate', help='validate proposal structure and evidence')
    validate.add_argument('proposal', type=Path)
    validate.add_argument('--intake', type=Path)
    validate.add_argument('--repository', type=Path)
    validate.add_argument('--allow-stale', action='store_true')
    validate.add_argument('--json', action='store_true')

    render = commands.add_parser('render', help='render a validated narrative handoff')
    render.add_argument('proposal', type=Path)
    render.add_argument('--intake', type=Path)
    render.add_argument('--repository', type=Path)
    render.add_argument(
        '--format',
        dest='output_format',
        choices=['all', 'html', 'myst', 'typst'],
        default='all',
    )
    render.add_argument('--build', action='store_true', help='also compile the Typst source to PDF')
    render.add_argument('--allow-stale', action='store_true')
    render.add_argument('-n', '--dry-run', action='store_true')
    render.add_argument('--json', action='store_true')

    skill = commands.add_parser('skill', help='locate or export the packaged agent skill')
    skill_commands = skill.add_subparsers(dest='skill_command')
    skill_path_parser = skill_commands.add_parser('path', help='print the packaged skill path')
    skill_path_parser.add_argument('--json', action='store_true')
    skill_export = skill_commands.add_parser('export', help='copy the skill to a chosen directory')
    skill_export.add_argument('destination', type=Path)
    skill_export.add_argument('-f', '--force', action='store_true')
    skill_export.add_argument('-n', '--dry-run', action='store_true')
    skill_export.add_argument('--json', action='store_true')

    args = parser.parse_args(vargs or None)
    args._parser = parser
    return args


def main(*vargs: str) -> int:
    """Run the my-basis adoption command."""
    args = _cli(*vargs)
    parser: ap.ArgumentParser = args._parser
    try:
        if args.command == 'prepare':
            result = prepare_repository(
                args.repository,
                output_dir=args.output_dir,
                target_python=args.target_python,
                dry=args.dry_run,
            )
        elif args.command == 'capture':
            result = capture_atomic_diff(
                args.repository,
                base=args.base,
                head=args.head,
                output_dir=args.output_dir,
                summary=args.summary,
                dry=args.dry_run,
            )
        elif args.command == 'refresh':
            result = refresh_intake(
                args.intake,
                repository=args.repository,
                target_python=args.target_python,
                dry=args.dry_run,
            )
        elif args.command == 'validate':
            result = validate_file(
                args.proposal,
                intake_path=args.intake,
                repository=args.repository,
                allow_stale=args.allow_stale,
            )
        elif args.command == 'render':
            result = render_file(
                args.proposal,
                intake_path=args.intake,
                repository=args.repository,
                output_format=args.output_format,
                build=args.build,
                allow_stale=args.allow_stale,
                dry=args.dry_run,
            )
        elif args.command == 'skill' and args.skill_command == 'path':
            result = {'skill': str(skill_root())}
        elif args.command == 'skill' and args.skill_command == 'export':
            result = export_skill(
                args.destination,
                force=args.force,
                dry=args.dry_run,
            )
        else:
            parser.print_help()
            return 0
        _emit(result, json_output=bool(args.json))
        return 0
    except (AdoptionCommandError, OSError, pyd.ValidationError, ProposalValidationError) as exc:
        if isinstance(exc, (pyd.ValidationError, ProposalValidationError)):
            message = validation_error_text(exc)
            status = 2
        else:
            message = str(exc)
            status = exc.status if isinstance(exc, AdoptionCommandError) else 4
        print(f'my-basis-adopt: {message}', file=sys.stderr)
        return status


if __name__ == '__main__':
    raise SystemExit(main())
