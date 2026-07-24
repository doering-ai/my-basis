# Atomic diff corpus

The diff corpus is the reusable half of a fleet adoption. It preserves not only
the final API call, but the exact, behavior-tested transformation that replaced an
older structure.

## What qualifies

Capture a commit when all of these are true:

- it replaces one coherent old structure with one coherent my-basis structure;
- the commit is reviewable without unrelated formatting or version churn;
- behavior is covered by parameterized differential or contract tests;
- the worktree is clean and both revisions are committed;
- the summary explains the conceptual replacement, not merely the files touched.

Dependency-floor changes, generated lockfile updates, and formatter-only changes
belong in separate commits unless they are indivisible from the transformation.

## Capture

```sh
my-basis-adopt capture . \
  --base origin/main \
  --head HEAD \
  --output-dir .basis-adoption/diffs/regex-router \
  --summary "Replace the parallel route regexes with one named RegexStore grammar."
```

The command writes:

- `change.patch`, the complete textual Git patch;
- `manifest.json`, containing the two full commit IDs, patch SHA-256, byte count,
  diffstat, and narrative summary.

It refuses dirty tracked worktrees, identical revisions, empty patches, symlink
destinations, and patches larger than 2 MB. For a larger coherent change, split
the implementation into atomic commits rather than truncating the evidence.

## Report placement

Copy each manifest object into `proposal.json` under `vcs.diffs`. Keep the patch
beside the report at the manifest's relative `patch_path`. The rendered report
links to the full patch and tells the high-level story; readers can inspect or
apply the exact transformation without reconstructing it from prose.

Summaries should use this form:

> Replace **old conceptual owner** with **new canonical owner**, preserving
> **observable contract** and removing **obsolete parallel structure**.

## Fleet index

For a fleet campaign, create one index row per atomic commit:

| Repository | Transformation | APIs | Tests | Patch SHA-256 |
| --- | --- | --- | --- | --- |
| plugin | copied helper to canonical facade | `my.ut` | contract matrix | manifest value |

Do not combine unrelated repositories into one patch. A fleet report may group
the narratives, but each repository retains its own branch, commits, gates, and
merge handoff.
