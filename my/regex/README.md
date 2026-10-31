# `my.regex`

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

`my.regex` treats regular expressions as named, composable structures rather than anonymous strings. It provides stores for shared patterns, match data for predicate-style processing, and a small introspection layer for understanding a pattern's shape. Install the parent Python package through the [root myBasis guide](../../README.md#installation).

</blockquote>

## Pattern management

<blockquote class="artificial-prose">

`RegexStore` accepts strings, lists, tuples, and the package's compact marked syntax. A named subpattern can be invoked with `(?P>name)`. The tuple `('<|>', ['cat', 'car', 'dog'])` requests tree optimization; a raw string containing `<|>` remains a raw string.

`compose_tree()` reuses the regex AST to factor finite literals, positive literal sets and unflagged noncapturing groups, including greedy optional atoms. Caller priority is preserved: `['a', 'ab']` searches short first; put `'ab'` first to prefer the longer match. Equal-width alternatives and disjoint ASCII first-character classes may regroup without changing the chosen match; potentially competing prefixes retain relative order. Eligible trees share prefixes/suffixes and sets, and insert atomic groups only when a unique endpoint is proved. Prefix-containing choices keep the backtracking needed by an enclosing continuation.

Captures, assertions, wildcard/repeated/lazy syntax, existing atomic groups and unsupported grammar use ordinary ordered alternation. Compiler flags flow from `define(flags=...)`, enclosing DSL marks and `compose(..., flags=...)`. Full Unicode folding with ignore-case (including VERSION1's default full folding), reverse, verbose, locale and fuzzy matching modes conservatively skip optimization. Raw inline flag or fuzzy-constraint fragments also keep surrounding composition ordinary. An arbitrary configured formatter conservatively disables nested tree optimization because it can introduce flags after the initial context scan.

For a string that will be compiled elsewhere, pass its intended flags to `compose_tree(..., flags=...)` or `compose(..., flags=...)`. Flags applied only after composition cannot be inferred. For example, full-fold `ss|st` accepts `ß`, while factoring it to `s[st]` would change its language. Direct `Tree` transformations operate on forward literal syntax without an external compiler-mode context.

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
