############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from typing import overload, ClassVar, Literal, is_typeddict, Any
from typing_extensions import TypeIs  # 3.13 in the stdlib; our floor is 3.12
from collections.abc import Hashable, Iterable, ItemsView, Mapping
from enum import Enum
from dataclasses import is_dataclass
import contextlib as ctx
import functools as ft
import itertools as it
import inspect

### EXTERNAL
import pydantic as pyd

### INTERNAL
from ..infra.types import (
    Stream,
    String,
    Scalar,
    Time,
    Atom,
    Vec,
    Iter,
    Maps,
    Model,
    Func,
    Funcs,
)
from ..utils import ut
from ..caches import NestedCache
from .MyType import MyType, TypeArg
from ._TypingBase import _TypingBase


############
### BODY ###
############
class TypeMatch(_TypingBase):
    """Type matching utilities for MyType and Typist.

    Exported as the static alias `tym`, and mixed into `Typist` (so `ty.match` and the
    `is_*_type` family resolve here). Matching compares *types* to types; see `TypeCheck` for
    comparing runtime values to types.

    Examples:
        Compare generic types recursively, beyond what `issubclass()` can see::

            >>> from collections.abc import Mapping
            >>> from my import tym
            >>> tym.match(dict[str, int], Mapping[str, int])
            True
            >>> tym.match(dict[str, int], Mapping[str, str])
            False
    """

    MATCH_CACHE: ClassVar[NestedCache[tuple[str, str], bool]] = NestedCache(signature=(str, str))

    # -------------------
    # `.` Initial Methods
    # -------------------

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def _match_literals(cls, t0: MyType, t1: MyType, inter: bool) -> bool:
        """Check if two literal types match according to subset or intersection logic.

        Args:
            t0: First MyType with literal members.
            t1: Second MyType with literal members.
            inter: If True, check for intersection; if False, check for subset.
        Returns:
            True if types match according to the specified logic.
        """
        # 0. Setup
        lit0, lit1 = t0.literal_members, t1.literal_members
        o0, o1 = t0.origin, t1.origin

        _recur = ft.partial(cls.match, intersect=inter)
        if lit0 and lit1:
            assert o0 and o1, "Found literal without an origin, which doesn't make sense."
            if o0 is Literal and o1 is Literal:
                # I.i. Two literals are basically the same as container types, just with objects
                fn = ut.has_any if inter else ut.has_all
                return fn(t1.literal_members, *t0.literal_members)

            elif issubclass(o0, o1) and issubclass(o1, tuple):  # type: ignore
                # I.ii. Two positional tuples must always match exactly
                return len(t0.args) == len(t1.args) and all(
                    it.starmap(_recur, zip(t0.args, t1.args, strict=True))
                )
        elif lit0 and (m1 := t1.main):
            assert o0, "Found literal without an origin, which doesn't make sense."
            if o0 is Literal:
                # II.i. A literal can be a subset of an atomic type(s)
                fn = any if inter else all
                return fn(_recur(arg, t1) for arg in t0.args)
            elif issubclass(o0, m1) and issubclass(m1, tuple):
                if len(t1.args) == 0:
                    # II.ii. Any positional tuple is a subset of its plain base
                    return True
                elif t1.vals:
                    # II.iii. Theoretically, a positional tuple could a subset of a typed tuple
                    #         e.g. tuple[int, str] x tuple[object, ...]
                    return all(_recur(arg, t1.vals) for arg in t0.args)

        elif lit1 and inter and t0.main:
            # III. Just recurse w/ flipped arguments for DRY reasons
            return cls._match_literals(t1, t0, inter=False)

        return False

    # -------------------
    # `+` Primary Methods
    # -------------------
    @classmethod
    def is_map_item_type[T](cls, tvar: TypeArg[T]) -> bool:
        """Check if this type represents a mapping item (2-tuple key-value pair)."""
        tvar = MyType.new(tvar)
        args, n = tvar.args, len(tvar.args)
        if tvar.main is tuple:
            match n, args:
                case 0, _:
                    return True
                case 2, (k, _):
                    return cls.match(k.main, Hashable)
        return False

    # ------------------
    # `*` Public Methods
    # ------------------
    @overload
    @classmethod
    def match(cls, t0: None, t1: Any, intersect: bool = False) -> Literal[False]:  # noqa: D418
        """Check if the first type is a subset of the second."""

    @overload
    @classmethod
    def match(cls, t0: Any, t1: None, intersect: bool = False) -> Literal[False]: ...
    @overload
    @classmethod
    def match[T1](cls, t0: type, t1: TypeArg[T1], intersect: bool = False) -> TypeIs[type[T1]]: ...
    @overload
    @classmethod
    def match[T1](
        cls, t0: MyType, t1: TypeArg[T1], intersect: bool = False
    ) -> TypeIs[MyType[T1]]: ...
    @overload
    @classmethod
    def match[T1](
        cls, t0: tuple[type, ...], t1: TypeArg[T1], intersect: bool = False
    ) -> TypeIs[tuple[type, ...]]: ...
    @classmethod
    def match(cls, t0: TypeArg, t1: TypeArg, intersect: bool = False) -> bool:
        """Check if the first type is valid subset of the second (or intersects, if so set).

        Args:
            t0: The source type.
            t1: The target type.
            intersect: If `True`, check for any overlap between the two types
                       rather than full subset coverage.
        Examples:
            Subset matching is directional; `intersect` loosens it to any overlap::

                >>> from my import tym
                >>> tym.match(int, int | str)
                True
                >>> tym.match(int | str, int)
                False
                >>> tym.match(int | str, int, intersect=True)
                True
        """
        # I. Parse the types (if they're already parsed, no work is done)
        t0, t1 = MyType.new(t0), MyType.new(t1)
        r0, r1 = t0.root, t1.root
        m0, m1 = t0.main, t1.main
        if t0 == t1:
            return True

        # II.i. The POS/NEG sentinels (bare `Any` / `None`, i.e. unspecified) are wildcards
        # that match anything in either direction. An *explicit* NoneType built via
        # MyType.parse(NoneType) is a distinct concrete instance (not the NEG singleton) and
        # falls through to real matching.
        if r0 is Any or r1 is Any or t0 is MyType.NEG or t1 is MyType.NEG:
            return True
        elif not (t0 and t1):
            return False

        # II.i. Check cache based on simple stringification
        cache_key = str(r0), str(r1) + ('.I' if intersect else '')
        if (cached := TypeMatch.MATCH_CACHE[cache_key]) is not None:
            return cached

        _recur = ft.partial(cls.match, intersect=intersect)
        ret = False
        if t0.literal_members or t1.literal_members:
            # III.i. Literal case
            ret = cls._match_literals(t0, t1, intersect)
        elif not (m0 and m1):
            # III.ii. Unhandled case
            pass
        elif t0.is_split or t1.is_split:
            # III.iii. Unions case
            lhs_options = t0.args if t0.is_split else [t0]
            rhs_options = t1.args if t1.is_split else [t1]
            fn = any if intersect else all
            ret = fn(any(_recur(lo, ro) for ro in rhs_options) for lo in lhs_options)
        else:
            # IV. Main case: check for simple subclass coverage for the main type and any children
            with ctx.suppress(TypeError):
                ret = issubclass(m0, m1) or (intersect and issubclass(m1, m0))
            # A `str`/`bytes` iterates into chars/ints -- never arbitrary elements -- so it must
            # not be judged a subset of an element-constrained, non-string iterable (e.g. the
            # `Iterable[tuple[...]]` member of `Map`), even though `issubclass(str, Iterable)`
            # holds.
            if ret and t1.vals and cls.is_string_type(t0) and not cls.is_string_type(t1):
                ret = False
            # An unconstrained parent element type (keys/vals is None) accepts any child, so only
            # recurse when the parent actually constrains that part (e.g. Color is a subset of the
            # bare Enum, and a bare Mapping is a subset of Mapping[str, ...]).
            ret = (
                ret
                and (not t1.keys or _recur(t0.keys, t1.keys))
                and (not t1.vals or _recur(t0.vals, t1.vals))
            )

        # Cache & return
        TypeMatch.MATCH_CACHE[cache_key] = ret
        return ret

    # ---- STREAM ----
    @overload
    @classmethod
    def is_stream_type(cls, tvar: MyType) -> TypeIs[MyType[Stream]]: ...
    @overload
    @classmethod
    def is_stream_type(cls, tvar: type) -> TypeIs[type[Stream]]: ...
    @classmethod
    def is_stream_type(cls, tvar: MyType | type) -> bool:
        """Determine if the given type is a Stream type."""
        return bool(main := MyType.new(tvar).main) and issubclass(main, Stream)

    # ---- STRING ----
    @overload
    @classmethod
    def is_string_type(cls, tvar: MyType) -> TypeIs[MyType[String]]: ...
    @overload
    @classmethod
    def is_string_type(cls, tvar: type) -> TypeIs[type[String]]: ...
    @classmethod
    def is_string_type(cls, tvar: MyType | type) -> bool:
        """Determine if the given type is a String type."""
        return bool(main := MyType.new(tvar).main) and issubclass(main, String)

    # ---- SCALAR ----
    @overload
    @classmethod
    def is_scalar_type(cls, tvar: MyType) -> TypeIs[MyType[Scalar]]: ...
    @overload
    @classmethod
    def is_scalar_type(cls, tvar: type) -> TypeIs[type[Scalar]]: ...
    @classmethod
    def is_scalar_type(cls, tvar: MyType | type) -> bool:
        """Determine if the given type is a Scalar type."""
        return bool(main := MyType.new(tvar).main) and issubclass(main, Scalar)

    # ---- TIME ----
    @overload
    @classmethod
    def is_time_type(cls, tvar: MyType) -> TypeIs[MyType[Time]]: ...
    @overload
    @classmethod
    def is_time_type(cls, tvar: type) -> TypeIs[type[Time]]: ...
    @classmethod
    def is_time_type(cls, tvar: MyType | type) -> bool:
        """Determine if the given type is a Time type."""
        return bool(main := MyType.new(tvar).main) and issubclass(main, Time)

    # ---- ATOM ----
    @overload
    @classmethod
    def is_atom_type(cls, tvar: MyType) -> TypeIs[MyType[Atom]]: ...
    @overload
    @classmethod
    def is_atom_type(cls, tvar: type) -> TypeIs[type[Atom]]: ...
    @classmethod
    def is_atom_type(cls, tvar: MyType | type) -> bool:
        """Determine if the given type is an Atom type."""
        tvar = MyType.new(tvar)
        return bool(tvar.main) and (
            cls.is_string_type(tvar)
            or cls.is_scalar_type(tvar)
            or cls.is_time_type(tvar)
            or issubclass(tvar.main, Enum)
        )

    # ---- VEC ----
    @overload
    @classmethod
    def is_vec_type(cls, tvar: MyType) -> TypeIs[MyType[Vec]]: ...
    @overload
    @classmethod
    def is_vec_type(cls, tvar: type) -> TypeIs[type[Vec]]: ...
    @classmethod
    def is_vec_type(cls, tvar: MyType | type) -> bool:
        """Determine if the given type is a Vec type."""
        return bool(main := MyType.new(tvar).main) and issubclass(main, Vec)

    # ---- MAP ----
    @overload
    @classmethod
    def is_map_type(cls, tvar: MyType) -> TypeIs[MyType[Mapping | ItemsView]]: ...
    @overload
    @classmethod
    # `type[]` cannot wrap `Map` (parametrized members, per typing spec) -- narrow to bare bases.
    def is_map_type(cls, tvar: type) -> TypeIs[type[Mapping | ItemsView]]: ...
    @classmethod
    def is_map_type(cls, tvar: MyType | type) -> bool:
        """Determine if a type is a Map: a `Mapping`/`ItemsView`, or an iterable of pairs."""
        tvar = MyType.new(tvar)
        main = tvar.main
        if not main:
            return False
        with ctx.suppress(TypeError):
            if issubclass(main, Maps):
                return True
            # An iterable of `(key, value)` pairs (e.g. `Iterator[tuple[str, int]]`) is map-like.
            # Tested inline rather than via `is_iter_type` to avoid mutual recursion on abstract
            # iterables, and gated on `vals` so a bare iterable is not mistaken for a map.
            if (
                issubclass(main, Iterable)
                and tvar.vals
                and not (cls.is_string_type(main) or cls.is_vec_type(main))
                and cls.match(tvar.vals, tuple[Any, Any])
            ):
                return True
        return False

    # ---- ITER ----
    @overload
    @classmethod
    def is_iter_type(cls, tvar: MyType) -> TypeIs[MyType[Iter]]: ...
    @overload
    @classmethod
    def is_iter_type(cls, tvar: type) -> TypeIs[type[Iter]]: ...
    @classmethod
    def is_iter_type(cls, tvar: MyType | type) -> bool:
        """Determine if the given type is a non-struct, non-atomic Iterable (mostly iterators)."""
        return (
            bool(main := MyType.new(tvar).main)
            and issubclass(main, Iter)
            and not (cls.is_string_type(main) or cls.is_vec_type(main) or cls.is_map_type(main))
        )

    # ---- STRUCT ----
    @overload
    @classmethod
    def is_struct_type(cls, tvar: MyType) -> TypeIs[MyType[Vec | Mapping | ItemsView | Model]]: ...
    @overload
    @classmethod
    # `type[]` cannot wrap `Struct` (its `Map` arm has parametrized members) -- bare bases instead.
    def is_struct_type(cls, tvar: type) -> TypeIs[type[Vec | Mapping | ItemsView | Model]]: ...
    @classmethod
    def is_struct_type(cls, tvar: MyType | type) -> bool:
        """Determine if the given type is a Struct type (any Iterable or Model)."""
        return bool(main := MyType.new(tvar).main) and (
            issubclass(main, Iterable) or cls.is_model_type(tvar)
        )

    # ---- FUNC ----
    @overload
    @classmethod
    def is_func_type(cls, tvar: MyType) -> TypeIs[MyType[Func]]: ...
    @overload
    @classmethod
    def is_func_type(cls, tvar: type) -> TypeIs[type[Func]]: ...
    @classmethod
    def is_func_type(cls, tvar: MyType | type) -> bool:
        """Determine if the given type is a Func type."""
        return bool(main := MyType.new(tvar).main) and issubclass(main, Funcs)

    # ---- MODEL ----
    @overload
    @classmethod
    def is_model_type[M: Model](cls, tvar: MyType) -> TypeIs[MyType[M]]: ...
    @overload
    @classmethod
    def is_model_type[M: Model](cls, tvar: type) -> TypeIs[type[M]]: ...
    @classmethod
    def is_model_type(cls, tvar: MyType | type) -> bool:
        """Determine if the given type is a Model type (pydantic model, dataclass, or TypedDict)."""
        tvar = MyType.new(tvar)
        main = tvar.main
        return (
            bool(main)
            and inspect.isclass(main)
            and (
                issubclass(main, pyd.BaseModel)
                or is_typeddict(main)
                or pyd.dataclasses.is_pydantic_dataclass(main)
                or is_dataclass(main)
            )
        )


tym = typematch = TypeMatch
