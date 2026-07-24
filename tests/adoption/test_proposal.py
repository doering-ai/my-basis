############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

### EXTERNAL
import pydantic as pyd
import pytest as pyt

### INTERNAL
from my._adoption import (
    Intake,
    Proposal,
    ProposalValidationError,
    RegexStoreProposal,
    intake_sha256,
    proposal_template,
    render_html,
    render_myst,
    render_typst,
    scan_repository,
    validate_proposal,
)
from .test_scanner import make_repository


############
### DATA ###
############
def make_proposal(intake: Intake, **updates: Any) -> Proposal:
    """Create a complete canonical proposal for validation and rendering tests."""
    evidence = next(item for item in intake.evidence if item.path == 'fixture/__init__.py')
    data: dict[str, Any] = {
        'intake_sha256': intake_sha256(intake),
        'mode': 'implement',
        'disposition': 'adopt',
        'summary': {
            'repository_story': 'Fixture is a small command parser.',
            'adoption_thesis': 'A small narrative that keeps behavior visible.',
            'deliberate_non_changes': ['Keep the public command names unchanged.'],
        },
        'baseline': {'head': 'abc1234', 'commands': ['task test']},
        'changes': [
            {
                'id': 'regex.router',
                'status': 'implemented',
                'title': 'Name the command router',
                'why': 'The router becomes one named grammar with bounded examples.',
                'evidence_refs': [
                    {
                        'path': evidence.path,
                        'sha256': evidence.sha256,
                        'signal_id': None,
                    }
                ],
                'basis_apis': ['RegexStore'],
                'files': ['fixture/__init__.py'],
                'behavior_contract': 'Open and close remain full-match commands.',
                'risk': 'An alternation boundary could change.',
                'tests': ['task test'],
                'regexstore': {
                    'complexity': 'complex',
                    'before': "ROUTES = re.compile(r'open|close')",
                    'dsl_example': ("ROUTES = RegexStore.new(command=('<|>', ['open', 'close']))"),
                    'positive_examples': [{'input': 'open', 'expected': True}],
                    'negative_examples': [{'input': 'opened', 'expected': False}],
                    'caveats': ['Keep the full-match boundary explicit.'],
                },
            }
        ],
        'verification': [
            {
                'command': 'task test',
                'cwd': '.',
                'exit_code': 0,
                'output_tail': '1 passed',
                'state': 'passed',
            }
        ],
        'vcs': {
            'base_branch': 'main',
            'work_branch': 'agent/MEMY-754-fixture',
            'commits': ['abc1234'],
            'diff_stat': '2 files changed',
            'diffs': [
                {
                    'base_commit': 'a' * 40,
                    'head_commit': 'b' * 40,
                    'patch_path': 'diffs/regex-router.patch',
                    'patch_sha256': 'c' * 64,
                    'bytes': 312,
                    'diff_stat': '2 files changed',
                    'summary': 'Replace the ad-hoc router with one named RegexStore grammar.',
                }
            ],
        },
        'report': {'format': 'myst', 'source': 'report.md', 'rendered': 'report.html'},
        'handoff': {
            'merge_kind': 'branch',
            'merge_commands': ['Run task test.', 'Review and merge the branch.'],
            'review_url': None,
            'revision_prompt': (
                'Use $adopt-my-basis and preserve accepted IDs. Revise regex.router, then run '
                'my-basis-adopt refresh.'
            ),
        },
        'problem_space': {
            'nodes': ['Inspect the remaining dynamic patterns.'],
            'keystone': 'Confirm router equivalence.',
            'terminus': 'The command grammar has one owner.',
        },
    }
    data.update(updates)
    return Proposal.model_validate(data)


