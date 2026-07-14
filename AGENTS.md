# Agent Development Guidelines

The myBasis Python package (imported as `my`) contains a variety of utilities generally centered around the topics of text processing, functional programming, and runtime type coercion.

It is developed with usage as a library in mind, and given its broad scope, is organized into a mostly-flat structure.
The source code is found in `my/`, broken up further into ~7 subpackages.
The corresponding PyTest files for each individual python file are present in matching subdirectories of `tests/`, and the Sphinx w/ MyST documents for the project are found in `docs/`.

## Ethos

- Beautiful is better than ugly.
- Explicit is better than implicit.
- Simple is better than complex.
- Complex is better than complicated.
- Flat is better than nested.
- Sparse is better than dense.
- Readability counts.
- Special cases aren't special enough to break the rules.
- Although practicality beats purity.
- Errors should never pass silently.
- Unless explicitly silenced.
- In the face of ambiguity, refuse the temptation to guess.
- There should be one-- and preferably only one --obvious way to do it.
- Although that way may not be obvious at first unless you're Dutch.
- Now is better than never.
- Although never is often better than *right* now.
- If the implementation is hard to explain, it's a bad idea.
- If the implementation is easy to explain, it may be a good idea.
- Namespaces are one honking great idea -- let's do more of those!

## Commands

For details of various commands, consult `/Taskfile`. Here's a lit of the main commands; pass `-- ARGS` to forward ARGS to the underlying tool.

### PyTest Commands

```zsh
# Run All Tests
task test

# Run Specific Test File
task test -- -v tests/apis/test_Environment.py

# Run Specific Test
task test -- -v tests/apis/test_Environment.py::TestEnvironment::test_get__basic

# Calculate Coverage
task test:cov

# Debug Mode
task test:pdb  # Drops into debugger on failure
task test:dev  # For debugging one test at a time
```

### Sphinx Documentation Commmands

```zsh
task docs # Build the Sphinx documentation via `sphinx-build`.
```

## Key Dependencies

For a full list of dependencies, see `pyproject.toml`

### Development

- `python 3.13`: The project is written in modern Python 3.13 syntax -- no need to support older versions!

- `uv`: dependency management

- `ruff`: linting and code formatting

- `pyrefly`: static type checking (`task eval:typecheck`, or `uv run pyrefly check`)

- `uv build` & `uv publish`: package building & publishing

- `pytest`: unit testing

### Runtime

- `pydantic`: data validation and settings management using Python type annotations

- `regex`: advanced regular expressions -- especially critical for the `my.regex` subpackage.

- `more-itertools`: additional iteration utilities beyond the standard library

## Specifics

### Testing Guide

Whenevery you're making siginifant changes to test files, be sure to read and apply `tests/README.md`.

### File Structure

Almost all Python files in the project contain one or more of the following sections, each delineated by a large, wrapped comment:

```python
############
### HEAD ###
############
"""
This is where imports are defined in three subsections: `STANDARD` (the python stdlib), `EXTERNAL` (dependencies installed via `uv` and controlled by `pyproject.toml`), and `INTERNAL` (other files in this project or an imported library that we wrote).
"""

############
### DATA ###
############
"""This is where dataclasses (usually Pydantic BaseModels) and module-level constants are defined."""

############
### BODY ###
############
"""This is where the main functionality of the file is implemented."""

############
### MAIN ###
############
"""
The entrypoint code for executing this file on the commandline as a script, often with handling of arguments via `argparse`.
"""
```

### Class Sections

In general, the project makes extensive use of classes, both in typical object-oriented situations and for general code organization using static classes and/or singletons.

Large classes are almost always broken down into four subsections, each delimited by a wrapped commment like so:

