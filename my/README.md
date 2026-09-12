# `my` Python Library

> Left-rule blocks mark artificial prose; quotations retain their own attribution.

<blockquote class="artificial-prose">

`my` is the public namespace for the library’s internal layers. This page is the import map to consult before adding a relative import or moving a shared abstraction. For package installation and ordinary use, see the [project README](../README.md).

</blockquote>

## Subpackage dependency tree

<blockquote class="artificial-prose">

The graph records relative-import dependencies. Keep a new edge within this ordering, or update the map with the implementation; that keeps an apparently small import from turning into a cycle through a higher layer.

</blockquote>

- `infra` imports nothing.
  - `utils` imports `infra`.
    - `caches` imports `utils`.
      - `typing` imports `infra`, `utils`, and `caches`.
        - `types` imports `infra`, `utils`, and `typing`.
          - `regex` imports `infra`, `utils`, `types`, and `typing`.
            - `apis` imports `infra`, `utils`, `types`, `regex`, and `typing`.
            - `files` imports `infra`, `utils`, `typing`, `types`, and `regex`.

<blockquote class="artificial-prose">

`data` and `scripts` sit outside this relative-import graph. `data` is a resource namespace read through `importlib.resources`, while scripts consume the finished public API through absolute `from my import ...` imports.

</blockquote>

## Contributing

I created this project over the course of 2025 for my own use, so it's definitely 'opinionated', for better or worse.
Specifically, it is influenced by:

- a weathered respect for polymorphism,
- an addiction to "ergonomic" code\*\*, and
- a reliance on symbolic (deterministic!) devtools, namely heavy use of typing, even at runtime.

If you're interested in contributing the project, simply get in touch, open an issue, or open a PR!

```{note}
__\*\*:__ This buzzword implies some trite promises--namely that the code is concise, clear, and/or generally satisfying--but I intend it with a bit more sincerity & specificity.

In my usage, it is code that conforms to the design standards set out by the physical and interface design academies(/industries), especially the work of Don Norman.
The most relevant are Consistency, Simplicity, Mapping, Visibility, Constraints, and Feedback.
```
