---
title: my-basis 1.0 readiness handoff
date: 2026-07-23
genre: reference
sid: MEMY-754
---

# my-basis 1.0 readiness handoff

This is the maintainer-facing account of the final pre-1.0 campaign. It is meant
to answer three questions without requiring a tour through the implementation:

1. Is the Basis change itself ready to merge?
2. What did applying Basis across the public Python fleet teach us?
3. What remains a human release decision rather than an engineering task?

> **Disposition:** the campaign has a coherent merge shape, and every local 1.0
> engineering gate is green. Do not cut `v1.0.0` from this document alone.
> Merge only after the submitted GitLab pipeline is green and the maintainer has
> authored the 1.0 stability promise.

## Executive disposition

The work supports merging the Basis branch once its final integrated gates are
green. It does **not** claim that 1.0 has been released, tagged, or published.
PyPI still reports `0.8.4` as the latest public release; there was no `0.9.0`
tag or publication. The current work therefore remains an unreleased candidate,
not a retroactive release claim.

The three requested outcomes have the following disposition:

| Area                              | Disposition                                                                  | What the maintainer is approving                                                                                                                                                                                                |
| --------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Test authorship and style         | Ready; integrated local proof is green                                       | A deterministic audit plus a broad normalization toward parameter tables, ordinary-sized names, and no test-name depth beyond `test_name__scenario`.                                                                            |
| Fleet adoption and reusable skill | Complete as a decision pass; two downstream drafts remain intentionally open | Every canonical public Python repository received an evidence-backed disposition. The resulting scanner, proposal contract, report renderer, and packaged skill turn that judgment process into a repeatable beginner workflow. |
| `typst-basis` fold                | Folded on the candidate at `c63d6eed`                                        | Its complete Git history now lives under top-level `typst/`, while its license, version, tags, installation, tests, and release lifecycle remain independent from the Python distribution.                                      |

The campaign deliberately did not maximize use of Basis. Five of the nine
repositories were declined, deferred, or left as already-adopted because their
Python floor, zero-dependency promise, failure-path constraints, or lack of a
coherent replacement outweighed any code reduction. That restraint is part of
the 1.0 result.

## What changed

### Tests: house style became an enforceable contract

The test pass preserves behavior while moving scenario variation into
parameter tables. Long names were not mechanically shortened at the expense of
meaning; repeated arrangements became rows with readable IDs, and the remaining
two-level names identify a genuinely different subtype or failure mode.

The new deterministic audit treats the following as objective failures:

- a test name deeper than `test_name__scenario`;
- invalid Python syntax;
- parameter row arity that does not match the declared arguments;
- literal parameter ID counts that do not match the rows;
- `Test*` classes made uncollectable by `__init__` or `__new__`; and
- collection hazards that would let a style report look green while tests were
  silently absent.

The audit also reports suite-wide shape: files, functions, parameterized
functions, and represented cases. It is a guardrail, not a demand that every
test be parameterized. A single focused behavior remains a single focused test.

### The library: tests exposed contract defects worth fixing before 1.0

The review was not merely editorial. Consolidating the tests made several
public contracts legible enough to repair:

- **Regex composition** now preserves compiled flags across construction,
  assignment, import, and union; rejects lossy reuse of externally flagged
  dependencies; forwards the unattended-processing timeout through
  substitution; and keeps router priority ordered and testable.
- **Runtime typing** now treats Predicate string leaves, enum normalization,
  sparse defaults, polarity, late cast registration, and declined coercions
  explicitly instead of relying on incidental behavior.
- **Files and persistence** now preserve concatenated content, cache indexes,
  headerless Markdown, nested notes, newline boundaries, and the historical
  Buffer behavior while offering an explicit fence-replacement path.
- **Filesystem parsing** rejects ambiguous URI, UNC, drive-root, and
  authority-like forms rather than manufacturing plausible paths, and states
  its supported non-root POSIX grammar explicitly.
- **Utility edges** around fenced YAML, UTC/epoch dates, package resolution,
  metric setup, and semantic width calculations now have compact,
  parameterized regression coverage.

