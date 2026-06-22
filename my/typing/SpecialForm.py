############
### HEAD ###
############
# Standard imports
from __future__ import annotations

# from types import (
#     UnionType,
#     GenericAlias,
#     EllipsisType,
#     NoneType,
#     get_original_bases,
#     FunctionType,
#     BuiltinFunctionType,
# )
# from typing import (
#     Any,
#     ClassVar,
#     Literal,
#     Self,
#     TypeGuard,
#     Unpack,
#     overload,
#     TypeIs,
#     is_typeddict,
#     TypeAliasType,
#     get_args,
#     get_origin,
#     Union,
#     IO,
# )
# from collections import Counter, deque
# from collections.abc import (
#     Iterable,
#     Iterator,
#     Mapping,
#     Callable,
#     AsyncIterable,
#     ItemsView,
#     Set,
# )
# from io import StringIO, BytesIO
from enum import Enum

# Modular imports

# Local imports
# from ..infra.types import (
#     Object,
#     Stream,
#     String,
#     Scalar,
#     Time,
#     Atom,
#     Vec,
#     Iter,
#     Map,
#     Model,
#     Struct,
#     Func,
#     Dataclass,
# )
from ..utils import ut


############
### BODY ###
############
class SpecialForm(Enum):
    """An enumerator built to classify all those type annotation that aren't `type` instances."""

    NULL = frozenset('')

    #: Forms that always match.
    UNIV = frozenset(
        {
            'Unknown',
            'Any',
        }
    )

    #: Forms that are treated as unmatchable.
    NONE = frozenset(
        (
            '',
            'CapsuleType',
            'Concatenate',
            'LiteralString',
            'Never',
            'NewType',
            'NoReturn',
            'NotImplementedType',
            'ParamSpec',
            'ParamSpecArgs',
            'ParamSpecKwargs',
            'Protocol',
            'ReadOnly',
            'Self',
            'Type',
            'TypeVar',
            'TypeVarTuple',
        )
    )

    #: Simple wrapper types.
    MONO = frozenset(
        (
            'Annotated',
            'ClassVar',
            'Final',
            'NotRequired',
            'Required',
            'Unpack',
        )
    )

    #: Wrappers of more than one type at once.
    POLY = frozenset(
        (
            'Union',
            'Optional',
            'UnionType',
        )
    )

    #: Types that resolve to bool at runtime.
    COND = frozenset(
        (
            'TypeGuard',
            'TypeIs',
        )
    )

    #: Iterable types (i.e. vectors, maps, and models).
    ITER = frozenset(
        (
            'AsyncGenerator',
            'AsyncIterable',
            'AsyncIterator',
            'Generator',
            'Iterator',
            'TypedDict',
            'NamedTuple',
        )
    )

    #: Fundamental stdlib types from the `types` module.
    TYPE = frozenset(
        (
            'Ellipsis',
            'EllipsisType',
            'TypeAlias',
            'TypeAliasType',
            'NoneType',
        )
    )

    #: Types for representing callable objects.
    FUNC = frozenset(
        (
            'Callable',
            'Coroutine',
        )
    )

    @classmethod
    def __new__(cls, tvar: object | None = None) -> SpecialForm:
        """Return the filter that matches this name."""
        if not tvar:
            return cls.NULL
        elif isinstance(tvar, str):
            name = tvar
        else:
            name = str(ut.get_one(tvar.__dict__, '__name__', 'name') or tvar)

        return next((name in form.value for form in cls), cls.NULL)
