############
### HEAD ###
############
# Standard imports
from __future__ import annotations
from typing import Any, ClassVar, Literal, Self, TypeGuard, Unpack, overload, TypeIs, TypeAlias
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
import itertools as it
import types
import typing as ty
import inspect
import contextlib as ctx
import dataclasses
from enum import Enum
import functools as ft

# Modular imports
import pydantic as pyd
import more_itertools as mi

# Local imports
from ..infra.types import (
    Dataclass,
    Stream,
    Streams,
    String,
    Strings,
    Scalar,
    Scalars,
    Time,
    Times,
    Atom,
    Vec,
    Vecs,
    Iter,
    Map,
    Maps,
    Model,
    Struct,
    Structs,
    Func,
    Funcs,
)
from ..utils import ut
from ..caches import Cache, NestedCache

# SpecialFormField = Annotated[ty._SpecialForm, ut.pyd_schemify(ty._SpecialForm)]
type TypeArg[T = Any] = type[T] | MyType[T] | tuple[type[T], ...] | TypeAlias | None
type AnyType[T] = type[T] | MyType[T]


############
### BODY ###
############
@ft.total_ordering
class MyType[T](pyd.BaseModel, covariant=True):
    """A wrapper for any type annotation that normalizes the wide variety of interfaces."""

    #: If any of these types are passed into `parse()`, no work will be done and an "inactive"
    #: instance will be returned (i.e. it will only have `root` defined, and will be falsey).
    UNHANDLED_TYPES: ClassVar[set[str]] = {
        '',
        'Any',
        # 'object',
        # Functional
        'Generator',
        'Iterator',
        'AsyncIterator',
        'AsyncIterable',
        'AsyncGenerator',
        'Coroutine',
        # Special Forms
        'Callable',  # deprecated
        'Type',  # deprecated
        'NoReturn',
        'TypeGuard',
        'NewType',  # shouldn't exist at runtime
        # >= 3.10
        'Self',
        'Never',
        'LiteralString',  # Too complicated & rare
        'Concatenate',
        'TypeAlias',  # Should never come up, but seems to for pyrefly
        # >= 3.13
        'TypeIs',
        'ReadOnly',
        # from types module:
        'NoneType',
        'EllipsisType',
        'NotImplementedType',
        'CapsuleType',
        'Ellipsis',
        # Possible, but not yet handled:
        'TypedDict',  # treat like BaseModel
        'NamedTuple',  # treat like tuple but w/ names
        'Protocol',  # try isinstance
        ### IMPORTANT: TypeVars are completely unhandled as of now.
        ### Could do it with .__bound__, perhaps?
        'TypeVar',
        'TypeVarTuple',
        'ParamSpec',
        'ParamSpecArgs',
        'ParamSpecKwargs',
    }
    SIMPLE_FORMS: ClassVar[set[str]] = {
        'ClassVar',
        'Optional',
        'Annotated',
        'Required',
        'NotRequired',
        'Final',
    }

    PARSE_CACHE: ClassVar[Cache[int, MyType]] = Cache()
    MATCH_CACHE: ClassVar[NestedCache[tuple[str, str], bool]] = NestedCache(signature=(str, str))
    RAISE: ClassVar[bool] = False

    #: The original type annotation passed in, which may be unparseable.
    root: type[T] | Any | None = None

    main: type | None = None
    """
    The main type (e.g. `dict`, `list`, `int`, etc.) or `None` if unparseable. 
    This applies to cases such as:
      - Generics (e.g. `dict[str, int]`),
      - Literals (e.g. `Literal["a", "b"]`)
      - "Special Types" (e.g. `Optional[int]`, `Union[int, None]`, `Annotated[int, ...]`)
    For unions, this is `types.UnionType` and the args are the member types.
    """

    #: The type of generic's "values", which are usually the *final* type argument
    vals: MyType | None = None

    #: For mappings, the type of the keys. For other types, None.
    keys: MyType | None = None

    #: The name of the type (e.g. 'dict', 'Union', 'Annotated', etc.) or '' if unparseable.
    name: str = ''

    #: A unique serialized identifier for this type, used for caching.
    uid: int = 0

    #: The origin of the type, if it has one (e.g. `dict` for `dict[str, int]`); otherwise None.
    origin: type | None = None
    args: tuple[MyType, ...] = tuple()
    literal_members: list[Any] = []
    is_split: bool = False

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __init__(self, root: type[T] | Any | None = None, uid: int = 0, **kwargs):
        """Initialize a MyType instance with the given source type and unique identifier."""
        super().__init__(root=root, uid=uid, **kwargs)

    @overload
    @classmethod
    def new[R](cls, root: type[R] | MyType[R]) -> MyType[R]: ...

    @overload
    @classmethod
    def new[R](cls, root: R) -> MyType[R]: ...

    @classmethod
    def new[R](cls, root: R | type[R] | MyType[R]) -> MyType[R]:
        """Create a new MyType instance by parsing a type OR inferring the full type of a value."""
        if not root:
            # 0. None -> uninitialized Any
            return cls()
        elif isinstance(root, MyType):
            return root
        elif isinstance(root, type):
            # I.i. Parse literal types
            return cls.parse(root)
        elif (name := getattr(root, '__name__', '')) and (
            name in cls.UNHANDLED_TYPES or name in cls.SIMPLE_FORMS
        ):
            # I.ii. Parse special forms
            return cls.parse(root)
        else:
            # II. Infer the type annotation of some data
            return cls.metaparse(root)

    @classmethod
    def parse(cls, root: Any, throw: bool = True) -> MyType:
        """Decompose a given type so that other methods can intelligently handly each part in turn.

        By far the most likely usecase is for containers such as `dict[str, int]` (which becomes the
        tuple `(dict, str, int)`) and `list[int]` (which becomes `(list, int, None)`), but it's
        useful for other generics, unions (e.g. `string | int`), and special non-type forms
        (e.g. `Annotated` and `Literal`). See `MyType.UNHANDLED_TYPES` for a best-effort list
        of unhandled annotations.

        Args:
            root: The type annotation to decompose -- either a type, a union of types, or None.
            throw: If True, will re-raise any exceptions encountered during parsing.
        Returns:
            1. The **main type** (e.g. `dict`, `list`, `int`, etc.) or `None` if unparseable.
            2. The **key type** (for mappings) or `None`.
            3. The **value type** (for any generics with just one type arg) or `None`.
        """
        if isinstance(root, MyType):
            return root
        elif root is Ellipsis:
            root = types.EllipsisType
        elif root is None:
            root = types.NoneType
        elif isinstance(root, ty.TypeAliasType):
            root = root.__value__

        try:
            uid = hash(str(root))
            if cached := cls.PARSE_CACHE[uid]:
                return cached

            cls.PARSE_CACHE[uid] = ret = cls(root=root, uid=uid)
            return ret
        except Exception:
            if cls.RAISE or throw:
                raise
            else:
                # Return without attempting to make it valid
                return cls(root=root)

    @classmethod
    def metaparse(cls, data: object) -> MyType:
        """Infer the type annotation of a given data value, recursing into containers.

        Args:
            data: Data value to infer type from.
        Returns:
            Parsed MyType instance representing the inferred type.
        """
        origin = type(data)
        args = []
        if not data or not hasattr(origin, '__class_getitem__'):
            return cls.parse(origin)

        # if isinstance(data, Iterator):
        #     _, cpy = mi.spy(data)
        #     data = list(cpy)

        if isinstance(data, Vecs):
            valss = list(filter(bool, map(cls.metaparse, data)))
            if isinstance(data, tuple):
                if len(set(valss)) == 1:
                    t = valss[0].root
                    assert t is not None
                    args = [t, Ellipsis]
                else:
                    args = [vt.root for vt in valss if vt.root is not None]
            else:
                args = [cls._condense_args(valss)]
        elif isinstance(data, Maps):
            _val = dict(data)
            _keys, _vals = _val.keys(), _val.values()
            keyss, valss = [ut.condense(map(cls.metaparse, _i)) for _i in (_keys, _vals)]
            args = [cls._condense_args(keyss), cls._condense_args(valss)]

        return cls.parse(origin[*args] if args else origin)  # type: ignore

    @pyd.model_validator(mode='after')
    def _process_src(self) -> Self:
        """Process the source type annotation to populate the MyType fields."""
        # 0. Validate & parse the source type
        if not self.root or not self.uid:
            return self
        self.name, self.origin, args = self._read(self.root)

        if options := self._split(self.name, self.origin, args):
            # I. Split for divergent types
            if len(options) == 1 and self.origin is Unpack:
                options = ty.get_args(options[0])
            self.args = tuple(self._process_args(options))
            self.is_split = True
            self.main = types.UnionType
        elif self.name in self.UNHANDLED_TYPES:
            # Ignore unhandled types
            pass
        elif self.name in self.SIMPLE_FORMS:
            # Unwrap simple forms (e.g. `Annotated[str]`)
            if contents := mi.first(filter(bool, self._process_args(args)), None):
                # Overwrite all our pydantic vars with the `contents`'s versions
                # NOTE: keep our uid & root, for caching purposes
                self.main = contents.main
                self.keys = contents.keys
                self.vals = contents.vals
                self.is_split = contents.is_split
                self.name = contents.name
                self.origin = contents.origin
                self.args = (*contents.args,)
                self.literal_members = contents.literal_members
        elif self.origin is Literal:
            # Process literals
            self.literal_members = list(args)
            self.args = tuple(map(self.parse, set(map(type, args))))
        else:
            # Process args for all remaining types, though only generics should have them
            self.args = tuple(self._process_args(args))
            if self.origin:
                self.main = self.origin
                self._process_generic(self.origin)
            elif isinstance(self.root, type):
                # V. MAIN CASE: Catch atomic and un-parametrized types
                self.main = self.root
                self._process_type(self.root)

        return self

    def _process_type(self, root: type) -> None:
        # Niche Subcases
        if issubclass(root, Counter) and not self.vals:
            self.vals = MyType(int)
        elif issubclass(root, Enum):
            self.keys = MyType(str)
            if not self.vals:
                vals = list(root.__members__.values())
                self.vals = MyType.metaparse(vals[0]) if vals else MyType(int)

    def _process_generic(self, origin: type) -> None:
        if not self.args:
            pass
        elif issubclass(origin, tuple):
            # I. Catch tuples (either monotyped or literal)
            if self.args[-1].root is types.EllipsisType:
                if len(self.args) > 1:
                    self.vals = self.args[0]
                else:
                    self.args = tuple()
            else:
                self.literal_members = list(self.args)
        elif len(self) == 1:
            arg = self.args[0]
            if issubclass(origin, Maps):
                # II. Catch mono-keyed maps
                self.keys = arg
                if issubclass(origin, Counter):
                    self.vals = self.parse(int)
            else:
                # III. Catch sequences
                self.vals = arg
        elif len(self) == 2 and issubclass(origin, Maps):
            # IV. Catch maps
            self.keys, self.vals = self.args

    # -------------------
    # `-` Private Methods
    # -------------------
    def _process_args(self, args: tuple) -> Iterator[MyType]:
        """Process type arguments, unpacking Unpack types.

        Args:
            args: Tuple of type arguments to process.
        Yields:
            Parsed MyType instances, with Unpack types expanded.
        """
        for arg in map(self.parse, args):
            if arg.origin is Unpack:
                yield from arg.args
            else:
                yield arg

    @classmethod
    def _condense_args(cls, args: list[MyType]) -> type | types.UnionType:  # type: ignore[not-a-type]
        """Condense multiple type arguments into a single type or union.

        Args:
            args: List of MyType instances to condense.
        Returns:
            Single type if all args are the same, UnionType otherwise.
        """
        uniques = [arg.root for arg in set(args) if arg.root is not None]
        if len(uniques) == 1:
            return uniques[0]
        else:
            acc, *rest = uniques
            for other in rest:
                acc = acc | other
            return acc

    def literal_check(self, value: Any) -> TypeGuard[T]:
        """Check if a value matches this literal type.

        Args:
            value: The value to check.
        Returns:
            True if value matches the literal members.
        """
        if not self.literal_members:
            return False
        elif self.origin is Literal:
            return value in self.literal_members
        elif isinstance(self.origin, type) and issubclass(self.origin, tuple):
            return (
                # Confirm origin
                self.origin is not None
                and issubclass(self.origin, tuple)
                and isinstance(value, self.origin)
                # Confirm args
                and len(self.args) > 0
                and self.args[-1].root is not types.EllipsisType
                and len(value) == len(self.args)
                # Check them in turn
                and all(arg.check(val) for val, arg in zip(value, self.args, strict=True))
            )
        return False

    @classmethod
    def _is_type(cls, tvar: Any) -> TypeGuard[type | types.GenericAlias]:  # type: ignore[not-a-type]
        """Check if a value is a valid, handleable type.

        Args:
            tvar: The value to check.
        Returns:
            True if tvar is a type that can be parsed.
        """
        return bool(
            tvar is not None
            and (name := getattr(tvar, '__name__', ''))
            and name not in cls.UNHANDLED_TYPES
        )

    @classmethod
    def _parseable(cls, tvar: Any) -> TypeGuard[type | tuple[type, ...]]:  # type: ignore[not-a-type]
        """Check if a value or tuple of values are parseable types.

        Args:
            tvar: The value or tuple to check.
        Returns:
            True if tvar contains parseable types.
        """
        if isinstance(tvar, tuple):
            return any(map(cls._parseable, tvar))
        else:
            return cls._is_type(tvar)

    @classmethod
    def _read(cls, tvar: Any) -> tuple[str, type[Any] | None, tuple]:
        """Get the immediate basic values of this type, without any recursion.

        Args:
            tvar: Type to decompose.
        Return:
            1. The type's name.
            2. The type's origin (if any).
            3. The type's args (if any).
        """
        if tvar is None:
            return '', None, tuple()
        elif isinstance(tvar, tuple):
            return '', None, tvar

        name = str(getattr(tvar, '__name__', ''))
        origin = ty.get_origin(tvar)
        args = ty.get_args(tvar)

        if not (origin or args):
            with ctx.suppress(Exception):
                # III.i. Handle user defined generics that don't register origin/args properly
                if inspect.isclass(tvar) and len(orig_bases := types.get_original_bases(tvar)) == 1:
                    base = orig_bases[0]
                    # _origin = ty.get_origin(base)
                    _args = ty.get_args(base)
                    if _args:
                        origin = tvar
                        args = _args

        return name, origin, args

    @classmethod
    def _split(cls, name: str, origin: Any | None, args: tuple) -> tuple:
        """Decompose a union or tuple type into its member types.

        Args:
            name: Name of the type.
            origin: Origin of the type.
            args: Arguments of the type.
        Returns:
            Tuple of member types if it's a union/tuple, empty tuple otherwise.
        """
        if name == '' or len(args) == 0:
            return args
        elif name in {'Union', 'Unpack', 'Optional'} or isinstance(origin, types.UnionType):
            return args
        else:
            return tuple()

    # -------------------
    # `+` Primary Methods
    # -------------------
    @property
    def rtype(self) -> type[T]:
        """Get the original type annotation that this MyType instance represents."""
        ret = self.root
        if isinstance(ret, type):
            return ret
        elif self.is_split:
            if self.origin is Unpack and len(self) == 1:
                return self.args[0].rtype
            elif self.origin is types.UnionType:
                return ty.Union[self.args]  # type: ignore
        elif len(self) > 0 and isinstance(self.args[0].root, type):
            return self.args[0].root
        return Any  # type: ignore

    # ------------------
    # `*` Public Methods
    # ------------------
    def __len__(self) -> int:
        return len(self.args)

    def __bool__(self) -> bool:
        return self.main is not None or len(self.literal_members) > 0

    def __str__(self) -> str:
        return f'{self.root}'

    def __repr__(self) -> str:
        parts = []
        if self.main is not None:
            parts.append(f'main={self.main}')
        if self.keys is not None:
            parts.append(f'key={self.keys}')
        if self.vals is not None:
            parts.append(f'val={self.vals}')
        if self.literal_members:
            parts.append('LITERAL')
        return f'MyType[{self.root}]' + (f'({", ".join(parts)})' if parts else '')

    def __eq__(self, other: object) -> bool:
        if other is None:
            return self.main is None
        elif isinstance(other, MyType):
            return self.uid == other.uid
        elif isinstance(other, type):
            return self.uid == hash(str(other))
        return False

    def __hash__(self) -> int:
        return self.uid

    def __lt__(self, other: object) -> bool:
        if isinstance(other, MyType) and self != other:
            return self.matches(other)
        return False

    def check(self, data: object) -> TypeIs[T]:
        """Check if a given data value matches this type, recursing into containers where needed.

        Args:
            data: The data value to check. Ideally not an exhaustable iter.
        Returns:
            True if *all* aspects of this type are satisfied by this data, including nested types.
        """
        datatype = type(data)

        # Special types
        if self.root is Any or datatype is Any:
            return True
        elif data is None:
            return self.root is types.NoneType
        elif data is Ellipsis:
            return self.root is types.EllipsisType
        elif getattr(datatype, '__name__', '') in self.UNHANDLED_TYPES:
            return False

        # Composite types
        if self.is_split:
            return any(option.check(data) for option in self.args)
        elif self.literal_members:
            return self.literal_check(data)

        # Main cases: normal types, probably nested
        if self.main is None:
            return False
        elif not isinstance(data, self.main):
            return False
        elif self.keys is not None and self.vals is not None and isinstance(data, Mapping):
            if items := ut.map_items(data):
                keys, vals = mi.unzip(items)
                return all(
                    it.chain(
                        self.keys.check_iter(keys),
                        self.vals.check_iter(vals),
                    )
                )
        elif self.vals is not None and isinstance(data, Iterable):
            return all(self.vals.check_iter(data))

        return True

    @overload
    def __contains__(self, child: None) -> Literal[False]: ...
    @overload
    def __contains__(self, child: type) -> TypeIs[type[T]]: ...
    @overload
    def __contains__(self, child: MyType) -> TypeIs[MyType[T]]: ...
    @overload
    def __contains__(self, child: tuple[type, ...]) -> TypeIs[tuple[type[T], ...]]: ...
    @overload
    def __contains__(self, child: object) -> TypeIs[type[T]]: ...
    def __contains__(self, child: MyType | type | object | None) -> bool:
        """Determines whether the preceeding type is a valid subset of this one."""
        if child is None or not isinstance(child, (type, MyType)):
            return False
        else:
            return MyType.match(MyType(child), self)

    @overload
    def __and__(self, other: None) -> Literal[False]: ...
    @overload
    def __and__(self, other: type) -> TypeIs[type[T]]: ...
    @overload
    def __and__(self, other: MyType) -> TypeIs[MyType[T]]: ...
    @overload
    def __and__(self, other: tuple[type, ...]) -> TypeIs[tuple[type[T], ...]]: ...
    @overload
    def __and__(self, other: object) -> TypeIs[type[T]]: ...
    def __and__(self, other: MyType | type | object | None) -> bool:
        """Determines whether the preceeding type is a valid subset of this one."""
        if other is None or not isinstance(other, (type, MyType)):
            return False
        else:
            return MyType.match(MyType(other), self, intersect=True)

    @overload
    @classmethod
    def match[T1](cls, lhs: type, rhs: type[T1], intersect: bool = False) -> TypeIs[type[T1]]: ...
    @overload
    @classmethod
    def match[T1](
        cls, lhs: MyType, rhs: MyType[T1], intersect: bool = False
    ) -> TypeIs[MyType[T1]]: ...
    @overload
    @classmethod
    def match[T1](
        cls, lhs: tuple[type, ...], rhs: type[T1], intersect: bool = False
    ) -> TypeIs[tuple[type[T1], ...]]: ...
    @overload
    @classmethod
    def match[T1](
        cls, lhs: type, rhs: tuple[type[T1], ...], intersect: bool = False
    ) -> TypeIs[type[T1]]: ...
    @overload
    @classmethod
    def match[T1](
        cls, lhs: MyType, rhs: tuple[type[T1], ...], intersect: bool = False
    ) -> TypeIs[MyType[T1]]: ...
    @classmethod
    def match(cls, lhs: TypeArg, rhs: TypeArg, intersect: bool = False) -> bool:
        """Check if the first type is valid subset of the second.

        Args:
            lhs: The source type.
            rhs: The target type.
            intersect: If `True`, check for any overlap between the two types
                       rather than full subset coverage.
        """
        # I. Parse the types (if they're already parsed, no work is done)
        t0, t1 = cls(lhs), cls(rhs)
        r0, r1 = t0.root, t1.root
        m0, m1 = t0.main, t1.main

        # II.i. Any & None (i.e. unspecified) are true, but unhandled MyTypes are always false
        if {r0, r1} & {Any, None}:
            return True
        elif not (t0 and t1):
            return False

        # II.i. Check cache based on simple stringification
        cache_key = str(r0), str(r1)
        if intersect:
            cache_key = (cache_key[0], cache_key[1] + '.I')
        if (cached := cls.MATCH_CACHE[*cache_key]) is not None:
            return cached

        ret = False
        _recur = ft.partial(cls.match, intersect=intersect)
        if t0.is_literal or t1.is_literal:
            # III.i. Literal case
            ret = cls._match_literals(t0, t1, intersect)
        elif not (m0 and m1):
            # III.ii. Unhandled case
            ret = False
        elif t0.is_split or t1.is_split:
            # III.iii. Unions case
            lhs_options = t0.args if t0.is_split else [t0]
            rhs_options = t1.args if t1.is_split else [t1]
            fn = any if intersect else all
            ret = fn(any(_recur(lo, ro) for ro in rhs_options) for lo in lhs_options)
        else:
            # IV. Main case: check for simple subclass coverage for the main type and any children
            ret = (
                (issubclass(m0, m1) or (intersect and issubclass(m1, m0)))
                and _recur(t0.keys, t1.keys)
                and _recur(t0.vals, t1.vals)
            )

        # Cache & return
        cls.MATCH_CACHE[*cache_key] = ret
        return ret

    def matches(self, other: TypeArg) -> bool:
        """Check if this type matches another type or value."""
        return MyType.match(self, MyType(other))

    def within(self, other: TypeArg) -> bool:
        """Check if this type matches another type or value."""
        return MyType.match(self, MyType(other))

    @classmethod
    def _match_literals(cls, t0: MyType, t1: MyType, intersect: bool) -> bool:
        """Check if two literal types match according to subset or intersection logic.

        Args:
            t0: First MyType with literal members.
            t1: Second MyType with literal members.
            intersect: If True, check for intersection; if False, check for subset.
        Returns:
            True if types match according to the specified logic.
        """
        # 0. Setup
        lit0, lit1 = t0.literal_members, t1.literal_members
        o0, o1 = t0.origin, t1.origin

        _recur = ft.partial(cls.match, intersect=intersect)

        if lit0 and lit1:
            assert o0 and o1, "Found literal without an origin, which doesn't make sense."
            if o0 is Literal and o1 is Literal:
                # I.i. Two literals are basically the same as container types, just with objects
                fn = ut.has_any if intersect else ut.has_all
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
                fn = any if intersect else all
                return fn(_recur(arg, t1) for arg in t0.args)
            elif issubclass(o0, m1) and issubclass(m1, tuple):
                if len(t1.args) == 0:
                    # II.ii. Any positional tuple is a subset of its plain base
                    return True
                elif t1.vals:
                    # II.iii. Theoretically, a positional tuple could a subset of a typed tuple
                    #         e.g. tuple[int, str] x tuple[object, ...]
                    return all(_recur(arg, t1.vals) for arg in t0.args)

        elif lit1 and intersect and t0.main:
            # III. Just recurse w/ flipped arguments for DRY reasons
            return cls._match_literals(t1, t0, intersect=False)

        return False

    @property
    def is_literal(self) -> bool:
        """Check if this MyType represents a literal type (i.e. `Literal` or literal `tuple`)."""
        return bool(self.literal_members)

    def check_iter(self, iterable: Iterable) -> Iterator[bool]:
        """Check if values in an iterable match this type.

        Args:
            iterable: The iterable of values to check.
        Yields:
            Boolean for each value indicating if it matches this type.
        """
        yield from map(self.check, iterable)

    def members(self) -> Iterator[MyType]:
        """Yield all field types for Pydantic models or TypedDicts.

        Returns:
            Iterator of MyType instances for each field in the type.
        """
        if not (main := self.main):
            return
        elif issubclass(main, pyd.BaseModel):
            yield from map(self.parse, ut.instance_fields(main).values())
        elif ty.is_typeddict(self.root):
            yield from map(self.parse, self.root.__annotations__.values())
        elif inspect.isclass(main):
            # if c := getattr(main, '__pydantic_fields__', None):
            if pyd.dataclasses.is_pydantic_dataclass(main):
                # Pydantic dataclasses
                pass
            elif dataclasses.is_dataclass(main):
                # Stdlib dataclasses
                pass

    def summarize(self) -> tuple[type | None, type | None, type | None]:
        """Get a simplified summary of this type with just the main types.

        Returns:
            Tuple of (main_type, keys, value_type) where key and value
            are extracted from their respective MyType wrappers.
        """
        if not self:
            return (None, None, None)
        return (
            self.main,
            self.keys.main if self.keys else None,
            self.vals.main if self.vals else None,
        )

    def is_map_item(self) -> bool:
        """Check if this type represents a mapping item (2-tuple key-value pair).

        Returns:
            True if this is a tuple[K, V] with exactly 2 non-None type args.
        """
        return self.main is tuple and (
            (len(self.args) == 2 and self.args[-1].root is not types.EllipsisType)
            or len(self.args) == 0
        )

    # -----------------------
    # Type Function Accessors
    # -----------------------
    @ft.cached_property
    def _is_stream(self) -> bool:
        if self.main:
            return self.is_stream_type(self.main)
        return False

    @ft.cached_property
    def _is_string(self) -> bool:
        if self.main:
            return self.is_string_type(self.main)
        return False

    @ft.cached_property
    def _is_scalar(self) -> bool:
        if self.main:
            return self.is_scalar_type(self.main)
        return False

    @ft.cached_property
    def _is_time(self) -> bool:
        if self.main:
            return self.is_time_type(self.main)
        return False

    @ft.cached_property
    def _is_atom(self) -> bool:
        if self.main:
            return self.is_atom_type(self.main)
        return False

    @ft.cached_property
    def _is_vec(self) -> bool:
        if self.main:
            return self.is_vec_type(self.main)
        return False

    @ft.cached_property
    def _is_map(self) -> bool:
        if self.main:
            return self.is_map_type(self.main)
        return False

    @ft.cached_property
    def _is_iter(self) -> bool:
        if self.main:
            return self.is_iter_type(self.main)
        return False

    @ft.cached_property
    def _is_func(self) -> bool:
        if self.main:
            return self.is_func_type(self.main)
        return False

    @ft.cached_property
    def _is_model(self) -> bool:
        if self.main:
            return self.is_model_type(self.main)
        return False

    # --------------
    # Type Functions
    # --------------
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
        return bool(main := MyType(tvar).main) and issubclass(main, Streams)

    @classmethod
    def is_stream(cls, tvar) -> TypeIs[Stream]:
        """Determine if a variable is a buff."""
        return isinstance(tvar, Streams)

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
        return bool(main := MyType(tvar).main) and issubclass(main, Strings)

    @classmethod
    def is_string(cls, tvar) -> TypeIs[String]:
        """Determine if a variable is a text."""
        return isinstance(tvar, Strings)

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
        return bool(main := MyType(tvar).main) and issubclass(main, Scalars)

    @classmethod
    def is_scalar(cls, tvar) -> TypeIs[Scalar]:
        """Determine if a variable is a num."""
        return isinstance(tvar, Scalars)

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
        return bool(main := MyType(tvar).main) and issubclass(main, Times)

    @classmethod
    def is_time(cls, tvar) -> TypeIs[Time]:
        """Determine if a variable is a time."""
        return isinstance(tvar, Times)

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
        return bool(main := MyType(tvar).main) and (
            cls.is_string_type(main)
            or cls.is_scalar_type(main)
            or cls.is_time_type(main)
            or issubclass(main, Enum)
        )

    @classmethod
    def is_atom(cls, val: object) -> TypeIs[Atom]:
        """Determine if a variable is an atom."""
        return cls.is_string(val) or cls.is_scalar(val) or cls.is_time(val) or isinstance(val, Enum)

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
        return bool(main := MyType(tvar).main) and issubclass(main, Vecs)

    @classmethod
    def is_vec(cls, tvar) -> TypeIs[Vec]:
        """Determine if a variable is a vec."""
        return isinstance(tvar, Vecs)

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
        main = MyType(tvar).main
        if not main:
            return False
        elif issubclass(main, Maps):
            return True
        elif cls.is_iter_type(main):
            pass
        return False

    @classmethod
    def is_map(cls, val: object) -> TypeIs[Map]:
        """Determine if a variable is a map."""
        if val is None or isinstance(val, type):
            return False
        elif isinstance(val, Maps):
            return True
        elif cls.is_iter(val):
            pass
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
        """Determine if a variable is a non-struct, non-atomic Iterable type (mostly iterators)."""
        return (
            bool(main := MyType(tvar).main)
            and issubclass(main, Iterable)
            and not issubclass(main, (str, bytes, *Streams))
        )

    @classmethod
    def is_iter(cls, val: object) -> TypeIs[Iter]:
        """Determine if a variable is an iterable that is NOT of another known type.."""
        return isinstance(val, Iterable) and not isinstance(val, (*Strings, *Structs))

    # ---- STRUCT ----
    @classmethod
    def is_struct_type(cls, tvar: type) -> TypeIs[type[Struct]]:
        """Determine if a variable is a struct type."""
        return isinstance(tvar, type) and (
            cls.is_vec_type(tvar) or cls.is_map_type(tvar) or cls.is_model_type(tvar)
        )

    @classmethod
    def is_struct(cls, val: object) -> TypeIs[Struct]:
        """Determine if a variable is a struct."""
        return cls.is_vec(val) or cls.is_map(val) or cls.is_model(val)

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
        return bool(main := MyType(tvar).main) and issubclass(main, Funcs)

    @classmethod
    def is_func(cls, val: object) -> TypeIs[Func]:
        """Determine if a variable is a func."""
        return callable(val) or isinstance(val, Funcs)

    # ---- MODEL ----
    @overload
    @classmethod
    def is_model_type(cls, tvar: MyType) -> TypeIs[MyType[Model]]: ...
    @overload
    @classmethod
    def is_model_type(cls, tvar: type) -> TypeIs[type[Model]]: ...
    @classmethod
    def is_model_type(cls, tvar: MyType | type) -> bool:
        """Determine if a variable is a model type."""
        return bool(main := MyType(tvar).main) and (
            issubclass(main, pyd.BaseModel) or ty.is_typeddict(main) or cls.is_dataclass(main)
        )

    @classmethod
    def is_dataclass(cls, tvar: type) -> TypeIs[type[Dataclass]]:
        """Determine if a variable is a dataclass type (standardlib or pydantic)."""
        return isinstance(tvar, type) and (
            pyd.dataclasses.is_pydantic_dataclass(tvar) or dataclasses.is_dataclass(tvar)
        )

    @classmethod
    def is_model(cls, val: object) -> TypeIs[Model]:
        """Determine if a variable is a model."""
        return cls.is_model_type(cls.metaparse(val))
