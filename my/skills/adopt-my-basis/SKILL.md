---
name: adopt-my-basis
description: Audit or refactor a Python repository to adopt my-basis where it improves clarity, using deterministic repository intake, evidence-backed adoption or decline decisions, special RegexStore analysis and DSL examples, repository-native verification, and a rendered MyST or Typst proposal with merge and revision handoff. Use when someone asks to apply, introduce, dogfood, migrate to, or find opportunities for my-basis in one Python repository or a Python fleet. Do not use merely to install the package or for non-Python repositories.
---

# Adopt my-basis

Use the packaged scanner for facts and use agent judgment for changes. A decline,
partial adoption, or already-complete result is successful when it preserves the
repository's dependency, latency, compatibility, or failure-path contract.

## Quick start

From the target repository, use the packaged command without a persistent installation:

```sh
uvx --from my-basis my-basis-adopt skill path
uvx --from my-basis my-basis-adopt skill export .agents/skills/adopt-my-basis
uvx --from my-basis my-basis-adopt prepare .
```

Run `skill path` to give the agent the packaged skill directly. Export only when the
agent needs its own copy, and choose a destination in that agent's skill directory.
The rest of this guide uses bare `my-basis-adopt` as shorthand for the installed
console script; for one-shot use, keep the `uvx --from my-basis` prefix.

Then give the printed `intake.json` path to an agent and ask it to use this skill.
The scanner may create `.basis-adoption/`; it must not edit source, dependency, or
version-control files. Treat `intake.commands.candidate_native_gates` as candidate
native gates until repository instructions or CI confirm them. Opportunity detection
is regex-focused; inspect the other inventory categories manually.

## Choose the mode

- Use `propose` when the user asked for an audit, report, or options.
- Use `implement` only when the user authorized repository changes.
- Within `implement`, use **bounded mode** for one local substitution and **structural mode**
  when the user wants canonical my-basis idioms to replace copied helpers, parallel data
  structures, or a module-wide grammar. Structural mode may deliberately pursue adoption
  farther than the usual minimum, but the resulting whole module must be simpler and each
  replacement must remain behavior-tested.
- If the tree is dirty, isolate implementation in a worktree or stay in `propose`.
- Do not require Plane, an advisor, a merge request, or any other remote service.
  Local evidence, a branch or patch, and the rendered report are the durable path.

## Workflow

01. Read the nearest agent instructions and repository documentation.
02. Run `my-basis-adopt prepare <repo>` and read the resulting `intake.json`.
03. Inspect every cited source site. Detector signals and candidate native gates are
    leads, not conclusions.
04. Read [the opportunity map](references/opportunity-map.md). If any regex signal
    exists, also read [the RegexStore guide](references/regexstore.md). For Sublime repos,
    read [the modern plugin-host guide](references/sublime.md). In structural mode, also
    read [the atomic diff corpus guide](references/diff-corpus.md).
05. Establish the repository's Python floor, dependency budget, import-latency
    constraints, startup/failure paths, package manager, and native verification
    commands before proposing a dependency.
06. Classify each finding as `implemented`, `proposed`, `declined`, `deferred`, or
    `already-present`. Give every finding a stable ID such as `basis-003`.
07. For implementation, write focused behavior tests first. Favor parameter tables
    over scenario-test proliferation and keep names at `test_name__scenario`.
08. Add or pin `my-basis` using the repository's existing package manager and source
    convention. Refresh a moving Git/tag source explicitly and print the installed
    version; lock files do not refresh themselves.
09. In bounded mode, make the smallest coherent refactor. In structural mode, replace
    the complete obsolete structure when doing so produces one clearer canonical model;
    do not leave old and new abstractions competing for ownership.
10. Run repository-native tests, lint, typing, build, and docs gates as applicable.
    Record exact commands, working directories, exit codes, and concise output.
11. Commit each behavior-preserving transformation atomically. Capture it with
    `my-basis-adopt capture <repo> --base <base> --head <head> --output-dir <dir> \
    --summary <story>`. Keep small patches directly copy-ready and summarize large ones.
12. Write `proposal.json` against proposal v2, include every captured manifest under
    `vcs.diffs`, run `my-basis-adopt validate`, and render MyST or Typst.
13. Return the rendered artifact, source proposal, branch/commit or patch, exact
    merge instructions, and a stable-ID prompt for requesting another round.

## Safety and correctness gates

- Never import or execute the target package during discovery.
- Do not read secret-like files, virtual environments, generated/vendor trees,
  oversized files, or symlinks that escape the repository.
- Treat environment access as either startup configuration or runtime-injected
  state. `my.env` is cached; do not use it where tests, secret handoffs, or plugins
  deliberately mutate `os.environ` after import.
- Do not raise a repository's Python floor without an explicit product decision. A
  fleet campaign that explicitly retires an old host is such a decision; record both the
  declared source floor and the actual embedded runtime instead of pretending they match.
- Measure import/cold-start cost for prompt-critical, hook, and failure-path tools.
- A direct import requires a direct dependency even when my-basis is already
  present transitively.
- Do not merge, publish, delete an old implementation, or perform the final release
  gate. Hand the human a reviewable result.

## RegexStore gate

Use RegexStore for a reusable grammar, shared named pieces, repeated transforms,
router classification, recursive structures, or patterns whose construction needs
to be explained. Keep a lone obvious `re.compile` call as-is.

Every RegexStore change must include:

- a runnable DSL example in the report;
- parameterized differential tests against the old behavior;
- boundary, flag, backreference/subroutine, and timeout analysis;
- fail-fast compilation for security-sensitive patterns;
- positive and negative examples for complex grammars.

Use `\g<name>` for a true backreference when reinvocation normalization is enabled;
`(?P>name)` invokes the named subpattern. Read the full guide before composing a
complex store or router.

## Proposal and report

Follow [the proposal contract](references/proposal-contract.md). Every implemented
proposal includes at least one SHA-bound entry from `my-basis-adopt capture`; this is the
copy-ready transformation corpus, not merely a diffstat. Keep the main
report narrative and put file inventories and logs in appendices:

1. the repository's present shape;
2. the adoption thesis;
3. changes grouped by user-visible theme;
4. the RegexStore walkthrough, when relevant;
5. deliberate non-changes;
6. verification evidence and residual risk;
7. how to merge or apply the patch;
8. how to request another round;
9. the remaining problem space and its keystone.

Render with:

```sh
# Write report.md as MyST Markdown.
my-basis-adopt render .basis-adoption/proposal.json --format myst

# Write standalone report.html.
my-basis-adopt render .basis-adoption/proposal.json --format html

# Write report.typ and compile report.pdf.
my-basis-adopt render .basis-adoption/proposal.json --format typst --build
```

Typst source rendering does not require the `typst` executable; `--build` does. If
Typst compilation is unavailable, retain `report.typ`, report the missing executable,
and return an available rendered route such as MyST or HTML.

## Revision handoff

Give the user a prompt in this form:

```text
Use $adopt-my-basis with intake <path> and proposal <path>.
Preserve accepted change IDs. Revise basis-003 and basis-006 as follows: <request>.
Rerun affected gates, refresh stale evidence, and regenerate the report.
```

Refresh the intake when source evidence has changed. Stable IDs survive revisions;
accepted changes must not be silently reopened.

## Fleet dogfood

For each repository, run the scanner before manual inspection. Record each detector
as confirmed, false-positive, or missed. Change deterministic rules only for
repeatable symbolic evidence seen in two repositories (unless it is an invariant);
change this guidance for judgment errors and the report template for communication
errors. Re-run earlier fixtures after every rule change. Never let the scanner
self-modify its detectors or this skill.
