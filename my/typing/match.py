############
### HEAD ###
############
### STANDARD
from typing import overload, ClassVar, TypeIs, Literal, is_typeddict, Any
from collections.abc import Hashable, Iterable
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
    Map,
    Model,
    Struct,
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
    """Type matching utilities for MyType and Typist."""

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

        _recur = ft.partial(cls.match, inter=inter)
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
    def match(cls, t0: None, t1: Any, inter: bool = False) -> Literal[False]: ...
    @overload
    @classmethod
    def match(cls, t0: Any, t1: None, inter: bool = False) -> Literal[False]: ...
    @overload
    @classmethod
    def match[T1](cls, t0: type, t1: TypeArg[T1], inter: bool = False) -> TypeIs[type[T1]]: ...
    @overload
    @classmethod
    def match[T1](cls, t0: MyType, t1: TypeArg[T1], inter: bool = False) -> TypeIs[MyType[T1]]: ...
    @overload
    @classmethod
    def match[T1](
        cls, t0: tuple[type, ...], t1: TypeArg[T1], inter: bool = False
    ) -> TypeIs[tuple[type, ...]]: ...
    @classmethod
    def match(cls, t0: TypeArg, t1: TypeArg, inter: bool = False) -> bool:
        """Check if the first type is valid subset of the second (or intersects, if so set).

        Args:
            t0: The source type.
            t1: The target type.
            inter: If `True`, check for any overlap between the two types
                       rather than full subset coverage.
        """
        # I. Parse the types (if they're already parsed, no work is done)
        t0, t1 = MyType.new(t0), MyType.new(t1)
        r0, r1 = t0.root, t1.root
        m0, m1 = t0.main, t1.main
        if t0 == t1:
            return True

        # II.i. Any & None (i.e. unspecified) are true, but unhandled MyTypes are always false
        if r0 is Any or r1 is Any:
            return True
        elif r0 is None or r1 is None or not (t0 and t1):
            return False

        # II.i. Check cache based on simple stringification
        cache_key = str(r0), str(r1) + ('.I' if inter else '')
        if (cached := TypeMatch.MATCH_CACHE[cache_key]) is not None:
            return cached

        _recur = ft.partial(cls.match, inter=inter)
        ret = False
        if t0.literal_members or t1.literal_members:
            # III.i. Literal case
            ret = cls._match_literals(t0, t1, inter)
        elif not (m0 and m1):
            # III.ii. Unhandled case
            pass
        elif t0.is_split or t1.is_split:
            # III.iii. Unions case
            lhs_options = t0.args if t0.is_split else [t0]
            rhs_options = t1.args if t1.is_split else [t1]
            fn = any if inter else all
            ret = fn(any(_recur(lo, ro) for ro in rhs_options) for lo in lhs_options)
        else:
            # IV. Main case: check for simple subclass coverage for the main type and any children
            with ctx.suppress(TypeError):
                ret = issubclass(m0, m1) or (inter and issubclass(m1, m0))
            ret = ret and _recur(t0.keys, t1.keys) and _recur(t0.vals, t1.vals)

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
        """Determine if a variable is a Stream type."""
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
        """Determine if a variable is a String type."""
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
        """Determine if a variable is a Scalar type."""
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
        """Determine if a variable is a Time type."""
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
        """Determine if a variable is a Atom type."""
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
        """Determine if a variable is a Vec type."""
        return bool(main := MyType.new(tvar).main) and issubclass(main, Vec)

    # ---- MAP ----
    @overload
    @classmethod
    def is_map_type(cls, tvar: MyType) -> TypeIs[MyType[Map]]: ...
    @overload
    @classmethod
    def is_map_type(cls, tvar: type) -> TypeIs[type[Map]]: ...
    @classmethod
    def is_map_type(cls, tvar: MyType | type) -> bool:
        """Determine if a variable is a Map type."""
        tvar = MyType.new(tvar)
        return bool(
            tvar.main
            and (
                issubclass(tvar.main, Map)
                or (cls.is_iter_type(tvar.main) and tym.match(tvar.vals, tuple[Any, Any]))
            )
        )

    # ---- ITER ----
    @overload
    @classmethod
    def is_iter_type(cls, tvar: MyType) -> TypeIs[MyType[Iter]]: ...
    @overload
    @classmethod
    def is_iter_type(cls, tvar: type) -> TypeIs[type[Iter]]: ...
    @classmethod
    def is_iter_type(cls, tvar: MyType | type) -> bool:
        """Determine if a variable is a non-struct, non-atomic Iterable type (mostly iterators)."""
        return (
            bool(main := MyType.new(tvar).main)
            and issubclass(main, Iter)
            and not (cls.is_string_type(main) or cls.is_vec_type(main) or cls.is_map_type(main))
        )

    # ---- STRUCT ----
    @overload
    @classmethod
    def is_struct_type(cls, tvar: MyType) -> TypeIs[MyType[Struct]]: ...
    @overload
    @classmethod
    def is_struct_type(cls, tvar: type) -> TypeIs[type[Struct]]: ...
    @classmethod
    def is_struct_type(cls, tvar: MyType | type) -> bool:
        """Determine if a variable is a struct type."""
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
        """Determine if a variable is a Func type."""
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
        """Determine if a variable is a model type."""
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
