# Meta - Regex Introspection

The `meta` subdirectory provides tools for parsing, analyzing, and manipulating regular expressions at a structural level. These are "meta-patterns"—regular expressions designed to match and decompose other regular expressions. This enables programmatic transformation and optimization of regex patterns.

## Atomic Components

The package defines three types of atoms representing the fundamental building blocks of regex patterns. `Atom` is the base class representing any atomic unit, whether a literal character, escape sequence, or special construct. It provides methods for quantifier attachment, plain text atomization (handling escapes and special characters), and string representation.

`GroupAtom` represents any parenthetical group construct, from simple capturing groups `(...)` to complex constructs like atomic groups `(?>...)`, lookaheads `(?=...)`, or named captures `(?P<name>...)`. The atom stores the group's kind (via `GroupKind`), its start syntax, body content, and any trailing quantifier. Methods support extracting the group name for named groups and determining structural properties.

`SetAtom` represents character class expressions like `[a-z]`, `[^0-9]`, or `[:alpha:]`. Sets can be negated and may contain ranges, character class shortcuts, or POSIX character classes. Like groups, sets can have trailing quantifiers.

## Group Classification

`GroupKind` is an `IntFlag` enum providing fine-grained classification of all group types supported by the `regex` library. The enum distinguishes between basic types (plain/positional captures vs non-capturing groups), named constructs (named captures, subroutine calls, backreferences), lookarounds (lookahead/behind, positive/negative), and special forms (atomic groups, conditionals, comments, DEFINE blocks).

The enum supports bitwise operations for filtering, with predefined masks like `_NAMED` (all named group types), `_SIMPLE` (plain groups), and `_INVOC` (subroutine invocations). The `read()` classmethod parses group opening syntax to determine the kind, handling the complex decision tree of `(?...` forms.

## Regex Decomposition

The `Regex` class provides the core functionality for breaking down regex strings into atomic components. The `atomize()` classmethod recursively parses a pattern string, correctly handling nesting, escaping, and the interactions between groups and character sets. It uses the `group_iterator()` and `set_iterator()` methods which leverage buffer pair matching to identify balanced constructs.

The class stores its data as a list of `Atom` objects and supports pattern splitting at branch points (the `|` operator). Methods like `is_split()` determine if a pattern contains top-level alternation, while `split()` breaks patterns into their branches. The class integrates with Pydantic for use in typed data models.

## Tree Optimization

The `Tree` class represents branching regex patterns as hierarchical structures suitable for optimization. A tree consists of multiple branches (alternation arms), and each branch is a sequence of atoms. The `expand()` method recursively replaces groups with their expanded forms, while `condense()` factors out common prefixes and suffixes to reduce pattern complexity.

Condensation works by identifying shared leading or trailing atoms across all branches and hoisting them outside the alternation group. This process repeats recursively on nested groups until no further optimization is possible. The `render()` method converts the optimized tree back to a regex string.

## Meta-Patterns

The `meta_patterns.py` module defines `META_RGXS`, a `RegexStore` containing patterns for matching regex syntax elements themselves. These patterns identify group opening delimiters, character sets, escape sequences, quantifiers, inline flags, and special characters. They power the parsing logic in `Regex` and enable the DSL mark syntax in `RegexStore`.

The `Quantifier` class represents quantifier syntax (like `*`, `+`, `?`, `{n,m}`, including lazy and possessive variants), providing utilities for comparing and manipulating quantifiers programmatically.
