# my.regex

## Pattern Management

The `RegexStore` class is the centerpiece of this subpackage, providing a powerful DSL (domain-specific language) for defining, composing, and managing complex regex patterns. Rather than working with raw regex strings, you define patterns using a hierarchical structure of strings, lists, tuples, and custom mark syntax. Patterns can reference other patterns as subroutines using the `(?P>name)` syntax, and the store automatically resolves dependencies and compiles them into execution-ready objects.

The DSL supports several composition primitives: strings are composed directly, lists concatenate their elements with a configurable separator, tuples create groups with custom separators and quantifiers, and the special `<|>` mark triggers pattern optimization. The mark syntax provides a concise way to specify group types (capturing, non-capturing, atomic, etc.), separators, inline flags, and quantifiers. For example, `('|:', [pattern1, pattern2])` creates a non-capturing alternation group.

Pattern optimization is handled through router trees, which efficiently match long patterns against long texts by factoring out common prefixes and suffixes. The `compose_tree()` method recursively expands and condenses branching patterns, producing optimized expressions that can be significantly faster than naive alternations.

## Match Processing

`MatchData` and `ParseData` provide ergonomic containers for regex match results. `MatchData` extends the `Predicate` type with cached properties for common match attributes like `span`, `start`, `end`, and `text`. It maintains both the original `regex.Match` object and a cleaned dictionary of captured groups, with support for accessing group values, positions, and spans.

`ParseData` handles the transformation of raw match data through custom parser functions. Parsers can be simple string-based renaming, dictionary-based routing (for routers), or arbitrary functions that transform captured values. The parsing infrastructure supports interleaving captures from multiple matches and applying field-specific transformations.

## Common Patterns

The `common.py` module exports `COMMON_RGXS`, a `RegexStore` containing frequently-used patterns for URLs, dates, numeric values, and prose elements. Patterns include web URLs with automatic detritus removal, various date formats (symbolic, YMD, DMY, MDY), Roman numerals, and common prepositions. The `format_url()` function demonstrates custom pattern parsers that clean matched results.

## Meta - Regex Introspection

The `meta` subdirectory contains tools for parsing and analyzing regex patterns themselves—essentially "regex for regex". The `Regex` class breaks regex strings into atomic components (`Atom`, `GroupAtom`, `SetAtom`) representing individual characters, groups, and character sets. This enables programmatic manipulation of regex patterns, such as transforming positional captures to non-capturing groups or extracting all subroutine invocations.

`GroupKind` is an `IntFlag` enum representing all possible group types (capturing, non-capturing, atomic, lookahead/behind, named, backreferences, etc.). The `group_iterator()` method uses buffer pair matching to correctly identify groups even in complex patterns, respecting nesting and ignoring escaped parentheses or those within character sets.

The `Tree` class represents branching patterns as hierarchical structures that can be optimized through expansion and condensation. This powers the router tree optimization in `RegexStore`, factoring out common prefixes and suffixes to reduce backtracking.

Together, these meta tools enable `RegexStore` to validate patterns, resolve dependencies, transform syntax, and generate optimized compiled expressions from high-level DSL descriptions.
