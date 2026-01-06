# Contributing

I created this project over the course of 2025 as part of my AI work, so it is likely pretty personal to me.
I've tried my best to generalize it in case someone finds it useful someday (for use, learning, or otherwise!), but I'd absolutely welcome any thoughts you have on how it might be better on that front.

If you're interested in contributing the project, simply get in touch, open an issue, or open a PR!

### Design Philosophy

1. I readily except

### Subpackage Dependency Tree

When adding new relative imports to any of the modules in this package, make sure to either respect or update this structure (in order to prevent circular dependencies).

- `utils` imports nothing.
    - `caches` imports `utils`
        - `typing` imports `utils` and `caches`
            - `types` imports `utils` and `typing`
                - `apis` imports `utils` and `types`
                - `regex` imports `utils` and `types`
                    - `files` imports `utils`, `typing`, `types`, and `regex`
