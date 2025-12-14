# Agent Development Guidelines

The MyBasis Python package (imported as `my`) contains a variety of utilities generally centered around the topics of text processing, functional programming, and runtime type coercion.

It is developed with usage as a library in mind, and given its broad scope, is organized into a mostly-flat structure.
The source code is found in `my/`, broken up further into subdirectories (e.g. `my/utils/`, `my/text/`, etc.) for the purposes of organization and prevention of circular imports.
The corresponding PyTest files for each individual python file are present in matching subdirectories of `tests/`.

## Important Dependencies

### Development

- `python 3.13`: The project is written in modern Python 3.13 syntax -- no need to support older versions!

- `uv`: dependency management

- `ruff`: linting and code formatting

- `ty`: static type checking

- `uv build` & `uv publish`: package building & publishing

- `pytest`: unit testing

### Runtime

- `pydantic`: data validation and settings management using Python type annotations

- `regex`: advanced regular expressions

- `tqdm`: progress bars

- `more-itertools`: additional iteration utilities beyond the standard library

## Style

### File Structure

Almost all Python files in the project contain one or more of the following sections, each delineated by a large, wrapped comment:

1. `HEAD`: This is where imports are defined in three subsections: `STANDARD` (the python stdlib), `EXTERNAL` (dependencies installed via `uv` and controlled by `pyproject.toml`), and `INTERNAL` (other files in this project or an imported library that we wrote).

2. `DATA`: This is where dataclasses (usually Pydantic BaseModels) and module-level constants are defined.

3. `BODY`: This is where the main functionality of the file is implemented.

4. `MAIN`: The entrypoint code for executing this file on the commandline as a script, often with handling of arguments via `argparse`.

### Classes

In general, the project makes extensive use of classes, both in typical object-oriented situations and for general code organization using static classes and/or singletons.

Large classes are almost always broken down into four subsections, each delimited by a wrapped commment like so:

```py
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

Each class and function should have a docstring describing its purpose, parameters, and return value(s).
Do not include type annotations in the docstring.
