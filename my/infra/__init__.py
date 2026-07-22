"""Foundational Types and Constants.

The `infra` subpackage is the package's dependency-free foundational layer: it defines the public
type-alias vocabulary (`Atom`, `Vec`, `Map`, `Model`, ...) that the top-level `my` namespace
re-exports, plus package paths and template plumbing. Nothing here imports from elsewhere in the
package, and it deliberately has no docs page of its own -- consumers meet these names through
`my` directly.
"""

from .types import (
    # Singular aliases
    Stream,
    String,
    Scalar,
    Real,
    Time,
    Atom,
    Vec,
    Map,
    Iter,
    Struct,
    Func,
    Object,
    Model,
    Dataclass,
    # Generic (parametrizable) aliases
    VecT,
    MapT,
    _Iter,
    StructT,
    FuncT,
    # Tuple collections (isinstance-safe)
    Streams,
    Strings,
    Scalars,
    Reals,
    Times,
    Enums,
    Atoms,
    Vecs,
    Maps,
    Models,
    Structs,
    Funcs,
    Iters,
    Objects,
    TYPESET,
)
from .constants import INFRA_PATHS, InfraPaths, DELIM, get_template

__all__ = [
    'Stream',
    'String',
    'Scalar',
    'Real',
    'Time',
    'Atom',
    'Vec',
    'Map',
    'Iter',
    'Struct',
    'Func',
    'Object',
    'Model',
    'Dataclass',
    'VecT',
    'MapT',
    '_Iter',
    'StructT',
    'FuncT',
    'Streams',
    'Strings',
    'Scalars',
    'Reals',
    'Times',
    'Enums',
    'Atoms',
    'Vecs',
    'Maps',
    'Models',
    'Structs',
    'Funcs',
    'Iters',
    'Objects',
    'TYPESET',
    'INFRA_PATHS',
    'InfraPaths',
    'DELIM',
    'JINJA',
    'get_template',
]


def __getattr__(name: str) -> object:
    """Lazily surface `constants.JINJA` so `import my` never builds the Jinja env eagerly."""
    if name == 'JINJA':
        from . import constants

        return constants.JINJA
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