############
### BODY ###
############
class TestRegexStoreProposal:
    # -------------------
    # `.` Initial Methods
    # -------------------
    @pyt.mark.parametrize(
        'data, expected_error',
        [
            ({'before': 're.compile("x")', 'dsl_example': ''}, 'non-empty DSL'),
            (
                {
                    'before': 're.compile("x")',
                    'dsl_example': 'store = RegexStore.new()',
                    'complexity': 'complex',
                },
                'positive examples',
            ),
            (
                {
                    'before': 're.compile("x")',
                    'dsl_example': 'store = RegexStore.new()',
                    'complexity': 'complex',
                    'positive_examples': [{'input': 'x', 'expected': True}],
                },
                'negative examples',
            ),
            (
                {
                    'before': 're.compile("x")',
                    'dsl_example': 'store = RegexStore.new()',
                    'complexity': 'complex',
                    'positive_examples': [{'input': 'x', 'expected': True}],
                    'negative_examples': [{'input': 'y', 'expected': False}],
                },
                'caveats',
            ),
        ],
    )
    def test_construct__invalid(self, data: dict[str, Any], expected_error: str):
        """Test RegexStore proposals require examples proportional to complexity."""
        with pyt.raises(pyd.ValidationError, match=expected_error):
            RegexStoreProposal.model_validate(data)

    @pyt.mark.parametrize(
        'data',
        [
            {
                'before': 're.compile(r"\\w+")',
                'dsl_example': "store['word'] = r'\\w+'",
            },
            {
                'before': 're.compile(r"alpha|beta")',
                'dsl_example': "store['word'] = ('|', ['alpha', 'beta'])",
                'complexity': 'complex',
                'positive_examples': [{'input': 'alpha', 'expected': True}],
                'negative_examples': [{'input': 'gamma', 'expected': False}],
                'caveats': ['Alternation is intentionally ordered.'],
            },
        ],
    )
    def test_construct(self, data: dict[str, Any]):
        """Test simple and fully evidenced complex RegexStore proposals."""
        assert RegexStoreProposal.model_validate(data).dsl_example == data['dsl_example']


