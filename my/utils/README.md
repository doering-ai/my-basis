# My Utilities

## Iteration Utilities

`IterUtils` provides functional programming primitives and collection manipulation tools. The `partition()` and `multi_partition()` methods split iterables based on predicates, while `bucket()` groups items by key function. The `find()` and `find_key()` methods locate items or keys in sequences and mappings using predicates or value matching.

Mapping utilities include `map_items()` for extracting key-value pairs from dict-like objects, `map_condense()` for filtering by value, and `val_map()` for transforming all values while preserving keys. The `build()` function enables function composition via reduce, and various has/all methods check for element presence across collections.

## Text Utilities

`TextUtils` provides regex-based text processing without requiring the full `my.regex` package. The `replace()` function applies multiple sequential regex substitutions, while `split_into()` guarantees exactly n parts with padding. The `multi_rgx()` function combines patterns into branching groups, and `regex_dict()`/`regex_array()` compile pattern collections.

Formatting utilities include `wrap()` for decorative text borders, `indent()`/`unindent()` for whitespace manipulation, and `has_any()`/`has_all()` for substring presence checking. The `unwrap_paragraphs()` method removes hard line breaks while preserving paragraph structure, useful for reformatting wrapped text.

## System Utilities

`SystemUtils` handles system-level operations across several domains. Time utilities like `posix()` convert between timestamps and UTC datetimes, while `posix_since()` calculates elapsed time. Filesystem utilities `validate_file()` and `validate_dir()` assert path existence, and `path_sub()` performs component substitution in Path objects.

Terminal interaction is supported through `get_terminal_width()`, `terminal_linewrap()` for text wrapping, and `zsh_colorize()` for colored output. The `confirm()` method provides user confirmation prompts with auto-confirm mode available for scripting. Logging setup via `setup_logging()` configures standard library loggers with file rotation.

The class also provides `clear_cached_properties()` for invalidating `functools.cached_property` values, `run_async()` for executing async functions from sync contexts, and Pydantic field helpers like `pyd_schemify()` for integrating non-Pydantic types into models.

## Syntax Utilities

`SyntaxUtils` provides tools for working with Python syntax and code structure. These utilities help with parsing, analyzing, and manipulating Python code at the syntactic level, supporting code generation and metaprogramming tasks.

## Semantic Utilities

`SemanticUtils` offers higher-level text analysis focused on meaning rather than structure. These utilities extract semantic information from text, supporting natural language processing and document understanding tasks.
