############
### HEAD ###
############
# Standard imports
from __future__ import annotations
from types import (
    UnionType,
    GenericAlias,
    EllipsisType,
    NoneType,
    get_original_bases,
    FunctionType,
    BuiltinFunctionType,
)
from typing import (
    Any,
    ClassVar,
    Literal,
    Self,
    TypeGuard,
    Unpack,
    overload,
    TypeIs,
    is_typeddict,
    TypeAliasType,
    get_args,
    get_origin,
    Union,
    IO,
)
from collections import Counter, deque
from collections.abc import (
    Iterable,
    Iterator,
    Mapping,
    Callable,
    AsyncIterable,
    ItemsView,
    Set,
)
from io import StringIO, BytesIO
import inspect
import dataclasses
from enum import Enum, Flag
from datetime import date, time, datetime, timedelta
import functools as ft
import itertools as it
import contextlib as ctx

# Modular imports
import pydantic as pyd
from pydantic import BaseModel
import more_itertools as mi

# Local imports
from ..infra.types import (
    Object,
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
    Dataclass,
)
from ..utils import ut
from ..caches import Cache
from ._TypingBase import _TypingBase

############
### DATA ###
############
type TypeArg[T = Any] = type[T] | MyType[T] | tuple[type[T], ...] | Any | None


class _Filters(pyd.BaseModel):
    #: Universal types are treated as the base of everything
    universal: set[str] = {'', 'Unknown', 'Any'}
    #: Functional types
    funcs: set[str] = {'Callable', 'Coroutine'}
    #: Structural types (i.e. vectors, maps, and models)
    structs: set[str] = {
        'AsyncGenerator',
        'AsyncIterable',
        'AsyncIterator',
        'Generator',
        'Iterator',
        'TypedDict',
    }
    #: Simple wrapper types
    monoarg: set[str] = {
        'Annotated',
        'ClassVar',
        'Final',
        'NoneType',
        'NotRequired',
        'Required',
    }
    #: Wrappers of more than one type at once
    polyarg: set[str] = {'Union', 'Unpack', 'Optional'}

    #: Forms that treat as `None` on sight.
    unhandled: set[str] = {
        'Type',  # deprecated
        'NoReturn',
        'TypeGuard',
        'NewType',  # shouldn't exist at runtime
        # >= 3.10
        'Self',
        'Never',
        'LiteralString',  # Too complicated & rare
        'Concatenate',
        # >= 3.13
        'ReadOnly',
        'CapsuleType',
        'NotImplementedType',
        # Possible, but not yet handled:
        'NamedTuple',  # treat like tuple but w/ names?
        'Protocol',  # try isinstance?
        #: **IMPORTANT:** TypeVars are completely unhandled as of now.
        #: Could do it with `TypeVar.__bound__()`, perhaps?
        'TypeVar',
        'TypeVarTuple',
        'ParamSpec',
        'ParamSpecArgs',
        'ParamSpecKwargs',
        # From the `types` module
        'TypeIs',
        'Ellipsis',
        'EllipsisType',
        'TypeAlias',
        'TypeAliasType',
    }

    def __contains__(self, other: object) -> bool:
        if not isinstance(other, str):
            other = getattr(other, '__name__', '')
        return len(other) > 0 and ut.has_any(
            other, (f for f in it.chain(*self.model_dump().values()))
        )


