# Templates

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

These Jinja templates are the small rendering layer shared by the package. They are resources consumed by code, rather than a second public API: a template change matters through the data shape supplied by its caller.

</blockquote>

## Document templates

<blockquote class="artificial-prose">

`document.md.jinja` is the recursive base. It renders a node's header and prose, then walks into child nodes. `Markdown.md.jinja` extends that shape for `my.files.Markdown`: it maps header, prose, and nodes to Markdown output and adds a fenced YAML block for a node's notes when notes are present.

</blockquote>

```text
document.md.jinja  -> recursive document structure
Markdown.md.jinja  -> Markdown nodes and optional Notes YAML
```

## Code generation templates

<blockquote class="artificial-prose">

`MyEnum.py.jinja` generates Python enum definitions that follow the package's source layout. It can add `Flag` behavior and adjusts imports from the nesting depth supplied by the caller. `get_template()` in `my.infra` loads these resources, and callers such as `Markdown` render a named template with their serialized model data.

</blockquote>
