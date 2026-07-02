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
