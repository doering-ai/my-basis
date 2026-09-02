# Agent Development Guidelines

The myBasis Python package, imported as `my`, provides utilities for text processing, functional programming, and runtime type coercion.

It is designed for use as a library.
Its broad scope uses a mostly flat structure.
The source lives under `my/` and is divided into seven public subpackages.
Tests for individual modules live in matching subdirectories under `tests/`.
Sphinx and MyST documentation lives under `docs/`.

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

The legacy `/Taskfile` pointer is stale.
Run `task --list` to see every available command.
The examples below show common tasks.
Pass `-- ARGS` to forward arguments to the underlying tool.

### Pytest commands

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

### Sphinx documentation commands

```zsh
task docs # Build the Sphinx documentation via `sphinx-build`.
```

## Key Dependencies

For a full list of dependencies, see `pyproject.toml`

### Development

- `python 3.13`: minimum supported interpreter and syntax version
- `uv`: dependency management
- `ruff`: linting and code formatting
- `pyrefly`: static type checking through `task eval:typecheck` or `uv run pyrefly check`
- `uv build` and `uv publish`: package building and publishing
- `pytest`: unit testing

### Runtime

- `pydantic`: data validation and settings management through Python type annotations
- `regex`: advanced regular expressions used by the `my.regex` subpackage
- `more-itertools`: iteration utilities beyond the standard library

## Specifics

### Testing Guide

When making significant changes to tests, read and apply `tests/README.md`.

### File Structure

Most Python files use one or more of the following sections.
A large wrapped comment marks each section:

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

The project uses classes for object-oriented behavior, static organization, and singletons.

Large classes usually contain four subsections.
A wrapped comment marks each subsection:

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

Code should use Python type annotations wherever possible.
When an exception is necessary, add `# type: ignore` to the end of the line.

### Docstrings

Each public class and function should have a docstring that describes its purpose, parameters, and return values.
Use Google-style Python docstrings.
Do not repeat type annotations in the docstring.

______________________________________________________________________

## Task backlog: `~/local/tasks`

> **Priority: high.** This is the canonical backlog.
> Treat it as the default source of work for any session that is not explicitly personal/one-off.

**Contents.** `~/local/tasks/` contains one plain Markdown file per task.
These files mirror the Plane.so backlog for workspace `dtm` and project `MEMY`.
Each `MEMY-<N>.md` file, or campaign spec such as `basis-07-*.md`, contains YAML frontmatter and a Markdown body.
The frontmatter defines `title`, `state`, `state_group`, `priority`, `tags`, `step`, and `repo`.
The body is the full specification of record: problem, plan, steps, acceptance criteria, and verification snippet.

This directory is the *collaboration surface*.
A background sync keeps the remote Plane mirror aligned.

**Use.** Check this directory before starting non-personal work.
The standing posture is: *pick a task file, execute its spec, report against its acceptance criteria*.
Do not "wait for an inline prompt."
For open-ended direction such as "keep going", "what's next", or "make progress on the backlog", the answer is usually a file from this directory.
Use the user's preferences plus `priority` and `state_group` (`backlog` → `started` → `done`) to choose it.
Campaign indexes such as `basis-00-index.md` sequence their own subtasks.
Read the index before entering its series.

The `~/my/corpus/policies/task-sync.md` policy and the `plane-ops` skill define read and write mechanics.
They also define the gated `plane_push` rule, conflict resolution, and the legacy bare-number filename exception.
This section only points to that specification.

______________________________________________________________________

## Agent coordination hygiene

> **Priority: high.** Four soft rules ("do unless you have a strong reason") keep parallel agents from stepping on each other and the user.
> Full text in `~/my/corpus/policies/agent_coordination.md`.

1. **Create a task file for every non-trivial unit of work.**
   This includes compilation tasks.
   Check for an existing task before creating one.
   Prefer reopening an incomplete or problem-causing task to creating a follow-up.
   Put the SID in branch names and commit messages such as `Refs: MEMY-N`.
2. **Work in your own worktree and verify its state on exit.**
   Confirm the expected worktree state before exit.
   Provision one proactively for non-trivial work.
   Isolation is the default.
   Flag anomalies to the user and move them to a `wip/` branch if necessary.
   Delete your bulletin entry during the exit check.
   See `~/my/corpus/policies/worktrees.md` for the lifecycle.
3. **Coordinate through `~/.ai/bulletin.md`.**
   At the start of non-trivial work, register a note of about three lines: what, where, and changes.
   Delete the note when the work ends.
   The `corpus-bulletin-poll` systemd timer snapshots the file every five minutes into `~/.ai/bulletin-history/`.
   It applies symbolic overlap checks and can apply an optional DSPy conflict assessment.
4. **Use MyST minisites.**
   Never put thousands of tokens of deep research, architectural analysis, or multi-stage synthesis into chat.
   1. Run `uv run myst-report new <topic>` to initialize a minimal Sphinx and MyST project in a scratch directory.
   2. Write the findings hierarchically in `index.md`.
   3. Run `uv run myst-report build <dir>` to build the HTML.
   4. Give the user a local `file:///` link to the output.
