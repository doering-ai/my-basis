############
### HEAD ###
############
### STANDARD
from typing import Any, Literal, overload, TypeIs, ClassVar, TYPE_CHECKING
from collections.abc import (
    Callable,
    Collection,
    Container,
    Hashable,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    MutableSequence,
)
from types import FunctionType
from collections import Counter, defaultdict
import functools as ft

### EXTERNAL
import more_itertools as mi
import pydantic as pyd

### INTERNAL (NOTE: If adding new internal imports, update the comments in `__init__.py`)
from ..infra.types import (
    TYPESET,
    Stream,
    Streams,
    String,
    Strings,
    Scalar,
    Scalars,
    Time,
    Times,
    Atom,
    Atoms,
    Vec,
    _Vec,
    Vecs,
    Iter,
    _Iter,
    Iters,
    Map,
    _Map,
    Maps,
    Model,
    Struct,
    _Struct,
    Structs,
    Func,
    Funcs,
)
from .MyType import MyType

if TYPE_CHECKING:
    from my import Typist  # noqa


############
### BODY ###
############
class Check[T](pyd.RootModel[type[T] | T]):
    """Type checking utilities for MyType and Typist."""

    ctx: ClassVar[Typist]

    tvar: MyType

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self):
        """Initialize the Check class and its context."""
        if not hasattr(Check, 'ctx'):
            from .Typist import Typist

            Check.ctx = Typist()

    # -------------------
    # `-` Private Methods
    # -------------------

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `*` Public Methods
    # ------------------
