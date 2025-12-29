# MyBasis

The MyBasis Python package contains a variety of utilities generally centered around the topics of text processing, functional programming, and runtime type coercion.
This broad scope is somewhat unusual, as any given application will likely only need a small subset of the contents; for this reason, it is intended for use in applications where dependency purity isn't very important, such as personal projects, local development scripts, offline data-processing projects, and prototypes.
As a metric, the package imports 32 dependencies totalling around ~250 MB in uncompressed `.venv/lib/` files.

## Modules

### `0` Utility Functions

#### `00` Iteration Utilities

#### `01` Syntax Utilities

`0` NORMALIZATION
`1` ANNOTATION

#### `03` Semantic Utilities

#### Text Utilities

#### Code Utilities

#### `02` System Utilities

##### `020` Logging

##### `021` Profiling

##### `022` Command Line Interaction

##### `023` File System Validation

#### Enumerations

#### UUIDs

#### Environment Variables

### Reusable Types

#### Minskian Predicates

#### Minskian Predicates

### `/typing/`: Type Coercion

#### "Vibe" Typing

### Text Processing

#### Regex "Stores"

#### Text Buffers

#### Markdown Trees

### Typed Caches

#### File Caches

#### Nested Caches

#### Pickle Caches

### Singleton Interfaces

#### GoogleSheets

#### Environment

## Caveats

### Pydantic-first

Although you can of course use this package without using Pydantic yourself, you'll be missing out on a lot of the ergonomic benefits: basically every class is a Pydantic "model", and the logging functionality included in [`my/base/utils.py`](/my/base/utils.py) exclusively supports Pydantic's `Logfire`.

### Built for Python 3.12+

It would be pretty trivial to make this library work with versions as old as 3.11, and I aim to do this when I find the time.
Anything older than that would be quite the reach however, as the typing code uses 3.11 syntax throughout a relatively complex module.

If you're blocked by this, either:

1. Let me know!

2. See if you can just manually extract the code you need from the repo. If you're only using one or two modules, it may be relatively trivial to backport the syntax.
