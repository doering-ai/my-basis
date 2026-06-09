# `my` Python Library

This document is a high-level overview of the engineering decisions behind the my Python package.
For general project information, see [the root directory](/README.md).

### Subpackage Dependency Tree

When adding new relative imports to any of the modules in this package, make sure to either respect or update this structure (in order to prevent circular dependencies).

- `utils` imports nothing.
  - `caches` imports `utils`
    - `typing` imports `utils` and `caches`
      - `types` imports `utils` and `typing`
        - `apis` imports `utils` and `types`
        - `regex` imports `utils` and `types`
          - `files` imports `utils`, `typing`, `types`, and `regex`

### Contributing

I created this project over the course of 2025 for my own use, so it's definitely 'opinionated', for
better or worse. Specifically, it is influenced by:

- a weathered respect for polymorphism,
- an addiction to "ergonomic" code\*\*, and
- a reliance on symbolic (deterministic!) devtools, namely heavy use of typing, even at runtime.

If you're interested in contributing the project, simply get in touch, open an issue, or open a PR!

```{note}
__\*\*:__ This buzzword implies some trite promises--namely that the code is concise,
clear, and/or generally satisfying--but I intend it with a bit more sincerity & specificity.

In my usage, it is code that conforms to the design standards set out by the physical and
interface design academies(/industries), especially the work of Don Norman.
The most relevant are Consistency, Simplicity, Mapping, Visibility, Constraints, and Feedback.
```
