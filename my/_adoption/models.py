############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import Literal

### EXTERNAL
import pydantic as pyd


############
### DATA ###
############
class FileEvidence(pyd.BaseModel):
    """Identify one scanned file without retaining its contents."""

    model_config = pyd.ConfigDict(frozen=True)

    path: str
    kind: Literal['config', 'python', 'workflow']
    sha256: str


class ImportFact(pyd.BaseModel):
    """Summarize imports of one top-level Python module."""

    model_config = pyd.ConfigDict(frozen=True)

    module: str
    occurrences: int
    files: list[str]


class RegexPatternFact(pyd.BaseModel):
    """Describe one statically visible regular-expression call."""

    model_config = pyd.ConfigDict(frozen=True)

    path: str
    line: int
    engine: Literal['re', 'regex']
    operation: str
    pattern: str | None = None
    pattern_sha256: str | None = None
    complex: bool = False
    test: bool = False


class Signal(pyd.BaseModel):
    """Present one stable, evidence-linked adoption signal."""

    model_config = pyd.ConfigDict(frozen=True)

    id: str
    level: Literal['info', 'opportunity', 'constraint']
    summary: str
    evidence: list[str] = pyd.Field(default_factory=list)


class Intake(pyd.BaseModel):
    """Contain deterministic facts used to plan a my-basis adoption."""

    schema_version: Literal[2] = 2
    repository: dict[str, str | None]
    source_digest: str
    python: dict[str, str | int | bool | None | list[str]]
    dependency: dict[str, str | bool | list[str]]
    commands: dict[str, list[str]]
    imports: list[ImportFact]
    regex: dict[str, int | bool | list[RegexPatternFact]]
    sublime: dict[str, str | bool | list[str] | None]
    exclusions: dict[str, int]
    parse_errors: list[str]
    disposition: dict[str, str]
    signals: list[Signal]
    evidence: list[FileEvidence]


class ContractModel(pyd.BaseModel):
    """Forbid misspelled fields in the beginner-facing proposal contract."""

    model_config = pyd.ConfigDict(extra='forbid')


class RegexExample(ContractModel):
    """Record one input and its expected RegexStore result."""

    input: str
    expected: str | bool | list[str]


class RegexStoreProposal(ContractModel):
    """Explain a proposed RegexStore DSL expression and its boundaries."""

    complexity: Literal['simple', 'complex'] = 'simple'
    before: str
    dsl_example: str
    positive_examples: list[RegexExample] = pyd.Field(default_factory=list)
    negative_examples: list[RegexExample] = pyd.Field(default_factory=list)
    caveats: list[str] = pyd.Field(default_factory=list)

    @pyd.model_validator(mode='after')
    def _validate_examples(self) -> RegexStoreProposal:
        if not self.dsl_example.strip():
            raise ValueError('RegexStore proposals require a non-empty DSL example')
        if self.complexity == 'complex' and not self.positive_examples:
            raise ValueError('complex RegexStore proposals require positive examples')
        if self.complexity == 'complex' and not self.negative_examples:
            raise ValueError('complex RegexStore proposals require negative examples')
        if self.complexity == 'complex' and not any(item.strip() for item in self.caveats):
            raise ValueError('complex RegexStore proposals require caveats')
        return self


class EvidenceRef(ContractModel):
    """Bind a change to exact intake evidence and an optional detector signal."""

    path: str
    sha256: str
    signal_id: str | None = None


class ChangeProposal(ContractModel):
    """Describe one stable, reviewable repository change."""

    id: str = pyd.Field(pattern=r'^[a-z0-9]+(?:[._-][a-z0-9]+)*$')
    title: str
    status: Literal['implemented', 'proposed', 'declined', 'deferred', 'already-present']
    why: str
    evidence_refs: list[EvidenceRef] = pyd.Field(default_factory=list)
    basis_apis: list[str] = pyd.Field(default_factory=list)
    files: list[str] = pyd.Field(default_factory=list)
    behavior_contract: str
    risk: str
    tests: list[str] = pyd.Field(default_factory=list)
    regexstore: RegexStoreProposal | None = None


