# `my.regex`

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

`my.regex` treats regular expressions as named, composable structures rather than anonymous strings. It provides stores for shared patterns, match data for predicate-style processing, and a small introspection layer for understanding a pattern's shape. Install the parent Python package through the [root myBasis guide](../../README.md#installation).

</blockquote>

## Pattern management

<blockquote class="artificial-prose">

`RegexStore` accepts strings, lists, tuples, and the package's compact marked syntax. A named subpattern can be invoked with `(?P>name)`; a string containing `<|>` is split into alternatives and optimized before it is compiled. This makes a store useful where a project has a vocabulary of reusable fragments rather than one isolated expression.

`compose_tree()` turns a collection of related expressions into a factored pattern tree, so common prefixes and suffixes need not be repeated in every branch.

</blockquote>

## Match processing

<blockquote class="artificial-prose">

`MatchData` carries the original `regex.Match` while participating in the package's predicate machinery. It exposes the matched text, captures, and their positions without discarding the result that produced them. `ParseData` is the intermediate store used when `RegexStore` parsers rename, route, interleave, or transform captured fields.

</blockquote>

## Common patterns

<blockquote class="artificial-prose">

`common_rgxs.py` exports `COMMON_RGXS`, a store of patterns for URLs, dates, numeric prose, and related recurring forms. Its `format_url()` helper normalizes a parsed URL into a concise human-readable form.

</blockquote>

## Regex introspection

<blockquote class="artificial-prose">

The [`meta`](meta/README.md) layer decomposes expressions into atoms, groups, sets, quantifiers, and trees. It is intended for tools that need to reason about a regex before using it, rather than treating it solely as a compiled matcher.

</blockquote>
