"""Re-export ``myBasis``'s public API at the checkout root.

SublimeText imports each ``Packages/<dirname>`` directory as a top-level module matching its
directory name, so this file exists to make ``import <dirname>`` (e.g. ``import myBasis`` for the
conventional checkout name) transparently forward to the real, nested ``<dirname>/myBasis/``
implementation package -- callers never need to know about the extra nesting.
"""

from __future__ import annotations

if __package__:
    # Normal case: this file is genuinely part of a package (live ST plugin loading, or any
    # validly-named checkout imported the ordinary way) -- forward via a relative import.
    from .myBasis import *  # noqa: F403
else:
    # Imported anchorlessly -- e.g. pytest's `Package` collector importing a checkout-root
    # `__init__.py` directly by file path, which it does unconditionally for any directory
    # containing one. That breaks the relative import above whenever the checkout directory
    # name isn't a valid Python identifier (see MEMY-60), since there's no package to be
    # relative *to*. Fall back to an absolute import of the nested package instead -- it
    # resolves the same code either way, via the `myBasis` distribution's editable install.
    from myBasis import *  # noqa: F403
