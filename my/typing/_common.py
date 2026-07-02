############
### HEAD ###
############
### STANDARD
from __future__ import annotations
import typing
import collections.abc as abc

### EXTERNAL

### INTERNAL
# from .MyType import MyType


class Decline(Exception):
    """Raised by a cast transform to signal it cannot handle the given pair -- *not* a crash.

    The cast dispatch loop (`Transform.__call__`) tries candidate transforms in turn. For years
    it wrapped every candidate in `suppress(Exception)`, so a transform that genuinely *crashed*
    on its input was indistinguishable from one that deliberately *declined* it: both just
    advanced to the next candidate. That conflation silently killed dozens of transforms whose
    bodies raised on every input (see the June-July 2026 repair campaign -- e.g. `is_map_type`
    raising `TypeError` on every call, `serialize()` handlers that could never fire), each dead
    for months before a crash was noticed.

    `Decline` splits the two meanings apart: a transform that determines it cannot handle the
    (source, target) pair *raises `Decline`* (or returns the `None` sentinel, still honored for
    now), and the loop catches **only** `Decline` before moving on. Any other exception is a real
    bug -- during the transitional period the loop logs it loudly and re-declines so nothing
    user-facing breaks while the latent-crash tail is flushed; eventually it will propagate.

    Lives here in `_common.py` so every chamber (cast, match, check, MyType) can import it without
    creating an import cycle.
    """


# Auxiliary & Meta Types

ABSTRACT_GENERICS = dict(
    maps=(typing.Mapping, abc.Mapping, abc.MutableMapping),
    vecs=(
        typing.Iterable,
        typing.Sequence,
        typing.Collection,
        abc.Sequence,
        abc.Collection,
        abc.Iterable,
    ),
    sets=(
        typing.AbstractSet,
        abc.Set,
        abc.MutableSet,
    ),
)