These are stability fixes, not a redesign of the public surface. Their common
theme is that provenance, boundaries, flags, and persistence should survive a
round trip or fail loudly.

### Adoption tooling: a beginner can produce evidence before asking for judgment

The package now carries an `adopt-my-basis` skill and exposes the
`my-basis-adopt` command. A beginner can discover or export the skill and build
an intake without installing a permanent development environment:

```sh
uvx --from my-basis my-basis-adopt skill path
uvx --from my-basis my-basis-adopt skill export .agents/skills/adopt-my-basis
uvx --from my-basis my-basis-adopt prepare .
```

`prepare` inventories the repository without importing or executing its
package. It avoids secret-like inputs, virtual environments, generated and
vendor trees, oversized files, and symlinks that escape the repository. Its
regex findings and candidate native gates are explicitly leads for an agent to
confirm, not self-authorizing refactors.

The resulting proposal contract binds a report to the canonical SHA-256 of one
exact intake. Proposed and implemented changes cite complete-file evidence;
implemented claims require implementation mode and an honest verification
result. Stale or mismatched evidence fails validation. Stable change IDs let a
maintainer accept most of a proposal while requesting another round for only a
few items.

The same proposal can be rendered as MyST Markdown, standalone HTML, or Typst
source and PDF:

```sh
my-basis-adopt validate .basis-adoption/proposal.json
my-basis-adopt render .basis-adoption/proposal.json --format myst
my-basis-adopt render .basis-adoption/proposal.json --format html
my-basis-adopt render .basis-adoption/proposal.json --format typst --build
```

The report leads with the repository story, adoption thesis, deliberate
non-changes, verification, and merge or revision handoff. File inventories and
logs belong in appendices. The tool can render evidence; it cannot decide that a
dependency belongs on a latency-sensitive hook or zero-dependency core.

### Typst: one repository, two deliberately separate products

Folding `typst-basis` into this repository is the lower-maintenance topology.
The prepared history import preserves its four source commits, relocates it to
top-level `typst/`, and adds the boundary material needed for life inside a
monorepo:

- nested MIT licensing for `@dtm/basis`;
- its own `typst.toml` version;
- POSIX `install.sh` and hermetic `test.sh`;
- compile fixtures for the components and report envelope;
- `typst-vX.Y.Z` tags rather than Python's bare `vX.Y.Z`; and
- explicit exclusion from Python wheels and source distributions.

The source repository head being preserved is
`fc46f3700af5415db0692f30bc955df361638aee`. The recovery bundle is
`/home/robbd/ai/artifacts/typst-basis-fc46f370.bundle`, with SHA-256
`1548bd0050fe4a6681de85d294cc5064fc324b36972e08dea599905bf5023370`.
The prepared relocation and boundary commits are `8ee77b2` and `4656775`.
The history merge entered Basis as
`c63d6eed41b9a490d43cfce6f3b180b0ab1f9275`.

The old checkout should remain in place until the Basis merge, package
installation, and downstream Corpus gate all succeed. History preservation is
the safety net; a hurried directory copy followed by deletion is not.

## Fleet dispositions

The canonical pass covered these nine public Python repositories. “No change”
is a result when it protects a deliberate compatibility or dependency
boundary.

