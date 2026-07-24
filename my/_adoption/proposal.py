"""Validate and render evidence-linked my-basis adoption proposals."""

############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from html import escape
from pathlib import Path
from typing import Literal
import hashlib
import json
import re

### EXTERNAL
import pydantic as pyd

### INTERNAL
from .models import Intake, Proposal, RegexExample
from .scanner import scan_repository


############
### DATA ###
############
class ProposalValidationError(ValueError):
    """Report one or more actionable proposal validation failures."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__('; '.join(errors))


############
### BODY ###
############
def load_intake(path: Path | str) -> Intake:
    """Load and structurally validate an intake JSON file."""
    return Intake.model_validate_json(Path(path).read_text())


def load_proposal(path: Path | str) -> Proposal:
    """Load and structurally validate a proposal JSON file."""
    return Proposal.model_validate_json(Path(path).read_text())


def intake_sha256(intake: Intake) -> str:
    """Hash one intake's canonical JSON payload."""
    payload = json.dumps(
        intake.model_dump(mode='json'),
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def proposal_template(intake: Intake) -> Proposal:
    """Create a valid beginner-editable proposal tied to an intake."""
    repository = intake.repository.get('distribution') or intake.repository['name'] or 'repository'
    status = intake.disposition['status']
    disposition: Literal['adopt', 'partial', 'already-adopted', 'decline', 'blocked']
    if status == 'defer':
        disposition = 'blocked'
    elif status == 'no-op' and intake.dependency['my_basis_present']:
        disposition = 'already-adopted'
    elif status == 'no-op':
        disposition = 'decline'
    else:
        disposition = 'partial'
    return Proposal(
        intake_sha256=intake_sha256(intake),
        mode='propose',
        disposition=disposition,
        summary={
            'repository_story': (
                f'{repository} contains {intake.python["files"]} authored Python file(s). '
                'Replace this sentence with the repository narrative confirmed from source.'
            ),
            'adoption_thesis': (
                'The deterministic intake is ready. Explain why each bounded use of my-basis '
                'helps, or why preserving the current boundary is the better result.'
            ),
            'deliberate_non_changes': [],
        },
        baseline={'head': None, 'commands': []},
        changes=[],
        verification=[],
        vcs={'diff_stat': ''},
        report={'format': 'myst', 'source': 'report.md', 'rendered': None},
        handoff={
            'merge_kind': 'none',
            'merge_commands': [],
            'review_url': None,
            'revision_prompt': (
                'Use $adopt-my-basis with this intake and proposal. Preserve accepted change '
                'IDs, name the IDs to revise, rerun affected gates, and regenerate the report.'
            ),
        },
        problem_space={
            'nodes': [],
            'keystone': 'Choose or decline the first evidence-backed adoption.',
            'terminus': 'No terminus is known until the repository review is complete.',
        },
    )


def validate_proposal(
    proposal: Proposal,
    intake: Intake,
    *,
    repository: Path | str | None = None,
) -> None:
    """Verify proposal evidence, intake linkage, and optional source freshness.

    Args:
        proposal: Agent-authored proposal to verify.
        intake: Deterministic intake used by the proposal.
        repository: Repository root to rescan. Omit to validate saved evidence only.
    Raises:
        ProposalValidationError: If any validation rule fails.
    """
    errors: list[str] = []
    if proposal.intake_sha256 != intake_sha256(intake):
        errors.append('proposal intake_sha256 does not match canonical intake.json')
    intake_evidence = {item.path: item for item in intake.evidence}
    signals_by_id = {signal.id: signal for signal in intake.signals}
    implemented = [change for change in proposal.changes if change.status == 'implemented']
    for change in proposal.changes:
        if change.status in {'proposed', 'implemented'} and not change.evidence_refs:
            errors.append(f'change {change.id!r} with status {change.status!r} requires evidence')
        if change.status == 'implemented' and proposal.mode != 'implement':
            errors.append(f'change {change.id!r} status `implemented` requires mode `implement`')
        for reference in change.evidence_refs:
            evidence = intake_evidence.get(reference.path)
            if evidence is None:
                errors.append(f'change {change.id!r} cites unknown evidence: {reference.path}')
            elif reference.sha256 != evidence.sha256:
                errors.append(
                    f'change {change.id!r} cites a stale evidence hash for {reference.path}'
                )
            if reference.signal_id is not None:
                signal = signals_by_id.get(reference.signal_id)
                if signal is None:
                    errors.append(
                        f'change {change.id!r} cites unknown signal: {reference.signal_id}'
                    )
                elif reference.path not in signal.evidence:
                    errors.append(
                        f'change {change.id!r} signal {reference.signal_id!r} does not cite '
                        f'evidence {reference.path!r}'
                    )
    if implemented and not any(
        item.state in {'passed', 'failed', 'unavailable'} for item in proposal.verification
    ):
        errors.append(
            'an implemented change requires verification or an explicit unavailable result'
        )

    identifiers = [change.id for change in proposal.changes]
    duplicates = sorted(
        {identifier for identifier in identifiers if identifiers.count(identifier) > 1}
    )
    if duplicates:
        errors.append(f'duplicate change IDs: {", ".join(duplicates)}')

    merge_kind = proposal.handoff.merge_kind
    if merge_kind != 'none' and not any(
        command.strip() for command in proposal.handoff.merge_commands
    ):
        errors.append(f'handoff.merge_kind {merge_kind!r} requires merge_commands')
    if merge_kind == 'none' and any(command.strip() for command in proposal.handoff.merge_commands):
        errors.append("handoff.merge_kind 'none' forbids merge_commands")
    if merge_kind in {'branch', 'merge-request'} and not (
        proposal.vcs.work_branch and proposal.vcs.work_branch.strip()
    ):
        errors.append(f'handoff.merge_kind {merge_kind!r} requires vcs.work_branch')
    if merge_kind == 'merge-request' and not (
        proposal.handoff.review_url and proposal.handoff.review_url.strip()
    ):
        errors.append('handoff.merge_kind `merge-request` requires review_url')
    if implemented and merge_kind == 'none':
        errors.append('implemented changes require a merge handoff or patch')
    if not proposal.handoff.revision_prompt.strip():
        errors.append('handoff.revision_prompt must be non-empty')
    if proposal.handoff.review_url and merge_kind != 'merge-request':
        errors.append('review_url requires handoff.merge_kind `merge-request`')
    if repository is not None:
        current = scan_repository(repository)
        if current.source_digest != intake.source_digest:
            errors.append('intake evidence is stale; run `my-basis-adopt refresh <intake>`')
    if errors:
        raise ProposalValidationError(errors)


def _myst_table_code(value: str) -> str:
    """Escape a code value for a MyST table cell."""
    return value.replace('|', r'\|')


def _myst_examples(title: str, examples: list[RegexExample]) -> list[str]:
    """Render a RegexStore example table for MyST."""
    if not examples:
        return []
    lines = [f'**{title}**', '', '| Input | Expected |', '| --- | --- |']
    lines.extend(
        f'| `{_myst_table_code(example.input)}` | '
        f'`{_myst_table_code(json.dumps(example.expected, ensure_ascii=False))}` |'
        for example in examples
    )
    return [*lines, '']


def render_myst(proposal: Proposal) -> str:
    """Render the canonical proposal as narrative MyST Markdown."""
    lines = [
        '---',
        'title: "my-basis adoption proposal"',
        '---',
        '',
        '# my-basis adoption proposal',
        '',
        f'**Mode:** `{proposal.mode}`  ',
        f'**Disposition:** `{proposal.disposition}`',
        '',
        '## The repository today',
        '',
        proposal.summary.repository_story,
        '',
        '## Adoption thesis',
        '',
        proposal.summary.adoption_thesis,
        '',
        '## Proposed changes',
        '',
    ]
    if not proposal.changes:
        lines.extend(['No source changes are proposed in this round.', ''])
    for change in proposal.changes:
        lines.extend(
            [
                f'({change.id})=',
                f'### {change.title}',
                '',
                f'**Status:** `{change.status}`',
                '',
                change.why,
                '',
                f'**Behavior contract:** {change.behavior_contract}',
                '',
                f'**Risk:** {change.risk}',
                '',
            ]
        )
        if change.basis_apis:
            lines.extend(
                ['**my-basis APIs:** ' + ', '.join(f'`{item}`' for item in change.basis_apis), '']
            )
        if change.files:
            lines.extend(['**Files:** ' + ', '.join(f'`{item}`' for item in change.files), ''])
        if change.tests:
            lines.extend(['**Tests**', '', *[f'- `{item}`' for item in change.tests], ''])
        if change.evidence_refs:
            references = ', '.join(
                f'`{item.path}@{item.sha256[:12]}`'
                + (f' (`{item.signal_id}`)' if item.signal_id else '')
                for item in change.evidence_refs
            )
            lines.extend([f'**Evidence:** {references}', ''])

    regex_changes = [change for change in proposal.changes if change.regexstore]
    lines.extend(['## RegexStore walkthrough', ''])
    if not regex_changes:
        lines.extend(['No RegexStore change is proposed in this round.', ''])
    for change in regex_changes:
        regexstore = change.regexstore
        assert regexstore is not None
        lines.extend(
            [
                f'### {change.title}',
                '',
                f'**Complexity:** `{regexstore.complexity}`',
                '',
                '**Before**',
                '',
                '```python',
                regexstore.before.rstrip(),
                '```',
                '',
                '**RegexStore DSL**',
                '',
                '```python',
                regexstore.dsl_example.rstrip(),
                '```',
                '',
            ]
        )
        lines.extend(_myst_examples('Positive examples', regexstore.positive_examples))
        lines.extend(_myst_examples('Negative examples', regexstore.negative_examples))
        if regexstore.caveats:
            lines.extend(['**Caveats**', '', *[f'- {item}' for item in regexstore.caveats], ''])

    lines.extend(['## What stays unchanged', ''])
    if proposal.summary.deliberate_non_changes:
        lines.extend(f'- {item}' for item in proposal.summary.deliberate_non_changes)
        lines.append('')
    else:
        lines.extend(['No deliberate non-change has been recorded yet.', ''])

    lines.extend(['## Verification and residual risk', ''])
    if proposal.baseline.head:
        lines.extend([f'Baseline revision: `{proposal.baseline.head}`', ''])
    if proposal.baseline.commands:
        lines.extend(
            [
                '**Baseline commands**',
                '',
                *[f'- `{item}`' for item in proposal.baseline.commands],
                '',
            ]
        )
    if proposal.verification:
        lines.extend(
            [
                '| State | Command | Exit | Working directory |',
                '| --- | --- | ---: | --- |',
            ]
        )
        lines.extend(
            f'| `{item.state}` | `{_myst_table_code(item.command)}` | '
            f'{item.exit_code if item.exit_code is not None else "—"} | '
            f'`{_myst_table_code(item.cwd)}` |'
            for item in proposal.verification
        )
        lines.append('')
        for item in proposal.verification:
            if item.output_tail:
                lines.extend(
                    [f'**`{item.command}` output**', '', '```text', item.output_tail, '```', '']
                )
    else:
        lines.extend(['No verification result has been recorded yet.', ''])

    lines.extend(['### Version-control result', ''])
    for label, value in (
        ('Base branch', proposal.vcs.base_branch),
        ('Work branch', proposal.vcs.work_branch),
    ):
        detail = f'`{value}`' if value else 'Not recorded.'
        lines.extend([f'**{label}:** {detail}', ''])
    if proposal.vcs.commits:
        lines.extend(['**Commits**', '', *[f'- `{item}`' for item in proposal.vcs.commits], ''])
    else:
        lines.extend(['**Commits:** None recorded.', ''])
    if proposal.vcs.diff_stat:
        lines.extend(['**Diff stat**', '', '```text', proposal.vcs.diff_stat.rstrip(), '```', ''])
    else:
        lines.extend(['**Diff stat:** Not recorded.', ''])

    lines.extend(['## Merge or apply', '', f'**Handoff:** `{proposal.handoff.merge_kind}`', ''])
    lines.extend(
        f'{index}. `{command}`' for index, command in enumerate(proposal.handoff.merge_commands, 1)
    )
    if proposal.handoff.merge_commands:
        lines.append('')
    else:
        lines.extend(['No merge command is required.', ''])
    review = proposal.handoff.review_url or 'Not recorded.'
    lines.extend([f'**Review:** {review}', ''])

    lines.extend(
        [
            '## Request another round',
            '',
            proposal.handoff.revision_prompt,
            '',
            '## Problem space',
            '',
        ]
    )
    lines.extend(f'- {item}' for item in proposal.problem_space.nodes)
    if proposal.problem_space.nodes:
        lines.append('')
    lines.extend(
        [
            f'**Keystone:** {proposal.problem_space.keystone}',
            '',
            f'**Terminus:** {proposal.problem_space.terminus}',
            '',
        ]
    )
    return '\n'.join(lines).rstrip() + '\n'


def render_html(proposal: Proposal) -> str:
    """Render the canonical proposal as dependency-free standalone HTML."""
    changes: list[str] = []
    regex_sections: list[str] = []
    for change in proposal.changes:
        references = ', '.join(
            f'<code>{escape(item.path)}@{item.sha256[:12]}</code>' for item in change.evidence_refs
        )
        changes.append(
            f'<section id="{escape(change.id)}"><h3>{escape(change.title)}</h3>'
            f'<p><strong>Status:</strong> <code>{escape(change.status)}</code></p>'
            f'<p>{escape(change.why)}</p>'
            f'<p><strong>Behavior contract:</strong> {escape(change.behavior_contract)}</p>'
            f'<p><strong>Risk:</strong> {escape(change.risk)}</p>'
            + (f'<p><strong>Evidence:</strong> {references}</p>' if references else '')
            + '</section>'
        )
        if regexstore := change.regexstore:
            examples: list[str] = []
            for title, values in (
                ('Positive examples', regexstore.positive_examples),
                ('Negative examples', regexstore.negative_examples),
            ):
                if values:
                    rows = ''.join(
                        '<tr>'
                        f'<td><code>{escape(item.input)}</code></td>'
                        f'<td><code>{escape(json.dumps(item.expected, ensure_ascii=False))}</code>'
                        '</td></tr>'
                        for item in values
                    )
                    examples.append(
                        f'<h4>{title}</h4><table><thead><tr><th>Input</th>'
                        f'<th>Expected</th></tr></thead><tbody>{rows}</tbody></table>'
                    )
            caveats = ''.join(f'<li>{escape(item)}</li>' for item in regexstore.caveats)
            regex_sections.append(
                f'<section><h3>{escape(change.title)}</h3>'
                f'<p><strong>Complexity:</strong> <code>{regexstore.complexity}</code></p>'
                '<h4>Before</h4>'
                f'<pre><code>{escape(regexstore.before)}</code></pre>'
                '<h4>RegexStore DSL</h4>'
                f'<pre><code>{escape(regexstore.dsl_example)}</code></pre>'
                + ''.join(examples)
                + (f'<h4>Caveats</h4><ul>{caveats}</ul>' if caveats else '')
                + '</section>'
            )
    if not changes:
        changes.append('<p>No source changes are proposed in this round.</p>')
    if not regex_sections:
        regex_sections.append('<p>No RegexStore change is proposed in this round.</p>')

    non_changes = (
        ''.join(f'<li>{escape(item)}</li>' for item in proposal.summary.deliberate_non_changes)
        or '<li>No deliberate non-change has been recorded yet.</li>'
    )
    verification = (
        ''.join(
            '<tr>'
            f'<td><code>{item.state}</code></td><td><code>{escape(item.command)}</code></td>'
            f'<td>{item.exit_code if item.exit_code is not None else "—"}</td>'
            f'<td><code>{escape(item.cwd)}</code></td></tr>'
            for item in proposal.verification
        )
        or '<tr><td colspan="4">No verification result has been recorded yet.</td></tr>'
    )
    merge = (
        ''.join(f'<li><code>{escape(item)}</code></li>' for item in proposal.handoff.merge_commands)
        or '<li>No merge command is required.</li>'
    )
    nodes = ''.join(f'<li>{escape(item)}</li>' for item in proposal.problem_space.nodes)
    base_branch = (
        f'<code>{escape(proposal.vcs.base_branch)}</code>'
        if proposal.vcs.base_branch
        else 'Not recorded.'
    )
    work_branch = (
        f'<code>{escape(proposal.vcs.work_branch)}</code>'
        if proposal.vcs.work_branch
        else 'Not recorded.'
    )
    commits = (
        ''.join(f'<li><code>{escape(item)}</code></li>' for item in proposal.vcs.commits)
        or '<li>None recorded.</li>'
    )
    diff_stat = (
        f'<pre><code>{escape(proposal.vcs.diff_stat)}</code></pre>'
        if proposal.vcs.diff_stat
        else '<p>Not recorded.</p>'
    )
    review = (
        f'<code>{escape(proposal.handoff.review_url)}</code>'
        if proposal.handoff.review_url
        else 'Not recorded.'
    )
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>my-basis adoption proposal</title>'
        '<style>body{font:18px/1.55 system-ui;max-width:74ch;margin:4rem auto;padding:0 1rem;'
        'color:#20242b}code,pre{background:#f2f4f7}pre{padding:1rem;overflow:auto}'
        'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd1d8;'
        'padding:.5rem;text-align:left}</style></head><body>'
        '<h1>my-basis adoption proposal</h1>'
        f'<p><strong>Mode:</strong> <code>{proposal.mode}</code>; '
        f'<strong>Disposition:</strong> <code>{proposal.disposition}</code></p>'
        f'<h2>The repository today</h2><p>{escape(proposal.summary.repository_story)}</p>'
        f'<h2>Adoption thesis</h2><p>{escape(proposal.summary.adoption_thesis)}</p>'
        '<h2>Proposed changes</h2>'
        + ''.join(changes)
        + '<h2>RegexStore walkthrough</h2>'
        + ''.join(regex_sections)
        + f'<h2>What stays unchanged</h2><ul>{non_changes}</ul>'
        + '<h2>Verification and residual risk</h2><table><thead><tr><th>State</th>'
        + '<th>Command</th><th>Exit</th><th>Working directory</th></tr></thead><tbody>'
        + verification
        + '</tbody></table><h3>Version-control result</h3>'
        + f'<p><strong>Base branch:</strong> {base_branch}</p>'
        + f'<p><strong>Work branch:</strong> {work_branch}</p>'
        + f'<p><strong>Commits:</strong></p><ul>{commits}</ul>'
        + f'<p><strong>Diff stat:</strong></p>{diff_stat}'
        + '<h2>Merge or apply</h2>'
        + f'<p><strong>Handoff:</strong> <code>{proposal.handoff.merge_kind}</code></p>'
        + f'<ol>{merge}</ol><p><strong>Review:</strong> {review}</p>'
        + '<h2>Request another round</h2>'
        + f'<p>{escape(proposal.handoff.revision_prompt)}</p><h2>Problem space</h2><ul>{nodes}</ul>'
        + f'<p><strong>Keystone:</strong> {escape(proposal.problem_space.keystone)}</p>'
        + f'<p><strong>Terminus:</strong> {escape(proposal.problem_space.terminus)}</p>'
        + '</body></html>\n'
    )


