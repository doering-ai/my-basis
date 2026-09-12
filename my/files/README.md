# Files

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

`Markdown` keeps a document as an editable tree. `DocName` gives the work a parseable filename tied to the evidence available for it. Both come with [myBasis](../../README.md#installation).

</blockquote>

## Markdown

<blockquote class="artificial-prose">

`Markdown` is a Pydantic document node with a header level, title, tags, prose `Buffer`, notes, and ordered child nodes. `parse()` recognizes level-one through level-six headers, tagged or indexed headers, and nested structure. It masks leading `#` characters inside backtick or tilde fences before scanning, so a code comment does not become a document heading. Empty sections remain nodes, which keeps descendants attached to the heading that owns them.

Indices use base-62 digits (`0-9`, `A-Z`, `a-z`) derived from sibling position. `walk()` traverses depth-first with optional direction and depth limits; `add_node()`, removal, replacement, and index refresh keep the tree addressable while it changes. A `Notes` section is parsed as YAML, and `render()` passes the serialized node through `Markdown.md.jinja` and, by default, `mdformat`.

</blockquote>

```python
from my import Markdown

text = '# Guide\n\nIntro.\n\n## `0 draft` Usage\n\nRun it.\n'
doc = Markdown.parse(text)[0]
assert [(node.level, node.idx, node.tags, node.title) for node in doc.tree] == [
    (1, '', [], 'Guide'),
    (2, '0', ['draft'], 'Usage'),
]
```

## DocName

<blockquote class="artificial-prose">

`DocName` validates the frozen `creators__year__title` filename grammar. Hyphens join words inside a semantic unit, underscores separate units within a slot, and double underscores separate the creator, year, and title slots. `0000` means that nobody has triaged a date; `undated` means that a date was sought and does not exist. Those values carry different evidence, so the parser keeps them distinct.

`mint()` follows an evidence ladder. It first uses named creators, then a work identifier such as `arxiv`, then a publisher or site handle. It keeps a readable title when an identifier supplies the creator-shaped slot and returns `None` rather than inventing a name when the metadata cannot identify a work. `parse()` accepts an existing name, filename, or directory stem and returns `None` for text outside the grammar.

</blockquote>

```python
from my.files import DocName

name = DocName.mint(
    creators=['Hannah Arendt'],
    year=1958,
    title='The Human Condition',
)
assert str(name) == 'arendt-h__1958__the-human-condition'
assert DocName.parse('aristotle__-0350__categories').year == '-0350'
```