| Repository        | Disposition            | Result and rationale                                                                                                                                                                                        | Review surface                                                                                                       |
| ----------------- | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `tact`            | Decline                | Its runtime core deliberately has zero dependencies. The apparent complex-regex sites were an isolated hunk-header parser and a test-only secret matcher, not a shared production grammar.                  | No MR; repository remained clean.                                                                                    |
| `irix`            | Already adopted        | Basis is already present. The only complex-looking regex was a local environment-placeholder lookbehind, so no RegexStore expansion earned its cost. Refresh the stale lock only after 1.0 exists.          | No MR; repository remained clean.                                                                                    |
| `means`           | Implemented and merged | Centralized `MEANS_DIR` and replaced the repeated fenced-YAML extraction with a tested RegexStore grammar. Native evaluation and all 401 tests passed.                                                      | [MR !5](https://gitlab.com/doering-ai/apps/means/-/merge_requests/5), commits `ad4ba61` and `aadec529`.              |
| `piq`             | Decline for this round | Its Python 3.11 floor is below Basis's deliberate 3.12 floor. Adding Basis would silently change a product contract; its isolated regex calls do not justify that decision.                                 | No MR; rendered decline proposal produced.                                                                           |
| `myform`          | Implemented and merged | Removed local regex helper duplication by adopting the existing Basis utility aliases. Ruff, Pyrefly, and all 4,353 tests passed.                                                                           | [MR !5](https://gitlab.com/doering-ai/libs/myform/-/merge_requests/5), commit `557ff2a7`.                            |
| `wikiparse`       | Implemented as a draft | Exercised its large existing RegexStore grammar against the candidate Buffer behavior. The controlled run reached 1,996 passing and 9 expected failures; 3 unrelated failures remain outside this refactor. | [Draft MR !2](https://gitlab.com/doering-ai/apps/wikiparse/-/merge_requests/2), commit `13287b1`; merge after Basis. |
| `superheavy-gate` | Decline                | It supports Python 3.11 and its failure hook is deliberately standard-library-only. A dependency in the path that decides whether heavy model use is allowed would invert that reliability contract.        | No MR; repository remained clean.                                                                                    |
| `arch`            | Implemented as a draft | Reused Basis where document and assay grammars already meet RegexStore. The focused 41-test slice passed; the broader run passed 966 tests after separating 3 known stale defects.                          | [Draft MR !2](https://gitlab.com/doering-ai/libs/arch/-/merge_requests/2), commit `7252d68`; merge after Basis.      |
| `model`           | Reference adopter      | It already demonstrates the intended Basis and RegexStore relationship. Five unrelated regex calls did not form another grammar worth consolidating. Refresh its `0.8.1` lock only after 1.0.               | No MR; repository remained clean.                                                                                    |

Two supporting Corpus changes sit outside the nine-repository disposition
matrix:

- [Corpus MR !47](https://gitlab.com/doering-ai/libs/corpus/-/merge_requests/47)
  fixed a RegexStore-backed Markdown fence backreference and is merged at
  `06190f67`.
- [Draft Corpus MR !46](https://gitlab.com/doering-ai/libs/corpus/-/merge_requests/46)
  changes the downstream `@dtm/basis` integration seam to the new monorepo
  location. It must follow, not precede, the Basis fold.

## RegexStore DSL walkthrough

RegexStore is valuable when patterns form a vocabulary: reusable pieces, a
grammar, a router, a recursive structure, or a repeated transform. One obvious
`re.compile` should stay one obvious `re.compile`.

The examples below are executable against this candidate. Each uses
`lazy_load=False` so a malformed production grammar fails at construction
rather than on its first user input.

### Exact composition and repeated captures

Lists normally use an optional-space separator. Set `separator=''` when every
character is part of the grammar:

```python
from my import RegexStore

TOKEN_RGXS = RegexStore.new(
    options=dict(separator='', lazy_load=False),
    sign=r'[+-]?',
    digits=r'\d+',
    number=r'(?P<value>(?P>sign)(?P>digits)(?:\.(?P>digits))?)',
)

match = TOKEN_RGXS.fullmatch('number', '-22.5')
assert match['value'] == ['-22.5']
assert match.data['digits'] == ['22', '5']
assert match.flat == {
    'sign': '-',
    'digits': '5',
    'value': '-22.5',
}
```

`MatchData` keeps all repeated named captures as lists. Its `flat` view selects
the last non-empty capture, which is convenient but should not replace
`match.data` when repetition matters.

### Named subroutine is not a backreference

These two constructs answer different questions:

- `(?P>word)` runs the named pattern again and may match different text.
- `\g<word>` matches the exact text captured previously.

```python
from my import RegexStore

PAIRS = RegexStore.new(
    options=dict(separator='', lazy_load=False),
    same_shape=r'(?P<word>[a-z]+):(?P>word)',
    same_text=r'(?P<word>[a-z]+):\g<word>',
)

assert PAIRS.fullmatch('same_shape', 'cat:dog')
assert PAIRS.fullmatch('same_text', 'cat:cat')
assert not PAIRS.fullmatch('same_text', 'cat:dog')
```

This distinction is especially important because the default
`force_reinvocations=True` behavior normalizes `(?P=word)` as a subroutine
invocation. Use `\g<word>` when equality with the earlier capture is the actual
contract. The Corpus fence fix is the practical version of this lesson: the
closing fence must repeat the opening delimiter, not merely match the delimiter
grammar again.

### Flags must travel with reusable definitions

A compiled pattern's flags are preserved while that pattern stands alone,
including through store import and union. Those compile-time flags cannot be
embedded into a larger pattern's source, so RegexStore now refuses a composed
dependency that would silently lose them.

Put reusable flags inside the definition:

```python
from my import RegexStore

WORDS = RegexStore.new(
    options=dict(separator='', lazy_load=False),
    word=r'(?i:publish|published|publishing)',
    command=r'\b(?P>word)\b',
)

assert WORDS.fullmatch('command', 'PUBLISHING')
assert not WORDS.fullmatch('command', 'publisher')
```

For a standalone imported `regex.Pattern`, external flags are fine. For a
definition referenced by `(?P>name)`, use scoped inline flags such as
`(?i:...)`. Supplying both a compiled pattern and another `flags=` value is
ambiguous and fails loudly.

### Substitution inherits the unattended-processing timeout

`sub` and `subn` route replacement through the same store-wide regex deadline
as the other public matching operations. The caller does not add a separate
`timeout=` argument:

```python
from my import RegexStore

CLEANUP = RegexStore.new(
    options=dict(separator='', lazy_load=False),
    horizontal_space=r'[ \t]+',
)

assert CLEANUP.sub(
    'horizontal_space',
    ' ',
    'alpha\t beta   gamma',
) == 'alpha beta gamma'

assert CLEANUP.subn(
    'horizontal_space',
    ' ',
    'alpha\t beta   gamma',
) == ('alpha beta gamma', 2)
```

The timeout is a containment boundary, not a proof that a hostile pattern is
safe. Security-sensitive patterns should still be eagerly compiled, exercised
against adversarially long inputs, and kept as simple as the behavior permits.

### Router order is public behavior

Router mappings are ordered. When categories overlap, the first matching branch
wins:

```python
from my import RegexStore

TOKENS = RegexStore.new(options=dict(separator='', lazy_load=False))
TOKENS.define_router_tree(
    'token',
    {
        'integer': r'\d+',
        'wordish': r'\w+',
    },
)

assert TOKENS.route_match('token', '42') == 'integer'
assert TOKENS.route_match('token', 'alpha_2') == 'wordish'
assert TOKENS.route_match('token', '+foo') == ''
```

Reversing those two mapping entries classifies `'42'` as `wordish`. Router
tests therefore need an overlap example, not only disjoint happy paths.
Routers deliberately use ordinary ordered alternation: optimized atomic
condensation can change the meaning of lazy or overlapping branches.

### The compact DSL vocabulary

- `(':', children)` makes a non-capturing group, keeping a composed sequence together.
- `('|:', children)` makes an ordered non-capturing alternation for classifications where branch priority matters.
- `('|:i', children)` makes a case-insensitive ordered alternation for small vocabularies.
- `('<|>', children)` makes an optimized atomic alternation; use it for measured grammars whose boundaries have golden tests.
- `(mark, prefix, children, suffix)` wraps a marked group in exact text for anchored or delimited fragments.
- `(?P>name)` invokes a named definition again, reusing the shape of a grammar piece.
- `\g<name>` matches a prior capture's exact text, as required by paired delimiters and equality constraints.

Before accepting a complex RegexStore change, ask:

1. Is it truly a grammar rather than a long isolated expression?
2. Are literal vocabularies escaped?
3. Are boundaries and anchors unchanged?
4. Are flags scoped where they can survive reuse?
5. Is every subroutine or backreference intentional?
6. Do public operations keep the timeout boundary?
7. Do differential tests cover positives, negatives, near misses, malformed
   inputs, overlaps, and length boundaries?

## Independent Python and Typst release boundaries

The monorepo removes a repository without pretending the two packages are one
artifact.

| Concern        | Python `my-basis`                                      | Typst `@dtm/basis`                                                            |
| -------------- | ------------------------------------------------------ | ----------------------------------------------------------------------------- |
| Source root    | `my/` and Python project files at repository root      | `typst/`                                                                      |
| License        | MPL-2.0                                                | Nested MIT `typst/LICENSE`                                                    |
| Version source | Root `pyproject.toml`                                  | `typst/typst.toml`                                                            |
| Tag namespace  | Bare `vX.Y.Z`                                          | `typst-vX.Y.Z`                                                                |
| Distribution   | PyPI wheel and source distribution                     | Local Typst package tree under `dtm/basis/<version>`                          |
| Installation   | `pip`, `uv`, or `uvx`                                  | `typst/install.sh` symlink for development or `--copy` for a release snapshot |
| Verification   | Python eval, test matrix, docs, wheel/sdist inspection | `typst/test.sh`, fixture compilation, and envelope query                      |
| Release gate   | Protected, manual PyPI job after a signed matching tag | Independent tag and package installation; never triggers PyPI                 |

The Python build checker must prove both halves of the packaging promise:

- no `typst/` member appears in either the wheel or source distribution; and
- every source-controlled file in `my/skills/adopt-my-basis/` is present in both
  Python artifacts.

That keeps a Typst checkout from inflating the Python package while ensuring the
new agent workflow actually ships to Python users.

## Verification ledger

Local proof is literal below. The submitted review and its exact-source pipeline
are explicit pre-merge gates, not soft passes.

| Surface                        | Command or evidence                                                                                                   | Status                                                                                                                                                                                                                     |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Lock integrity                 | `uv lock --check`                                                                                                     | Passed; 137 packages resolved from the existing lock.                                                                                                                                                                      |
| Lint, format, and typing       | `task eval`                                                                                                           | Passed; Pyrefly and both Ruff gates were clean, with 133 files already formatted.                                                                                                                                          |
| Test-style contract            | `task test:audit`                                                                                                     | Passed; 49 files, 966 functions, 441 parameterized functions, at least 2,782 cases, maximum depth 2, 0 diagnostics, and 0 violations.                                                                                      |
| Full Python suite              | `task test -- -q`                                                                                                     | Passed; 4,165 tests, 21 subtests, and 2 snapshots in 9.59 seconds, with no warnings.                                                                                                                                       |
| Python 3.12 dependency floor   | `task test:floor`                                                                                                     | Passed; the same 4,165 tests, 21 subtests, and 2 snapshots on CPython 3.12.13, Pydantic 2.12.2, and PyTest 9.0.0 in 8.91 seconds.                                                                                          |
| Documentation                  | `task docs`                                                                                                           | Passed warning-free; all eight packages were current and the Sphinx build was up to date.                                                                                                                                  |
| Packaged skill structure       | skill-creator `quick_validate.py my/skills/adopt-my-basis`                                                            | Passed: `Skill is valid!`; README/skill/reference mdformat checks and packaged CLI help/path also passed.                                                                                                                  |
| Adoption CLI                   | prepare, refresh, validate, and all render modes from a clean external output directory                               | Passed through 96 adoption tests and live prepare/validate/render smokes; the hardening smoke built a 33,500-byte PDF, and the final fleet pass rendered both PDF and HTML.                                                |
| Final fleet scanner regression | all nine canonical public Python repositories                                                                         | Passed; 9 prepares plus 9 live-freshness validations, identical before/after fingerprints, no surviving scanner defect. Ledger: `/home/robbd/ai/artifacts/memy-754-adoption-dogfood-final/findings.md` (`ee68a044…e4b21`). |
| Python artifact boundary       | `uv build --no-sources`, then `scripts/check_release_artifacts.py` over wheel and sdist                               | Passed; wheel 122 members, sdist 119 members, all 7 skill files in both, and no `typst/` leakage.                                                                                                                          |
| Integrated Typst package       | `typst/test.sh` from the merged Basis tree                                                                            | Passed compile and envelope gates locally and in the pinned official Typst 0.15.1 container; only documented fallback-font warnings appeared.                                                                              |
| GitLab Basis pipeline          | [pipeline 2701834857](https://gitlab.com/doering-ai/libs/basis/-/pipelines/2701834857), exact source `a0399ad`        | Running at handoff; merge is prohibited until the exact submitted source is green.                                                                                                                                         |
| Basis review surface           | [Basis MR !6](https://gitlab.com/doering-ai/libs/basis/-/merge_requests/6)                                            | Open and reviewable; the maintainer-owned dirty primary checkout remains intentionally untouched.                                                                                                                          |
| Initial scanner dogfood        | nine repositories, four artifacts each, zero parse errors, untouched proposal freshness valid, all target trees clean | Passed before hardening and superseded by the final clean-fingerprint pass above.                                                                                                                                          |
| Prepared Typst import          | `test.sh` under Typst 0.15.1, `typstyle 0.15 --check`, and the pinned official Typst container                        | Passed in the isolated import checkout and again from the merged Basis tree.                                                                                                                                               |
| Myform adoption                | Ruff, Pyrefly, and 4,353 tests                                                                                        | Passed and merged in MR !5.                                                                                                                                                                                                |
| Means adoption                 | native evaluation and 401 tests                                                                                       | Passed and merged in MR !5.                                                                                                                                                                                                |
| WikiParse draft                | controlled candidate run                                                                                              | 1,996 passed, 9 xfailed, 3 unrelated failures; remains draft.                                                                                                                                                              |
| Arch draft                     | focused and separated broader runs                                                                                    | 41 focused passed; 966 broader tests passed with 3 known stale defects separated; remains draft.                                                                                                                           |

## Merge or request another round

### Merge sequence

Use this order. It prevents downstream repositories from depending on a path or
behavior that has not landed.

1. **Close the Basis proof.** Submit the branch, record its review surface, and
   require the exact merge-request pipeline to pass. Review the branch
   `agent/MEMY-754-prepare-my-basis-for-1-0-through-fleet-dogfoodin` and the Basis
   MR recorded above. If the advisor is unavailable, preserve the exact manual
   diff review and bypass reason; unavailability is not approval.

2. **Protect the operator's local state.** As of this handoff, the primary Basis
   checkout contains maintainer-owned version and README work. Do not merge over
   it or discard it. Prefer the reviewable GitLab MR; only update the primary
   checkout after its local work has been reconciled and
   `git status --short --branch` is understood.

3. **Merge Basis first.** Require a green Basis pipeline and human review. Verify
   that `3de1fd7` and `fc46f37` remain ancestors of the merged Typst history and
   that `git log --follow -- typst/` shows the imported provenance.

4. **Repoint the local Typst package.** From the updated Basis checkout, run:

   ```sh
   /home/robbd/my/libs/basis/typst/install.sh
   readlink -f /home/robbd/.local/share/typst/packages/dtm/basis/0.1.0
   ```

   The second command must resolve beneath
   `/home/robbd/my/libs/basis/typst`, not the old `typst-basis` checkout.

5. **Land the consumer seam.** Rebase and merge
   [Corpus MR !46](https://gitlab.com/doering-ai/libs/corpus/-/merge_requests/46)
   only after the new package path resolves and its downstream Typst integration
   gate passes.

6. **Finish dependent adoption drafts.** Rebase and reverify Arch MR !2 and
   WikiParse MR !2 against the landed Basis contract. Keep them draft if their
   three unrelated stale failures are not cleanly separated from the proposed
   change.

7. **Refresh existing adopters after release.** Update the stale irix and model
   locks only when `my-basis==1.0.0` is actually available. Do not encode a
   fictional 1.0 source beforehand.

8. **Retire the old Typst checkout last.** Keep the verified recovery bundle.
   Delete or archive `/home/robbd/my/libs/typst-basis` only after the installed
   package target and Corpus consumer proof both point at Basis.

### The human 1.0 gate

No agent should manufacture the social guarantee implied by 1.0. After the merge
sequence above, the maintainer must:

1. author and approve the explicit public-API stability promise;
2. approve the final changelog and the root `1.0.0` version/lock change;
3. verify that the signed bare tag matches the packaged Python version;
4. push signed `v1.0.0`; and
5. manually approve the protected `Publish PyPI` job.

The manual job uploads; it is not permission for an agent to publish early.
A future `typst-v0.1.0` tag is independent and must not activate the PyPI path.

### Request another round

Use the following prompt and name only the areas being reopened:

```text
Resume MEMY-754 from RELEASE-1.0-HANDOFF.md.
Preserve the accepted results in tests, core-library, adoption-skill,
fleet-dispositions, and typst-boundary.
Revise these areas only: <area names and requested changes>.
Keep existing stable proposal change IDs, refresh any intake whose evidence
changed, rerun every affected native gate plus the final Basis gates, and
regenerate the MyST/Typst handoff with refreshed literal evidence.
Do not tag, publish, or author the maintainer's 1.0 stability promise.
```

For a single downstream proposal, use its stable change IDs:

```text
Use $adopt-my-basis with intake <path> and proposal <path>.
Preserve accepted change IDs. Revise basis-003 and basis-006 as follows:
<request>. Rerun affected gates, refresh stale evidence, and regenerate the
report.
```

## Infrastructure limitations

The work proceeded with local evidence when coordination services were
unreliable:

- Plane lookups returned the known modality/404 failure. `MEMY-754.md` remains
  the local collaboration record; no direct gated Plane push was used.
- The merge advisor returned provider errors for bounded downstream changes.
  Myform, Means, and the Corpus regex fix were manually reviewed with explicit,
  recorded operator-authorized bypass reasons. A provider error was never
  recorded as a passing review.
- The Read the Docs site remains provisioned-but-pending, so the repository
  documentation build is the authoritative documentation gate.
- The final Basis MR and pipeline remain explicit remote gates because they can
  only describe the submitted source state. The integrated local counts are
  recorded above.

None of these limitations justifies weakening the local verification contract.
They explain why the branch, commits, rendered artifacts, and command results are
the durable handoff.

## Problem space

- **★ Keystone — close the exact-source proof and merge Basis before any dependent
  draft.**
  - Record the submitted review surface and require its exact pipeline to pass.
  - Confirm the imported Typst ancestry and Python artifact exclusion together.
  - Preserve the maintainer's dirty primary checkout until its work is reconciled.
- Complete the downstream circulation.
  - Repoint and verify the local `@dtm/basis` package.
  - Merge the Corpus path seam.
  - Rebase and decide the Arch and WikiParse drafts.
- Make the new skill earn trust after release.
  - Refresh irix and model against the real 1.0 package.
  - Collect false positives and misses from future adopters as detector fixtures.
  - Keep dependency and failure-path declines as first-class successful outcomes.
- Keep the two release lines independent.
  - Bare Python tags control protected PyPI publication.
  - `typst-v*` tags control only the house Typst package.
  - Retain the imported source bundle until all consumers have crossed the seam.

**Terminus:** MEMY-754 ends when the Basis MR is merged with literal final proof,
the Typst package resolves from the monorepo and passes its downstream Corpus
gate, every fleet repository has the disposition recorded above, and the
maintainer has either cut 1.0 or explicitly deferred the human stability promise.
Later adoption findings belong to their own repository tasks; they do not keep
this campaign artificially open.
