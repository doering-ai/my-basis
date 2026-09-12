# `my.regex.meta`

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

`my.regex.meta` is the structural view of the parent regex package. It exposes the pieces of a regex and the trees assembled from them, so callers can inspect or transform an expression without first reducing it to an opaque compiled pattern. Install the parent package through the [root myBasis guide](../../../README.md#installation).

</blockquote>

## Atomic components

<blockquote class="artificial-prose">

`Atom`, `GroupAtom`, and `SetAtom` describe the units recognized while parsing an expression. An atom retains its original source text; group and set atoms add the delimiters, contents, and spans that make their structure meaningful. `Quantifier` records the repetition suffix associated with an atom when one is present.

</blockquote>

## Group classification

<blockquote class="artificial-prose">

`GroupKind` is a flag-based classification for the group forms the parser recognizes. Its masks, including `_NAMED`, `_SIMPLE`, and `_INVOC`, let a caller distinguish ordinary grouping, named definitions, and named invocations. `GroupKind.read()` derives that classification from a group prefix.

</blockquote>

## Decomposition and trees

<blockquote class="artificial-prose">

`Regex` atomizes a source expression and provides iterators over its groups and sets. `ParseData` keeps the original text beside that parsed structure. `Tree` can expand, condense, and render the resulting branches, which is useful when a tool needs to compare or factor alternatives.

</blockquote>

## Meta patterns

<blockquote class="artificial-prose">

`META_RGXS` is the store of patterns used by this layer to identify the regex syntax it understands. It is an implementation vocabulary for the introspector, not a second matching API.

</blockquote>
