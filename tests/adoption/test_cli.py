############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from pathlib import Path
from typing import Literal
import json

### EXTERNAL
import pytest as pyt

### INTERNAL
from my._adoption import load_intake, load_proposal, validate_proposal
from my.scripts import adopt_basis
from .test_proposal import make_proposal
from .test_scanner import make_repository


############
### BODY ###
############
class TestAdoptionCli:
    # ------------------
    # `*` Public Methods
    # ------------------
    @pyt.mark.parametrize('dry', [True, False])
    def test_prepare_repository(self, tmp_path: Path, dry: bool):
        """Test prepare writes only its declared repository-local artifact directory."""
        root = make_repository(tmp_path / 'repo')
        before = {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob('*')
            if path.is_file()
        }

        result = adopt_basis.prepare_repository(root, dry=dry)
        after = {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob('*')
            if path.is_file() and '.basis-adoption' not in path.parts
        }

        assert result['written'] is not dry
        assert after == before
        assert (root / '.basis-adoption').exists() is not dry

    def test_prepare_repository__external(self, tmp_path: Path):
        """Test fleet scans can keep every artifact outside the target worktree."""
        root = make_repository(tmp_path / 'repo')
        (root / 'Taskfile.yaml').write_text(
            'version: "3"\ntasks:\n    test:\n        cmd: uv run pytest\n'
        )
        output = tmp_path / 'fleet-artifacts' / 'fixture'

        result = adopt_basis.prepare_repository(root, output_dir=output)

        assert not (root / '.basis-adoption').exists()
        assert {path.name for path in output.iterdir()} == {
            'agent-prompt.md',
            'context.json',
            'intake.json',
            'proposal.template.json',
        }
        assert {Path(path).parent for path in result['artifacts']} == {output}
        prompt = (output / 'agent-prompt.md').read_text()
        for command in (
            'my-basis-adopt skill path',
            'my-basis-adopt skill export <destination>',
            'test ! -e proposal.json && cp proposal.template.json proposal.json',
            'task test',
        ):
            assert command in prompt
        assert 'Candidate native gates' in prompt
        assert 'regex-focused' in prompt
        first = load_intake(output / 'intake.json').source_digest
        (root / 'fixture' / '__init__.py').write_text('VALUE = 2\n')

        adopt_basis.refresh_intake(output / 'intake.json')

        assert load_intake(output / 'intake.json').source_digest != first
        assert not (root / '.basis-adoption').exists()

    @pyt.mark.parametrize('case', ['parent', 'prepare-file', 'render-file', 'build-file'])
    def test_artifact_writes__symlinks(self, tmp_path: Path, case: str):
        """Test artifact writers refuse symlink destinations and parents."""
        root = make_repository(tmp_path / 'repo')
        outside = tmp_path / 'outside'
        outside.mkdir()
        sentinel = outside / 'sentinel.txt'
        sentinel.write_text('preserve\n')

        if case == 'parent':
            alias = tmp_path / 'artifact-link'
            alias.symlink_to(outside, target_is_directory=True)
            action = lambda: adopt_basis.prepare_repository(root, output_dir=alias / 'nested')
        elif case == 'prepare-file':
            output = tmp_path / 'artifacts'
            output.mkdir()
            (output / adopt_basis.CONTEXT_NAME).symlink_to(sentinel)
            action = lambda: adopt_basis.prepare_repository(root, output_dir=output)
        else:
            adopt_basis.prepare_repository(root)
            artifact_dir = root / adopt_basis.ARTIFACT_DIR
            intake = load_intake(artifact_dir / adopt_basis.INTAKE_NAME)
            proposal = artifact_dir / 'proposal.json'
            proposal.write_text(make_proposal(intake).model_dump_json(indent=2))
            if case == 'render-file':
                (artifact_dir / 'report.md').symlink_to(sentinel)
                action = lambda: adopt_basis.render_file(proposal, output_format='myst')
            else:
                (artifact_dir / 'report.pdf').symlink_to(sentinel)
                action = lambda: adopt_basis.render_file(
                    proposal,
                    output_format='typst',
                    build=True,
                )

        with pyt.raises(adopt_basis.AdoptionCommandError, match='symlink'):
            action()

        assert sentinel.read_text() == 'preserve\n'
        if case == 'parent':
            assert not (outside / 'nested').exists()

    @pyt.mark.parametrize('edited_template', [False, True])
    def test_refresh_intake(self, tmp_path: Path, edited_template: bool):
        """Test refresh updates generated templates without overwriting operator work."""
        root = make_repository(tmp_path / 'repo')
        adopt_basis.prepare_repository(root)
        artifact_dir = root / '.basis-adoption'
        intake_path = artifact_dir / 'intake.json'
        primary_template = artifact_dir / adopt_basis.PROPOSAL_TEMPLATE_NAME
        proposal = artifact_dir / 'proposal.json'
        proposal.write_text('operator-owned\n')
        if edited_template:
            primary_template.write_text(primary_template.read_text() + '\noperator-owned\n')
        primary_before = primary_template.read_bytes()
        first = load_intake(intake_path).source_digest
        (root / 'fixture' / '__init__.py').write_text('VALUE = 2\n')

        result = adopt_basis.refresh_intake(intake_path)
        repeated = adopt_basis.refresh_intake(intake_path)

        intake = load_intake(intake_path)
        fresh_template = Path(result['template'])
        validate_proposal(load_proposal(fresh_template), intake)
        assert first != intake.source_digest
        assert repeated['template'] == result['template']
        assert proposal.read_text() == 'operator-owned\n'
        if edited_template:
            assert primary_template.read_bytes() == primary_before
            assert fresh_template != primary_template
            assert fresh_template.name.startswith('proposal.template.next-')
            assert list(artifact_dir.glob('proposal.template.next-*')) == [fresh_template]
            fresh_template.write_text('operator-edited next template\n')
            with pyt.raises(adopt_basis.AdoptionCommandError, match='refusing to overwrite'):
                adopt_basis.refresh_intake(intake_path)
            assert fresh_template.read_text() == 'operator-edited next template\n'
        else:
            assert fresh_template == primary_template
            assert primary_template.read_bytes() != primary_before

    @pyt.mark.parametrize('output_format', ['myst', 'html', 'typst', 'all'])
    def test_render_file(
        self,
        tmp_path: Path,
        output_format: Literal['all', 'html', 'myst', 'typst'],
    ):
        """Test each render selection writes only the corresponding report artifacts."""
        root = make_repository(tmp_path / 'repo')
        adopt_basis.prepare_repository(root)
        artifact_dir = root / '.basis-adoption'
        intake = load_intake(artifact_dir / 'intake.json')
        proposal = artifact_dir / 'proposal.json'
        proposal.write_text(
            make_proposal(intake).model_dump_json(indent=2),
        )

        result = adopt_basis.render_file(proposal, output_format=output_format)

        expected = {
            'myst': {'report.md'},
            'html': {'report.html'},
            'typst': {'report.typ'},
            'all': {'report.md', 'report.html', 'report.typ'},
        }[output_format]
        assert {Path(path).name for path in result['outputs']} == expected

    def test_render_file__missing_typst(
        self,
        tmp_path: Path,
        monkeypatch: pyt.MonkeyPatch,
    ):
        """Test optional PDF compilation names the missing external tool."""
        root = make_repository(tmp_path / 'repo')
        adopt_basis.prepare_repository(root)
        artifact_dir = root / '.basis-adoption'
        intake = load_intake(artifact_dir / 'intake.json')
        proposal = artifact_dir / 'proposal.json'
        proposal.write_text(make_proposal(intake).model_dump_json(indent=2))
        monkeypatch.setattr(adopt_basis.shutil, 'which', lambda _: None)

        with pyt.raises(adopt_basis.AdoptionCommandError, match='not installed') as exc:
            adopt_basis.render_file(proposal, output_format='typst', build=True)

        assert exc.value.status == 3
        assert (artifact_dir / 'report.typ').exists()
        assert not (artifact_dir / 'report.pdf').exists()

    @pyt.mark.parametrize('command', ['prepare', 'validate', 'render'])
    def test_main__json(
        self,
        tmp_path: Path,
        capsys: pyt.CaptureFixture[str],
        command: str,
    ):
        """Test pipeline-facing commands emit clean machine-readable output."""
        root = make_repository(tmp_path / 'repo')
        artifact_dir = root / '.basis-adoption'
        if command != 'prepare':
            adopt_basis.prepare_repository(root)
            intake = load_intake(artifact_dir / 'intake.json')
            (artifact_dir / 'proposal.json').write_text(
                make_proposal(intake).model_dump_json(indent=2)
            )
        arguments = {
            'prepare': ('prepare', str(root), '--json'),
            'validate': ('validate', str(artifact_dir / 'proposal.json'), '--json'),
            'render': (
                'render',
                str(artifact_dir / 'proposal.json'),
                '--format',
                'myst',
                '--json',
            ),
        }[command]

        status = adopt_basis.main(*arguments)
        output = json.loads(capsys.readouterr().out)

        assert status == 0
        assert isinstance(output, dict)

    @pyt.mark.parametrize('json_output', [False, True])
    def test_skill__path(
        self,
        capsys: pyt.CaptureFixture[str],
        json_output: bool,
    ):
        """Test people and pipelines can discover the packaged skill path."""
        arguments = ('skill', 'path', '--json') if json_output else ('skill', 'path')

        status = adopt_basis.main(*arguments)
        output = capsys.readouterr().out.strip()
        path = Path(json.loads(output)['skill'] if json_output else output)

        assert status == 0
        assert path.name == 'adopt-my-basis'
        assert (path / 'SKILL.md').is_file()

    @pyt.mark.parametrize('force', [False, True])
    def test_skill__export(self, tmp_path: Path, force: bool):
        """Test the packaged skill can be located and explicitly exported."""
        destination = tmp_path / 'skill'
        if force:
            destination.mkdir()
            (destination / 'local-note.txt').write_text('preserve\n')

        result = adopt_basis.export_skill(destination, force=force)

        assert Path(result['source']).name == 'adopt-my-basis'
        assert (destination / 'SKILL.md').is_file()
        if force:
            assert (destination / 'local-note.txt').read_text() == 'preserve\n'

    def test_skill__documentation(self):
        """Test the packaged skill documents render routes and runs its capture example."""
        root = adopt_basis.skill_root()
        skill = (root / 'SKILL.md').read_text()
        reference = (root / 'references' / 'regexstore.md').read_text()
        section = reference.split('## Reuse and captures', 1)[1]
        example = section.split('```python', 1)[1].split('```', 1)[0]

        for command in ('--format typst --build', '--format html'):
            assert command in skill
        exec(compile(example, 'regexstore.md', 'exec'), {})
