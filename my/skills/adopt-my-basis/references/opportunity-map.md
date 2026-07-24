# my-basis opportunity map

Use this as a map, not a replacement quota. Inspect the local behavior and its tests
before accepting any signal. Deterministic opportunity detection is regex-focused;
treat the other rows as manual review categories, not scanner coverage.

| Local shape                                              | Candidate                                           | Adopt when                                         | Decline or defer when                                            |
| -------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------------------- |
| repeated partitions, searches, deduplication, mapping    | `ut` / `IterUtils`                                  | semantics match and remove a local helper          | the helper is domain-specific or the dependency cost dominates   |
| sequential text cleanup and parsing                      | `ut` / `TextUtils`                                  | operations already match the documented order      | Unicode, transliteration, or whitespace behavior differs         |
| runtime coercion and validation                          | `ty`, `MyType`, `AutocastModel`                     | untyped boundaries need explicit coercion          | static types or Pydantic validation already express the contract |
| enum, span, predicate, buffer, or identifier scaffolding | `MyEnum`, `Span`, `Predicate`, `Buffer`, `UniqueId` | local type duplicates the same public behavior     | serialization, ordering, or identity semantics differ            |
| repeated filesystem serialization                        | `ut.from_file`, `ut.to_file`, `fs`                  | formats and error behavior match                   | atomicity, permissions, or transaction semantics are specialized |
| shell string construction                                | `Command`                                           | argv can remain structured and observable          | the wrapper's exact I/O or failure semantics do not fit          |
| environment configuration                                | `env`                                               | values are startup configuration                   | values are injected or mutated after import                      |
| bounded caches                                           | `Cache`, `FileCache`, `PickleCache`                 | lifecycle and pruning behavior match               | encryption, atomicity, TTL, or durability requirements differ    |
| Markdown structure                                       | `Markdown`                                          | headings must be fence-aware and round-trip        | only a tiny, well-bounded transform is needed                    |
| observability plumbing                                   | `MetricUtils`                                       | the repository already accepts the optional extra  | failure-path or core tools require near-zero dependencies        |
| related or generated regex patterns                      | `RegexStore`, `MatchData`                           | they form a grammar, router, or repeated transform | the pattern is isolated and obvious                              |

## Required preflight

1. Read `requires-python` and supported runtime documentation.
2. Inspect `git status`, linked worktrees, and local coordination notes.
3. Identify direct and transitive dependencies.
4. Run the installed-version probe after any lock refresh.
5. Confirm `intake.commands.candidate_native_gates` against repository instructions
   and CI, then find any missing test, lint, typecheck, build, or docs commands.
6. Identify latency-sensitive imports and failure paths before adding imports.

Typical probes:

```sh
git status --porcelain=v2 --branch
git worktree list --porcelain
uv tree --package my-basis --invert
uv run python -c "import importlib.metadata as m; print(m.version('my-basis'))"
rg -n -g '*.py' '^(from my|import my|import re|import regex)|re\.(compile|search|match|sub)'
```

Do not execute these blindly when the target uses a different package manager or
its agent instructions specify another gate.

## Evidence rules

For machine-enforced evidence, every `proposed` or `implemented` change cites at
least one intake-relative path and that entry's full-file SHA-256. A `signal_id` is
optional; when present, the signal must cite the same path. Line numbers, symbols,
and excerpts are useful narrative context but are not proposal-v1 evidence fields.
Always state the required behavior contract.

Report explicit reasons for deliberate non-changes. Prefer a partial adoption with
crisp boundaries over a broad mechanical rewrite.