############
### BODY ###
############
@ft.total_ordering
class MyType[T](_TypingBase, pyd.BaseModel):
    """A wrapper for any type annotation that normalizes the wide variety of interfaces.

    #### Examples
    Consider this simplified subset of the hierarchy:
    ```py
    str_t = MyType(str)
    bytes_t = MyType(bytes)
    int_t = MyType(int)
    float_t = MyType(float)

    String = str | bytes
    string_t = MyType(String)
    Scalar = int | float
    scalar_t = MyType(Scalar)

    Atom = str | int | bytes | float
    atom_t = MyType(Atom)
    ```

    ##### `__and__()`
    ```py
    # Affirms if either is part of the other, fails otherwise
    assert str_t & atom_t
    assert atom_t & str_t
    assert not str_t & int_t

    # Works with raw or wrapped types as long as at least one side is wrapped
    assert str & atom_t and str_t & Atom
    assert atom_t & str and Atom & str_t
    #! assert str & Atom and Atom & str

    # Works with type tuples and unions (when LHS is wrapped)
    assert str_t & (str | Scalar)
    assert str_t & (str, Scalar)
    assert not str_t & (bytes, Scalar)
    ```

    ##### `__contains__()`
    ```py
    # Determines whether the LHS is a subset of the RHS, but not the other way around.
    assert str in atom_t
    assert Atom not in str_t

    # RHS must be a MyType.
    #! assert str in Atom

    # Works with tuples
    assert str in (str_t, Scalar)

    # def ex[T](tvar: type[T]) -> None:
    #     target = MyType(tvar)
    ```


    ### "Main" types (i.e. `MyType.main`)

    The main type of an instance represents the most meaningfully *active* part of that type in
    this moment. Some cases:

    ```py
    assert MyType(dict[str, int]).main is dict
    assert MyType(Literal['a', 'b']).main is None
    assert MyType(Optional[int]).main is None
    ```
    Some cases:
      - Generics (e.g. `dict[str, int]`) produce
      - Literals (e.g. `Literal["a", "b"]`)
      - "Special Types" (e.g. `Optional[int]`, `Union[int, None]`, `Annotated[int, ...]`)
    For unions, this is `types.UnionType` and the args are the member types.
    """

    #: If any of these types are passed into `parse()`, no work will be done and an "inactive"
    #: instance will be returned (i.e. it will only have `root` defined, and will be falsey).
    FILTERS: ClassVar[_Filters] = _Filters()

    PARSE_CACHE: ClassVar[Cache[int, MyType]] = Cache()
    RAISE: ClassVar[bool] = False

    IDXS: ClassVar[dict[str, MyType]] = {}

    #: The original type annotation passed in, which may be unparseable.
    root: type[T] | Any | None = None

    #: The name of the type (e.g. 'dict', 'Union', 'Annotated', etc.) or '' if unparseable.
    name: str = ''

    #: A unique serialized identifier for this type, used for caching.
    uid: int = 0

    main: type | None = None
    """
    The main type, which usually just means the type itself or its origin. Is `None` if unparseable.
    See the discussion in the class-level documentation.
    """

    #: The type of generic's "values", which are usually the *final* type argument
    vals: MyType | None = None

    #: For mappings, the type of the keys. For other types, None.
    keys: MyType | None = None

    #: The arguments of generic types; only needed for advanced usecases.
    args: tuple[MyType, ...] = tuple()

    # ---- Internal attributes ----

    #: The origin of the type, if it has one (e.g. `dict` for `dict[str, int]`); otherwise None.
    origin: type | None = None

    #: For literal types, the list of literal members (e.g. `["a", "b"]` for `Literal["a", "b"]`).
    literal_members: list[Any] = []

    #: Whether this type represents a union of alternatives, matching any of its consituents.
    is_split: bool = False

    # -------------------
    # `.` Initial Methods
    # -------------------
    @overload
    def __init__[R = Any](self: MyType[R]): ...
    @overload
    def __init__[R: NoneType](self: MyType[R], root: None, uid: int = 0, **kwargs): ...
    @overload
    def __init__[R](self: MyType[R], root: TypeArg[R], uid: int = 0, **kwargs): ...
    # @overload
    # def __init__[R](self: MyType[R], root: R, uid: int = 0, **kwargs): ...
    def __init__[R](self, root: TypeArg[R] = Any, uid: int = 0, **kwargs):
        """Initialize a MyType instance with the given source type and unique identifier."""
        super().__init__(root=root, uid=uid or hash(str(root)), **kwargs)

    @overload
    @staticmethod
    def new() -> MyType[Any]: ...
    @overload
    @staticmethod
    def new(root: None) -> MyType[NoneType]: ...
    @overload
    @staticmethod
    def new[R](root: TypeArg[R]) -> MyType[R]: ...
    @overload
    @staticmethod
    def new[R](root: tuple[type[R], ...]) -> MyType[Union[type[R], ...]]: ...
    @overload
    @staticmethod
    def new[R](root: type[R] | MyType[R]) -> MyType[R]: ...
    @overload
    @staticmethod
    def new[R](root: R) -> MyType[R]: ...
    @staticmethod
    def new(root: TypeArg | Any | None = None) -> MyType:
        """Create a new MyType instance by parsing a type OR inferring the full type of a value."""
        cls = MyType
        if root is None:
            # 0. None -> uninitialized Any
            return cls()
        name = getattr(root, '__name__', '')

        if isinstance(root, (type, MyType, TypeAliasType, tuple)):
            # I.i. Parse direct types
            return cls.parse(root)

        if name.startswith('TypeAlias') and (val := getattr(root, '__value__', None)) is not None:
            return cls.parse(val)
        elif name in cls.FILTERS.universal:
            return cls()
        elif name in (cls.FILTERS.monoarg,):
            # I.ii. Parse special forms
            return cls.parse(root)

        # II. Infer the type annotation of *data*
        return cls.typeof(root)

    @overload
    @classmethod
    def parse[Rm: MyType](cls, root: Rm, throw: bool = True) -> Rm: ...
    @overload
    @classmethod
    def parse[R](cls, root: type[R], throw: bool = True) -> MyType[R]: ...
    @overload
    @classmethod
    def parse[Rt: tuple[type, ...]](cls, root: Rt, throw: bool = True) -> MyType[Rt]: ...
    @overload
    @classmethod
    def parse(cls, root: UnionType, throw: bool = True) -> MyType: ...
    @overload
    @classmethod
    def parse(cls, root: TypeAliasType, throw: bool = True) -> MyType: ...
    @overload
    @classmethod
    def parse(cls, root: None, throw: bool = True) -> MyType[NoneType]: ...
    @overload
    @classmethod
    def parse(cls, root: object, throw: bool = True) -> MyType: ...
    @classmethod
    def parse[R](cls, root: object, throw: bool = True) -> MyType:
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
            root = EllipsisType  # type: ignore
        elif root is None:
            root = NoneType  # type: ignore
        elif isinstance(root, TypeAliasType):
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
    def typeof[R: object](cls, data: R) -> MyType[R]:
        """Infer the type annotation of a given data value, recursing into containers.

        Args:
            data: Data value to infer type from.
        Returns:
            Parsed MyType instance representing the inferred type.
        """
        origin = type(data)
        args = []
        if not data or not hasattr(origin, '__class_getitem__'):
            return cls.parse(origin)  # type: ignore

        if cls._ty().is_vec(data):
            valss = ut.condense(map(cls.typeof, data))
            if isinstance(data, tuple):
                if len(set(valss)) == 1:
                    t = valss[0].root
                    assert t is not None
                    args = [t, Ellipsis]
                else:
                    args = [vt.root for vt in valss if vt.root is not None]
            else:
                args = [cls._condense_args(valss)]
        elif cls._ty().is_map(data):
            _val = dict(data)
            _keys, _vals = _val.keys(), _val.values()
            keyss, valss = [ut.condense(map(cls.typeof, _i)) for _i in (_keys, _vals)]
            args = [cls._condense_args(keyss), cls._condense_args(valss)]

        return cls.parse(origin[*args] if args else origin)  # type: ignore

    @pyd.model_validator(mode='after')
    def _process_src(self) -> Self:
        """Process the source type annotation to populate the MyType fields."""
        # 0. Validate & parse the source type
        if not self.root or not self.uid:
            return self
        self.name, self.origin, args = self._read(self.root)

        if branches := self._split(self.name, self.origin, args):
            # I. Split for divergent types (e.g. `Union[int, str]`)
            self.args = tuple(self._process_args(branches))
            self.is_split = True
            self.main = UnionType
        elif self.name in self.FILTERS.unhandled:
            # II. Ignore unhandled types, just setting self.origin for the curious & persistent
            pass
        elif self.name in self.FILTERS.monoarg:
            # III. Unwrap simple forms (e.g. `Annotated[str]`)
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
            # IV. Process literals
            self.literal_members = list(args)
            self.args = tuple(set(map(MyType.new, args)))
        else:
            # V. Process args for all remaining types, though only generics should have them
            self.args = tuple(self._process_args(args))
            if self.origin:
                # V.i. Parameterized Generics (e.g. structs)
                self.main = self.origin
                self._process_generic(self.origin, self.args)
            elif isinstance(self.root, type):
                # V.ii. Atomics (e.g. strings, unparameterized structs)
                self.main = self.root
                # Niche Subcases
                if issubclass(self.root, Counter) and not self.vals:
                    self.vals = MyType.new(int)
                elif issubclass(self.root, Enum):
                    self.keys = MyType.new(str)
                    if not self.vals:
                        vals = list(self.root.__members__.values())
                        self.vals = MyType.typeof(vals[0]) if vals else MyType.new(int)
        return self

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

    def _process_generic(
        self, origin: type, args: tuple[MyType, ...]
    ) -> tuple[MyType | None, MyType | None]:
        """Process the type arguments for a generic origin and its arguments.

        Returns:
            A (key, val) type annotation 2-tuple.
        """
        n = len(args or [])
        if n == 0:
            # 0. No args -> just set the main type
            self.main = origin
        elif issubclass(origin, tuple):
            # I. Catch tuples (either monotyped or literal)
            if args[-1].root is EllipsisType:
                if n > 1:
                    self.vals = args[0]
                else:
                    self.args = tuple()
            else:
                self.literal_members = list(args)
        elif n == 1:
            arg = args[0]
            if self.ty.is_map(origin):
                # II. Catch mono-keyed maps (e.g. Counters)
                if issubclass(origin, Counter):
                    return arg, self.parse(int)
            else:
                # III. Catch any generics with singular values -- the most common kind by far
                return None, arg
        elif n == 2 and self.ty.is_map(origin):
            # IV. Catch double-keyed (key+val) maps
            return args[0], args[1]
        return None, None

    @classmethod
    def _condense_args(cls, args: list[MyType]) -> type | UnionType:  # type: ignore[not-a-type]
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

    @classmethod
    def _is_type(cls, tvar: Any) -> TypeGuard[type | GenericAlias]:  # type: ignore[not-a-type]
        """Check if a value is a valid, handleable type.

        Args:
            tvar: The value to check.
        Returns:
            True if tvar is a type that can be parsed.
        """
        return bool(
            tvar is not None
            and (name := getattr(tvar, '__name__', ''))
            and name not in cls.FILTERS.unhandled
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
            return 'Union', None, tvar

        name = str(getattr(tvar, '__name__', ''))
        origin = get_origin(tvar)
        args = get_args(tvar)

        if not (origin or args):
            with ctx.suppress(Exception):
                # Handle user defined generics that don't register origin/args properly
                if inspect.isclass(tvar) and len(orig_bases := get_original_bases(tvar)) == 1:
                    base = orig_bases[0]
                    _args = get_args(base)
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
        if origin is Unpack and len(args) == 1:
            return get_args(args[0])
        elif name in cls.FILTERS.polyarg or isinstance(origin, UnionType):
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
            elif self.origin is UnionType:
                return Union[self.args]  # type: ignore
        elif len(self) > 0 and isinstance(self.args[0].root, type):
            return self.args[0].root
        return Any  # type: ignore

    # ------------------
    # `*` Public Methods
    # ------------------
    # ------------------
    # `*0` Magic Methods
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
            return self.match(other)
        return False

    @overload
    def __contains__(self, child: None) -> TypeIs[NoneType]: ...
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
        if isinstance(child, (type, MyType)):
            return self.ty.match(child, self, False)
        return False

    @overload
    def __and__(self, other: None) -> TypeIs[NoneType]: ...
    @overload
    def __and__(self, other: type) -> TypeIs[type[T]]: ...
    @overload
    def __and__(self, other: MyType) -> TypeIs[MyType[T]]: ...
    @overload
    def __and__(self, other: tuple[type, ...]) -> TypeIs[tuple[type[T], ...]]: ...
    def __and__(self, other: TypeArg) -> bool:
        """Determines whether the other type contains this one."""
        return other is not None and self.ty.match(self, other, True)

    @overload
    def __rand__(self, other: None) -> TypeIs[NoneType]: ...
    @overload
    def __rand__(self, other: type) -> TypeIs[type[T]]: ...
    @overload
    def __rand__(self, other: MyType) -> TypeIs[MyType[T]]: ...
    @overload
    def __rand__(self, other: tuple[type, ...]) -> TypeIs[tuple[type[T], ...]]: ...
    @overload
    def __rand__(self, other: object) -> TypeIs[type[T]]: ...
    def __rand__(self, other: MyType | type | object | None) -> bool:
        """Determines whether this type contains the other one."""
        if isinstance(other, (type, MyType)):
            return self.ty.match(other, self, True)
        return False

    # -------------------
    # `*1` Main Interface
    # -------------------
    @classmethod
    @overload
    def _match[T1](cls, t0: None, t1: TypeArg[T1]) -> TypeIs[NoneType]: ...
    @classmethod
    @overload
    def _match[T1](cls, t0: type, t1: TypeArg[T1]) -> TypeIs[type[T1]]: ...
    @classmethod
    @overload
    def _match[T1](cls, t0: MyType, t1: TypeArg[T1]) -> TypeIs[MyType[T1]]: ...
    @classmethod
    @overload
    def _match[T1](cls, t0: tuple[type, ...], t1: TypeArg[T1]) -> TypeIs[tuple[type[T1], ...]]: ...
    @classmethod
    def _match[T0, T1](cls, t0: TypeArg[T0], t1: TypeArg[T1], inter: bool = False) -> bool:
        if t0 is None or t1 is None:
            return False

        return cls._ty().match(MyType.new(t0), MyType.new(t1), inter)

    @overload
    def match(self, other: None) -> TypeIs[NoneType]: ...
    @overload
    def match(self, other: type) -> TypeIs[type[T]]: ...
    @overload
    def match(self, other: MyType) -> TypeIs[MyType[T]]: ...
    @overload
    def match(self, other: tuple[type, ...]) -> TypeIs[tuple[type[T], ...]]: ...
    @overload
    def match(self, other: object) -> TypeIs[type[T]]: ...
    def match(self, other: MyType | type | object | None) -> bool:
        """Determines whether the given type value is a subset of this type."""
        if isinstance(other, (type, MyType)):
            return self.ty.match(other, self)  # note that this checks the ARG for membership
        return False

    def check(self, data: object) -> TypeIs[T]:
        """Check if a given data value matches this type, recursing into containers where needed.

        Args:
            data: The data value to check. Ideally not an exhaustable iter.
        Returns:
            True if *all* aspects of this type are satisfied by this data, including nested types.
        """
        return self.ty.check(data, self.root) if self else False

    def members(self) -> Iterator[MyType]:
        """Yield all field types for Pydantic models or TypedDicts.

        Returns:
            Iterator of MyType instances for each field in the type.
        """
        if not (main := self.main):
            return
        elif issubclass(main, pyd.BaseModel):
            yield from map(self.parse, ut.instance_fields(main).values())
        elif is_typeddict(self.root):
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

    @ft.cached_property
    def idx(self) -> str:
        """A unique-ish ID for this type that implicitly identifies the closest 'known' ancestor."""
        return next(
            (
                idx
                for idx, tvar in sorted(
                    self.IDXS.items(), key=lambda x: f'{len(x[0])}_{x[0]}', reverse=True
                )
                if self.match(tvar)
            ),
            '0',
        )


############
### DATA ###
############
_idx_data: dict[str, Any] = {
    '0': Object,
    '1': Atom,
    '11': String,
    '111': str,
    '112': bytes,
    '113': Stream,
    '1131': bytearray,
    '1132': memoryview,
    '1133': IO,
    '11331': StringIO,
    '11332': BytesIO,
    '12': Scalar,
    '121': int,
    '122': float,
    '123': complex,
    '124': bool,
    '13': Enum,
    '131': Flag,
    '14': Time,
    '141': date,
    '142': time,
    '143': datetime,
    '144': timedelta,
    '2': Struct,
    '21': Vec,
    '211': list,
    '212': tuple,
    '213': Set,
    '214': deque,
    '22': Map,
    '221': Mapping,
    '222': ItemsView,
    '23': Iter,
    '231': Iterable,
    '232': AsyncIterable,
    '24': Model,
    '241': BaseModel,
    '242': Dataclass,
    '3': Func,
    '31': FunctionType,
    '32': BuiltinFunctionType,
    '33': Callable,
}
MyType.IDXS = ut.val_map(MyType.new, _idx_data)

AnyType: MyType[Any] = MyType.new(Any)