class TestProposal:
    # ------------------
    # `*` Public Methods
    # ------------------
    @pyt.mark.parametrize(
        'mutation, expected_error',
        [
            ('digest', 'intake_sha256'),
            ('path', 'unknown evidence'),
            ('hash', 'stale evidence hash'),
            ('signal', 'unknown signal'),
            ('signal-path', 'does not cite evidence'),
            ('duplicate', 'duplicate change IDs'),
            ('handoff-commands', 'requires merge_commands'),
            ('handoff-branch', 'requires vcs.work_branch'),
            ('handoff-review', 'requires review_url'),
            ('handoff-url-kind', 'review_url requires'),
            ('handoff-revision', 'revision_prompt'),
            ('handoff-none', 'implemented changes require a merge handoff'),
            ('handoff-none-commands', 'forbids merge_commands'),
            ('diff-corpus', 'implemented changes require an atomic diff artifact'),
        ],
    )
    def test_validate_proposal__invalid(
        self,
        tmp_path: Path,
        mutation: str,
        expected_error: str,
    ):
        """Test proposal digests, evidence references, and stable IDs fail closed."""
        root = make_repository(tmp_path / 'repo')
        intake = scan_repository(root)
        proposal = make_proposal(intake)
        reference = proposal.changes[0].evidence_refs[0]
        if mutation == 'digest':
            proposal.intake_sha256 = '0' * 64
        elif mutation == 'path':
            reference.path = 'missing.py'
        elif mutation == 'hash':
            reference.sha256 = '0' * 64
        elif mutation == 'signal':
            reference.signal_id = 'missing.signal'
        elif mutation == 'signal-path':
            reference.signal_id = 'adoption.review'
        elif mutation == 'duplicate':
            proposal.changes.append(proposal.changes[0].model_copy())
        elif mutation == 'handoff-commands':
            proposal.handoff.merge_commands = []
        elif mutation == 'handoff-branch':
            proposal.vcs.work_branch = None
        elif mutation == 'handoff-review':
            proposal.handoff.merge_kind = 'merge-request'
            proposal.handoff.review_url = None
        elif mutation == 'handoff-url-kind':
            proposal.handoff.review_url = 'https://example.test/review/42'
        elif mutation == 'handoff-revision':
            proposal.handoff.revision_prompt = '  '
        elif mutation == 'handoff-none':
            proposal.handoff.merge_kind = 'none'
        elif mutation == 'handoff-none-commands':
            proposal.changes = []
            proposal.handoff.merge_kind = 'none'
        elif mutation == 'diff-corpus':
            proposal.vcs.diffs = []

        with pyt.raises(ProposalValidationError, match=expected_error):
            validate_proposal(proposal, intake)

    @pyt.mark.parametrize(
        'mode, status, evidence, verification_state, expected_error',
        [
            ('propose', 'proposed', False, 'passed', 'requires evidence'),
            ('propose', 'implemented', True, 'passed', 'requires mode'),
            ('implement', 'implemented', False, 'passed', 'requires evidence'),
            ('implement', 'implemented', True, None, 'requires verification'),
            ('implement', 'implemented', True, 'not-run', 'requires verification'),
        ],
    )
    def test_validate_proposal__claims(
        self,
        tmp_path: Path,
        mode: Literal['propose', 'implement'],
        status: Literal['proposed', 'implemented'],
        evidence: bool,
        verification_state: Literal['passed', 'not-run'] | None,
        expected_error: str,
    ):
        """Test change claims bind mode, evidence, and honest verification."""
        intake = scan_repository(make_repository(tmp_path / 'repo'))
        proposal = make_proposal(intake)
        proposal.mode = mode
        proposal.changes[0].status = status
        if not evidence:
            proposal.changes[0].evidence_refs = []
        if verification_state is None:
            proposal.verification = []
        elif verification_state == 'not-run':
            proposal.verification = [
                proposal.verification[0].model_copy(update={'state': 'not-run', 'exit_code': None})
            ]

        with pyt.raises(ProposalValidationError, match=expected_error):
            validate_proposal(proposal, intake)

    @pyt.mark.parametrize(
        'state, exit_code',
        [('passed', 0), ('failed', 1), ('unavailable', None)],
    )
    def test_validate_proposal__verification(
        self,
        tmp_path: Path,
        state: Literal['passed', 'failed', 'unavailable'],
        exit_code: int | None,
    ):
        """Test implementation accepts recorded results and explicit unavailability."""
        intake = scan_repository(make_repository(tmp_path / 'repo'))
        proposal = make_proposal(intake)
        proposal.verification = [
            proposal.verification[0].model_copy(update={'state': state, 'exit_code': exit_code})
        ]

        validate_proposal(proposal, intake)

    def test_validate_proposal__signal_path(self, tmp_path: Path):
        """Test a signal accepts evidence only from its own cited paths."""
        root = make_repository(
            tmp_path / 'repo',
            python=(
                'import re\n'
                'A = re.search(r"a", "a")\n'
                'B = re.search(r"b", "b")\n'
                'C = re.search(r"c", "c")\n'
            ),
        )
        intake = scan_repository(root)
        proposal = make_proposal(intake)
        proposal.changes[0].evidence_refs[0].signal_id = 'regexstore.consolidation'

        validate_proposal(proposal, intake)

    def test_validate_proposal__intake(self, tmp_path: Path):
        """Test derived intake changes invalidate an otherwise fresh proposal."""
        intake = scan_repository(make_repository(tmp_path / 'repo'))
        proposal = make_proposal(intake)
        source_digest = intake.source_digest
        intake.disposition['reason'] = 'A materially different deterministic intake.'

        assert intake.source_digest == source_digest
        with pyt.raises(ProposalValidationError, match='canonical intake'):
            validate_proposal(proposal, intake)

    @pyt.mark.parametrize('fresh', [True, False])
    def test_validate_proposal__freshness(self, tmp_path: Path, fresh: bool):
        """Test validation can prove current evidence or identify a stale intake."""
        root = make_repository(tmp_path / 'repo')
        intake = scan_repository(root)
        proposal = make_proposal(intake)
        if not fresh:
            (root / 'fixture' / '__init__.py').write_text('VALUE = 2\n')

        if fresh:
            validate_proposal(proposal, intake, repository=root)
        else:
            with pyt.raises(ProposalValidationError, match='stale'):
                validate_proposal(proposal, intake, repository=root)

    @pyt.mark.parametrize(
        'renderer, marker',
        [
            (render_myst, '```python'),
            (render_html, '<pre><code>'),
            (render_typst, '#raw('),
        ],
    )
    def test_render__parity(
        self,
        tmp_path: Path,
        renderer: Callable[[Proposal], str],
        marker: str,
    ):
        """Test every report format carries the narrative, DSL, and handoff."""
        root = make_repository(tmp_path / 'repo')
        proposal = make_proposal(scan_repository(root))
        proposal.handoff.merge_kind = 'merge-request'
        proposal.handoff.review_url = 'https://example.test/review/42'
        rendered = renderer(proposal)

        for expected in (
            'A small narrative that keeps behavior visible.',
            'Name the command router',
            'RegexStore',
            'Run task test.',
            'my-basis-adopt refresh',
            'agent/MEMY-754-fixture',
            'abc1234',
            '2 files changed',
            'https://example.test/review/42',
        ):
            assert expected in rendered
        assert marker in rendered

    @pyt.mark.parametrize(
        'field',
        [
            'title',
            'behavior_contract',
            'risk',
            'deliberate_non_changes',
            'caveats',
            'revision_prompt',
            'nodes',
            'keystone',
            'terminus',
        ],
    )
    def test_render_typst__text(self, tmp_path: Path, field: str):
        """Test arbitrary proposal text remains inert inside Typst text nodes."""
        proposal = make_proposal(scan_repository(make_repository(tmp_path / 'repo')))
        payload = '#panic([executed])'
        if field in {'title', 'behavior_contract', 'risk'}:
            setattr(proposal.changes[0], field, payload)
        elif field == 'deliberate_non_changes':
            proposal.summary.deliberate_non_changes = [payload]
        elif field == 'caveats':
            assert proposal.changes[0].regexstore is not None
            proposal.changes[0].regexstore.caveats = [payload]
        elif field == 'revision_prompt':
            proposal.handoff.revision_prompt = payload
        elif field == 'nodes':
            proposal.problem_space.nodes = [payload]
        else:
            setattr(proposal.problem_space, field, payload)

        rendered = render_typst(proposal)

        for line in rendered.splitlines():
            if payload in line:
                assert f'#text("{payload}")' in line

    def test_render_myst__table(self, tmp_path: Path):
        """Test RegexStore table values escape Markdown column delimiters."""
        proposal = make_proposal(scan_repository(make_repository(tmp_path / 'repo')))
        regexstore = proposal.changes[0].regexstore
        assert regexstore is not None
        regexstore.positive_examples[0].input = 'left|right'

        rendered = render_myst(proposal)

        assert '`left\\|right`' in rendered
        assert '`left|right`' not in rendered

    @pyt.mark.parametrize(
        'status, dependency_present, expected',
        [
            ('review', False, 'partial'),
            ('defer', False, 'blocked'),
            ('no-op', False, 'decline'),
            ('no-op', True, 'already-adopted'),
        ],
    )
    def test_proposal_template(
        self,
        tmp_path: Path,
        status: str,
        dependency_present: bool,
        expected: str,
    ):
        """Test every intake disposition produces an editable valid template."""
        root = make_repository(tmp_path / 'repo')
        intake = scan_repository(root)
        intake.disposition['status'] = status
        intake.dependency['my_basis_present'] = dependency_present

        proposal = proposal_template(intake)

        assert proposal.disposition == expected
        assert proposal.intake_sha256 == intake_sha256(intake)
        assert proposal.intake_sha256 != intake.source_digest
        assert proposal.baseline.commands == []
        assert proposal.schema_version == 'my-basis-adoption/proposal/v2'