def _typst_string(value: str) -> str:
    """Escape a value for a Typst string literal."""
    return (
        value.replace('\\', '\\\\')
        .replace('"', '\\"')
        .replace('\n', '\\n')
        .replace('\r', '\\r')
        .replace('\t', '\\t')
    )


def _typst_text(value: str) -> str:
    """Render arbitrary prose as inert Typst text."""
    return f'#text("{_typst_string(value)}")'


def _typst_raw(value: str, *, lang: str | None = None, block: bool = False) -> str:
    """Render code or a command through a safe Typst string literal."""
    arguments = [f'"{_typst_string(value)}"']
    if lang:
        arguments.append(f'lang: "{_typst_string(lang)}"')
    if block:
        arguments.append('block: true')
    return f'#raw({", ".join(arguments)})'


def _typst_label(value: str) -> str:
    """Return a conservative Typst label identifier."""
    return re.sub(r'[^a-z0-9_-]+', '-', value.lower()).strip('-') or 'change'


def render_typst(proposal: Proposal) -> str:
    """Render the canonical proposal as standalone Typst source."""
    lines = [
        '#set page(margin: 1in)',
        '#set text(font: "Libertinus Serif", size: 11pt)',
        '#set heading(numbering: "1.")',
        '= my-basis adoption proposal',
        '',
        f'*Mode:* {_typst_raw(proposal.mode)}  \\ ',
        f'*Disposition:* {_typst_raw(proposal.disposition)}',
        '',
        '== The repository today',
        '',
        _typst_text(proposal.summary.repository_story),
        '',
        '== Adoption thesis',
        '',
        _typst_text(proposal.summary.adoption_thesis),
        '',
        '== Proposed changes',
        '',
    ]
    if not proposal.changes:
        lines.extend(['No source changes are proposed in this round.', ''])
    for change in proposal.changes:
        lines.extend(
            [
                f'=== {_typst_text(change.title)} <{_typst_label(change.id)}>',
                '',
                f'*Status:* {_typst_raw(change.status)}',
                '',
                _typst_text(change.why),
                '',
                f'*Behavior contract:* {_typst_text(change.behavior_contract)}',
                '',
                f'*Risk:* {_typst_text(change.risk)}',
                '',
            ]
        )
        if change.basis_apis:
            lines.extend(
                [
                    '*my-basis APIs:* ' + ', '.join(_typst_raw(item) for item in change.basis_apis),
                    '',
                ]
            )
        if change.files:
            lines.extend(['*Files:* ' + ', '.join(_typst_raw(item) for item in change.files), ''])
        if change.tests:
            lines.extend(['*Tests*', '', *[f'- {_typst_raw(item)}' for item in change.tests], ''])
        if change.evidence_refs:
            references: list[str] = []
            for item in change.evidence_refs:
                reference = f'{item.path}@{item.sha256[:12]}'
                if item.signal_id:
                    reference += f' ({item.signal_id})'
                references.append(_typst_raw(reference))
            lines.extend([f'*Evidence:* {", ".join(references)}', ''])

    regex_changes = [change for change in proposal.changes if change.regexstore]
    lines.extend(['== RegexStore walkthrough', ''])
    if not regex_changes:
        lines.extend(['No RegexStore change is proposed in this round.', ''])
    for change in regex_changes:
        regexstore = change.regexstore
        assert regexstore is not None
        lines.extend(
            [
                f'=== {_typst_text(change.title)}',
                '',
                f'*Complexity:* {_typst_raw(regexstore.complexity)}',
                '',
                '*Before*',
                '',
                _typst_raw(regexstore.before, lang='python', block=True),
                '',
                '*RegexStore DSL*',
                '',
                _typst_raw(regexstore.dsl_example, lang='python', block=True),
                '',
            ]
        )
        for title, examples in (
            ('Positive examples', regexstore.positive_examples),
            ('Negative examples', regexstore.negative_examples),
        ):
            if examples:
                lines.extend([f'*{title}*', ''])
                lines.extend(
                    f'- {_typst_raw(item.input)} -> '
                    f'{_typst_raw(json.dumps(item.expected, ensure_ascii=False))}'
                    for item in examples
                )
                lines.append('')
        if regexstore.caveats:
            lines.extend(
                ['*Caveats*', '', *[f'- {_typst_text(item)}' for item in regexstore.caveats], '']
            )

    lines.extend(['== What stays unchanged', ''])
    lines.extend(f'- {_typst_text(item)}' for item in proposal.summary.deliberate_non_changes)
    if not proposal.summary.deliberate_non_changes:
        lines.extend(['No deliberate non-change has been recorded yet.', ''])
    else:
        lines.append('')

    lines.extend(['== Verification and residual risk', ''])
    if proposal.baseline.head:
        lines.extend([f'Baseline revision: {_typst_raw(proposal.baseline.head)}', ''])
    if proposal.baseline.commands:
        lines.extend(
            [
                '*Baseline commands*',
                '',
                *[f'- {_typst_raw(item)}' for item in proposal.baseline.commands],
                '',
            ]
        )
    for item in proposal.verification:
        exit_code = item.exit_code if item.exit_code is not None else 'unavailable'
        lines.append(
            f'- {_typst_raw(item.state)}: {_typst_raw(item.command)} '
            f'(exit {exit_code}, {_typst_raw(item.cwd)})'
        )
        if item.output_tail:
            lines.extend(['', '*Output*', '', _typst_raw(item.output_tail, block=True)])
    if not proposal.verification:
        lines.extend(['No verification result has been recorded yet.', ''])
    else:
        lines.append('')

    lines.extend(['=== Version-control result', ''])
    for label, value in (
        ('Base branch', proposal.vcs.base_branch),
        ('Work branch', proposal.vcs.work_branch),
    ):
        detail = _typst_raw(value) if value else 'Not recorded.'
        lines.extend([f'*{label}:* {detail}', ''])
    if proposal.vcs.commits:
        lines.extend(
            ['*Commits*', '', *[f'- {_typst_raw(item)}' for item in proposal.vcs.commits], '']
        )
    else:
        lines.extend(['*Commits:* None recorded.', ''])
    if proposal.vcs.diff_stat:
        lines.extend(['*Diff stat*', '', _typst_raw(proposal.vcs.diff_stat, block=True), ''])
    else:
        lines.extend(['*Diff stat:* Not recorded.', ''])

    lines.extend(
        [
            '== Merge or apply',
            '',
            f'*Handoff:* {_typst_raw(proposal.handoff.merge_kind)}',
            '',
        ]
    )
    lines.extend(f'+ {_typst_raw(item)}' for item in proposal.handoff.merge_commands)
    if proposal.handoff.merge_commands:
        lines.append('')
    else:
        lines.extend(['No merge command is required.', ''])
    review = (
        _typst_raw(proposal.handoff.review_url) if proposal.handoff.review_url else 'Not recorded.'
    )
    lines.extend(
        [
            f'*Review:* {review}',
            '',
            '== Request another round',
            '',
            _typst_text(proposal.handoff.revision_prompt),
            '',
            '== Problem space',
            '',
        ]
    )
    lines.extend(f'- {_typst_text(item)}' for item in proposal.problem_space.nodes)
    if proposal.problem_space.nodes:
        lines.append('')
    lines.extend(
        [
            f'*Keystone:* {_typst_text(proposal.problem_space.keystone)}',
            '',
            f'*Terminus:* {_typst_text(proposal.problem_space.terminus)}',
            '',
        ]
    )
    return '\n'.join(lines).rstrip() + '\n'


def validation_error_text(error: pyd.ValidationError | ProposalValidationError) -> str:
    """Render structural and evidence validation failures without a traceback."""
    if isinstance(error, ProposalValidationError):
        return '\n'.join(f'- {item}' for item in error.errors)
    return '\n'.join(
        f'- {".".join(str(part) for part in item["loc"])}: {item["msg"]}' for item in error.errors()
    )
