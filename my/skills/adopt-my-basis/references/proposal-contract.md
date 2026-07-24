# Adoption proposal contract

The machine-readable proposal is
`my-basis-adoption/proposal/v1`. It references one exact intake by SHA-256 and
contains stable change IDs.

## Intake linkage

`intake_sha256` is the SHA-256 of the parsed intake model's canonical JSON bytes:

```python
payload = json.dumps(
    intake.model_dump(mode='json'),
    ensure_ascii=False,
    separators=(',', ':'),
    sort_keys=True,
).encode()
intake_sha256 = hashlib.sha256(payload).hexdigest()
```

It is not `intake.source_digest`, the digest of the pretty-printed `intake.json`
file, or a digest of its original source tree.

## Required shape

```text
schema_version
intake_sha256
mode: propose | implement
disposition: adopt | partial | already-adopted | decline | blocked
summary:
  repository_story
  adoption_thesis
  deliberate_non_changes[]
baseline:
  head
  commands[]
changes[]:
  id
  title
  status: implemented | proposed | declined | deferred | already-present
  why
  evidence_refs[]:
    path
    sha256
    signal_id?
  basis_apis[]
  files[]
  behavior_contract
  risk
  tests[]
verification[]:
  command
  cwd
  exit_code
  output_tail
  state: passed | failed | unavailable | not-run
vcs:
  base_branch
  work_branch
  commits[]
  diff_stat
report:
  format: myst | typst | html
  source
  rendered
handoff:
  merge_kind: branch | merge-request | patch | none
  merge_commands[]
  review_url
  revision_prompt
problem_space:
  nodes[]
  keystone
  terminus
```

Each RegexStore change also contains:

```text
regexstore:
  complexity: simple | complex
  before
  dsl_example
  positive_examples[]
  negative_examples[]
  caveats[]
```

`dsl_example` is always required. For `complex`, positive examples, negative
examples, and caveats must all be non-empty.

## Evidence, mode, and status invariants

Each `EvidenceRef` contains:

- `path`: the exact repository-relative POSIX path from `intake.evidence`;
- `sha256`: that intake entry's SHA-256 of the complete raw file bytes, not an
  excerpt hash;
- `signal_id`: optional. When present, it must name an intake signal whose
  `evidence` list contains the same path.

A reference does not need a signal ID. Reject an unknown path, a changed full-file
hash, an unknown signal, or a signal that does not cite the path. Line numbers,
symbols, and excerpts can improve the narrative, but proposal v1 does not carry or
validate them.

`mode` records authorization; `status` records the result. Apply these rules:

- `proposed` and `implemented` changes require at least one evidence reference.
- `implemented` is valid only in `mode: implement`.
- Any implemented result requires at least one proposal-level verification with
  state `passed`, `failed`, or `unavailable`; `not-run` does not satisfy that rule.
- `declined`, `deferred`, and `already-present` may omit evidence, although cited
  evidence is useful when it supports the decision.
- Change IDs remain stable across revisions and must be unique.

Verification states bind honestly to `exit_code`:

| State         | Required exit code |
| ------------- | ------------------ |
| `passed`      | `0`                |
| `failed`      | non-zero integer   |
| `unavailable` | `null`             |
| `not-run`     | `null`             |

Reject stale evidence instead of quietly rendering it. Unavailable infrastructure
is `unavailable`, never a passing result.

## Handoff invariants

Merge commands must be exact for the local result and must not claim a remote
review exists when it does not.

- Every merge kind except `none` requires at least one non-blank `merge_commands`
  entry.
- `branch` and `merge-request` require `vcs.work_branch`.
- `merge-request` requires `review_url`; a review URL is invalid for every other
  merge kind.
- `patch` supports a patch-only or no-Git result without requiring a work branch.
- `none` is suitable for a decline or other no-change result. It forbids non-blank
  `merge_commands` and is invalid when any change is `implemented`.
- `revision_prompt` must be non-blank; write it to name the stable IDs to revisit.

Preserve accepted IDs across rounds and rerun affected gates plus any full
repository gate required by policy.
