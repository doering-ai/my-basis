# MyBasis


The MyBasis Python package contains a variety of utilities generally centered around the topics of text processing, functional programming, and runtime type coercion.
This broad scope is somewhat unusual, as any given application will likely only need a small subset of the contents; for this reason, it is intended for use in applications where dependency purity isn't very important, such as personal projects, local development scripts, offline data-processing projects, and prototypes. 
As a metric, the package imports 32 dependencies totalling around ~250 MB in uncompressed `.venv/lib/` files.

## Modules

### `0` Basic Utilities
#### `00` System Utilities
##### `000` Logging
##### `001` Profiling
##### `002` Command Line Interaction
##### `003` File System Validation
#### `01` Functional Programming 

#### `02` Data Serialization
#### `03` Code Reflection
#### `04` Semantic Coercion
##### `040` Roman Numerals
##### `041` General Pluralization
##### `042` Human-Readable Counts
##### `043` Python & Typescript Identifiers 
#### `05` Syntactic Coercion

#### `01` Enumerations

#### `02` UUIDs

#### `03` Environment Variables

### `1` Type Coercion

#### `10` "Vibe" Typing

#### `11` Minskian "Frames"

### `2` Text Processing

#### `20` Regex "Stores"

#### `21` Text Buffers

#### `22` Markdown Trees

### `3` Performant Caching

#### `30` File Caches

#### `31` Nested Caches

#### `32` Pickle Caches

### `4` REST APIs

#### `40` GoogleSheets



## Caveats

### Pydantic-first

Although you can of course use this package without using Pydantic yourself, you'll be missing out on a lot of the ergonomic benefits: basically every class is a Pydantic "model", and the logging functionality included in [`my/base/utils.py`](/my/base/utils.py) exclusively supports Pydantic's `Logfire`. 


### Built for Python 3.13+

It would be pretty trivial to make this library work with versions as old as 3.11, and I aim to do this when I find the time. 
Anything older than that would be quite the reach however, as the typing code uses 3.11 syntax throughout a relatively complex module.

If you're blocked by this, either:

1. Let me know!

2. See if you can just manually extract the code you need from the repo. If you're only using one or two modules, it may be relatively trivial to backport the syntax.


