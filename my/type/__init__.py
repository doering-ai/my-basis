"""Deprecated compatibility shim for the old `my.type` subpackage.

`my.type` was renamed to `my.typing` during the 2025-11 subpackage reorganization
(commit `05e1b98`). This shim re-exports the current `my.typing` surface under the old import
path so pre-existing downstream imports (wikiparse, ai) keep working, emitting a
`DeprecationWarning` to push migration toward the new path. Remove once those consumers migrate
off `my.type`.

Note: `Environment`/`env` (moved to `my.apis`) and `Predicate` (moved to `my.types`) were also
part of the old `my.type` surface but crossed into unrelated subpackages during the reorg and are
not re-exported here -- no downstream site imports them from `my.type` today. `TimeType` (a
`date | datetime | time | timedelta` alias) was an internal implementation detail of the old
`Typist` and has no current public equivalent; also unused downstream.
"""

import warnings

import my.typing as _typing
from my.typing import *  # noqa: F403

warnings.warn(
    'my.type is deprecated and will be removed; import from my.typing instead.',
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [*_typing.__all__]