```python
class MyClass:
    """ [Docstring explaining the purpose of this class.] """
    # [Static class variables here]

    # [Class member variables here]

    # -------------------
    # `0` Initial Methods
    # -------------------
    # [Initialization logic, pydantic serialization & validation functions, static constructors, etc.]

    # -------------------
    # `-` Private Methods
    # -------------------
    # [Helper methods intended for internal use only.]

    # -------------------
    # `+` Primary Methods
    # -------------------
    # [The main methods intended for internal OR external use.]

    # ------------------
    # `x` Public Methods
    # ------------------
    # [The primary public interface methods of this class, including overloads, properties, etc.]
```

### Types

All code should be fully typed using Python type annotations if at all possible.
For exceptions, add `# type: ignore` to the end of the line.

### Docstrings

Each public class and function should have a docstring describing its purpose, parameters, and return value(s).
Docstrings follow the Google format for python docstrings.
Do not include type annotations in the docstring.


______________________________________________________________________

## Task Backlog — `~/local/tasks` (read this first)

> **Priority: high.** This is the canonical backlog.
> Treat it as the default source of work for any session that is not explicitly personal/one-off.

**What it is.** `~/local/tasks/` is a directory of plain Markdown files — one per task — that mirror the Plane.so backlog (workspace `dtm`, project `MEMY`).
Each file (`MEMY-<N>.md`, or a campaign-prefixed spec like `basis-07-*.md`) carries YAML frontmatter (`title`, `state`, `state_group`, `priority`, `tags`, `step`, `repo`) and a Markdown body that is the full spec of record: problem, plan, steps, acceptance criteria, verification snippet.
It is the *collaboration surface*; Plane is a remote mirror a background sync keeps in step.

**How central.** Before starting non-personal work, look here.
The standing posture is: *pick a task file, execute its spec, report against its acceptance criteria* — not "wait for an inline prompt."
When the user gives open-ended direction ("keep going", "what's next", "make progress on the backlog"), the answer is almost always a file in this directory, chosen by `priority`/`state_group` (`backlog` → `started` → `done`) and the user's stated preferences.
Campaign indexes (e.g. `basis-00-index.md`) sequence their own subtasks — read the index first when one exists for a series you're entering.

Read/write mechanics, the gated `plane_push` rule, conflict resolution, and the bare-number legacy-file caveat are documented in `~/my/corpus/policies/task-sync.md` and the `plane-ops` skill — this section is the centrality pointer, not the spec.

______________________________________________________________________

## Agent Coordination Hygiene — four soft rules (read this too)

> **Priority: high.** Four soft rules ("do unless you have a strong reason") keep parallel agents from stepping on each other and the user.
> Full text in `~/my/corpus/policies/agent_coordination.md`.

1. **Task file for every non-trivial unit of work** — even a compilation task.
   Check for an existing task before creating one; prefer reopening an incomplete or problem-causing task to a follow-up.
   The SID goes in commit messages (`Refs: MEMY-N`) and branch names.
2. **Work in your own worktree; verify state on exit** — never exit without confirming your worktree is in the expected state.
   Provision one proactively for non-trivial work — isolation is the default, not something the operator should have to ask for.
   Flag anomalies to the user and move them to a `wip/` branch if necessary.
   Delete your bulletin entry as part of this check.
   See `~/my/corpus/policies/worktrees.md` for the worktree lifecycle.
3. **Coordinate via `~/.ai/bulletin.md`** — register a ~3-line note (what / where / changes?) at the start of non-trivial work; delete it when done.
   A systemd timer (`corpus-bulletin-poll`) snapshots the file every 5 min into `~/.ai/bulletin-history/` with symbolic overlap checks + optional DSPy conflict assessment.
4. **Use MyST Minisites for massive outputs** — never dump thousands of tokens of deep research, architectural analysis, or multi-stage synthesis into the chat context.
   Instead, run `uv run myst-report new <topic>` to initialize a minimal Sphinx+MyST project in a scratch directory, write your findings hierarchically in `index.md`, build the HTML with `uv run myst-report build <dir>`, and hand the user a local `file:///` link to the output.