class ProposalSummary(ContractModel):
    """Narrate the repository, adoption thesis, and deliberate non-changes."""

    repository_story: str
    adoption_thesis: str
    deliberate_non_changes: list[str] = pyd.Field(default_factory=list)


class Baseline(ContractModel):
    """Record the source revision and native commands used as the baseline."""

    head: str | None = None
    commands: list[str] = pyd.Field(default_factory=list)


class Verification(ContractModel):
    """Record one verification outcome without laundering unavailable work."""

    command: str
    cwd: str
    exit_code: int | None = None
    output_tail: str = ''
    state: Literal['passed', 'failed', 'unavailable', 'not-run']

    @pyd.model_validator(mode='after')
    def _validate_state(self) -> Verification:
        if self.state == 'passed' and self.exit_code != 0:
            raise ValueError('passed verification requires exit_code 0')
        if self.state == 'failed' and self.exit_code in {None, 0}:
            raise ValueError('failed verification requires a non-zero exit_code')
        if self.state in {'unavailable', 'not-run'} and self.exit_code is not None:
            raise ValueError(f'{self.state} verification must not claim an exit_code')
        return self


class AtomicDiff(ContractModel):
    """Bind one copy-ready transformation patch to exact Git revisions."""

    base_commit: str = pyd.Field(pattern=r'^[0-9a-f]{40,64}$')
    head_commit: str = pyd.Field(pattern=r'^[0-9a-f]{40,64}$')
    patch_path: str
    patch_sha256: str = pyd.Field(pattern=r'^[0-9a-f]{64}$')
    bytes: int = pyd.Field(ge=1)
    diff_stat: str
    summary: str

    @pyd.model_validator(mode='after')
    def _validate_patch(self) -> AtomicDiff:
        path = self.patch_path.replace('\\', '/')
        if path.startswith('/') or '..' in path.split('/'):
            raise ValueError('patch_path must be a repository-relative artifact path')
        if self.base_commit == self.head_commit:
            raise ValueError('atomic diff base_commit and head_commit must differ')
        if not self.summary.strip():
            raise ValueError('atomic diff summary must be non-empty')
        return self


class VcsResult(ContractModel):
    """Describe the local version-control result without implying a remote review."""

    base_branch: str | None = None
    work_branch: str | None = None
    commits: list[str] = pyd.Field(default_factory=list)
    diff_stat: str = ''
    diffs: list[AtomicDiff] = pyd.Field(default_factory=list)


class ReportResult(ContractModel):
    """Locate the preferred report source and any rendered artifact."""

    format: Literal['myst', 'typst', 'html']
    source: str | None = None
    rendered: str | None = None


class Handoff(ContractModel):
    """Give exact merge and stable-ID revision instructions."""

    merge_kind: Literal['branch', 'merge-request', 'patch', 'none']
    merge_commands: list[str] = pyd.Field(default_factory=list)
    review_url: str | None = None
    revision_prompt: str


class ProblemSpace(ContractModel):
    """Name the remaining frontier, its keystone, and its terminus."""

    nodes: list[str] = pyd.Field(default_factory=list)
    keystone: str
    terminus: str


class Proposal(ContractModel):
    """Represent the canonical agent-authored adoption proposal and handoff."""

    schema_version: Literal['my-basis-adoption/proposal/v2'] = 'my-basis-adoption/proposal/v2'
    intake_sha256: str = pyd.Field(
        pattern=r'^[0-9a-f]{64}$',
        description='SHA-256 of the canonical serialized intake payload.',
    )
    mode: Literal['propose', 'implement']
    disposition: Literal['adopt', 'partial', 'already-adopted', 'decline', 'blocked']
    summary: ProposalSummary
    baseline: Baseline
    changes: list[ChangeProposal] = pyd.Field(default_factory=list)
    verification: list[Verification] = pyd.Field(default_factory=list)
    vcs: VcsResult
    report: ReportResult
    handoff: Handoff
    problem_space: ProblemSpace
