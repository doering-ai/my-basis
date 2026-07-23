############
### HEAD ###
############
# Standard imports
from __future__ import annotations
from types import (
    UnionType,
    EllipsisType,
    NoneType,
    FunctionType,
    BuiltinFunctionType,
    get_original_bases,
)
from typing import (
    Any,
    ClassVar,
    Generic,
    IO,
    Literal,
    ParamSpec,
    ParamSpecArgs,
    ParamSpecKwargs,
    Protocol,
    Self,
    TypeVar,
    TypeVarTuple,
    Unpack,
    overload,
    is_typeddict,
    TypeAliasType,
    get_args,
    get_origin,
    Union,
    Never,
)
from typing_extensions import TypeIs  # 3.13 in the stdlib `typing`; our floor is 3.12
from collections import Counter, deque
from collections.abc import (
    Iterator,
    Iterable,
    Mapping,
    Callable,
    AsyncIterable,
    ItemsView,
    Set,
    Hashable,
)
from io import StringIO, BytesIO
import inspect
import dataclasses
from enum import Enum, Flag
from datetime import date, time, datetime, timedelta
import functools as ft
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
from .Metatype import Metatype as Meta

############
### DATA ###
############
#: Any argument acceptable wherever a type is expected: a plain type, an already-wrapped
#: `MyType`, a tuple of types, a raw value (whose type is inferred), or None.
#: NOTE: `T` has no PEP 696 default (3.13 syntax, above our 3.12 floor). With a single
#: type parameter a partial subscript is impossible, so the default was inert.
type TypeArg[T] = type[T] | MyType[T] | tuple[type[T], ...] | Any | None
Empty = type[inspect.Parameter.empty]
empty = inspect.Parameter.empty


############
### BODY ###
############
@ft.total_ordering
class MyType[T](_TypingBase, pyd.BaseModel, arbitrary_types_allowed=True):
    """A wrapper for any type annotation that normalizes the wide variety of interfaces.

    .. rubric:: Examples

    Consider this simplified subset of the hierarchy:

    .. code-block:: python

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

    **``__and__()``**

    .. code-block:: python

       # Affirms if either is part of the other, fails otherwise
       assert str_t & atom_t
       assert atom_t & str_t
       assert not str_t & int_t

       # Works with a raw *plain type* on either side, as long as the other side is wrapped
       assert str & atom_t and str_t & Atom
       assert atom_t & str
       #! assert str & Atom  # two raw annotations know nothing of each other
       #! assert Atom & str_t  # a raw union LHS cannot reflect onto the wrapped RHS

       # Works with unions and tuples of plain types (when LHS is wrapped)
       assert str_t & (str | Scalar)
       assert str_t & (str, int)
       assert not str_t & (bytes, int)

    **``__contains__()``**

    .. code-block:: python

       # Determines whether the LHS is a subset of the RHS, but not the other way around.
       assert str in atom_t
       assert Atom not in str_t

       # RHS must be a MyType.
       #! assert str in Atom

       # Works with tuples
       assert str in (str_t, Scalar)

    .. rubric:: "Main" types (i.e. ``MyType.main``)

    The main type of an instance represents the most meaningfully *active* part of that type in
    this moment. Some cases:

    .. code-block:: python

       assert MyType(dict[str, int]).main is dict
       assert MyType(Literal['a', 'b']).main is None
       assert MyType(Optional[int]).is_split

    Some cases:
      - Basic generics use their origins, while the vast majority of Atoms use themselves in full.

      - Literals use ``Literal``.

      - Monotomic "Special Forms" (e.g. ``Annotated[int, ...]``, ``Final[str]``) use a type or
        union representing the wrapped content of the inner form.

      - Polytomic "Special Forms" (e.g. ``Optional[int]`` / ``Union[int, str]`` -> ``UnionType``,
        ``Unpack[str, str]`` -> ``Unpack``) use a type representing the wrapping content of the
        outer form.
    """

    POS: ClassVar[MyType]
    NEG: ClassVar[MyType]

    #: Whether to raise exceptions when type casting fails unexpectedly.
    RAISE: ClassVar[bool] = False

    #: Performance cache based on full type stringification (i.e. ``__str__()``)
    PARSE_CACHE: ClassVar[Cache[int, MyType]] = Cache()

    #: Cache of manually indexed types, where the key is a unique, hierarchical identifier.
    IDXS: ClassVar[dict[str, MyType]] = {}

    #: The original value passed in -- used for ``uid`` generation.
    raw: Any = NoneType

    #: The original type annotation passed in, which may be unparseable.
    root: type | UnionType | TypeAliasType | object | None = None

    #: The main type, which usually just means the type itself or its origin.
    main: type[T] | type[UnionType] | type[NoneType] | None = None

    #: The name of the type (e.g. 'dict', 'Union', 'Annotated', etc.) or '' if unparseable.
    name: str = ''

    #: A unique serialized identifier for this type, used for caching.
    uid: int = 0

    #: The arguments of generic types; only needed for advanced usecases.
    args: tuple[MyType, ...] = tuple()

    #: The type annotation for the contents of a generic collection.
    #: The vast majority of generics are monotyped so only use this field (e.g. vecs & iters).
    #: None when the contents are unconstrained (e.g. a bare ``list`` or an ``Any`` value type).
    vals: MyType | None = None

    #: For mappings, the type annotation of the keys. For other types, None.
    #: Can sometimes be monotype, e.g. ``Counter[str]`` -> ``dict[str, int]``
    keys: MyType | None = None

    # ---- Internal attributes ----
    #: The origin of the type, if it has one (e.g. ``dict`` for ``dict[str, int]``); otherwise None.
    origin: type | None = None

    #: For literal types, the list of literal members
    #: (e.g. ``["a", "b"]`` for ``Literal["a", "b"]``).
    literal_members: list[Any] = []

    # -------------------
    # `.` Initial Methods
    # -------------------
    @overload
    def __init__(self: MyType[NoneType], root: None, **kwargs): ...
    @overload
    def __init__[R](self: MyType[R], root: TypeArg[R], **kwargs): ...
    @overload
    def __init__[R](self: MyType[R], root: TypeArg[R] = Any, uid: int = 0, **kwargs): ...
    def __init__[R](self, root: TypeArg[R] = Any, uid: int = 0, **kwargs):
        """Initialize a MyType instance with the given source type and unique identifier.

        This function is overridden from ``pyd.BaseModel`` so as to allow positional args.

        Args:
            root: The original type annotation that this MyType instance represents. Can be any
                type or None.
            uid: A unique identifier for this type, used for caching. If not provided, will be
                generated from the stringified root.
            **kwargs: Additional keyword arguments to pass to the BaseModel initializer.
        """
        kwargs.pop('raw', None)
        super().__init__(raw=root, root=root, uid=uid or hash(str(root)), **kwargs)

    @overload
    @staticmethod
    def new() -> MyType[Any]: ...
    @overload
    @staticmethod
    def new(root: None) -> MyType[NoneType]: ...
    @overload
    @staticmethod
    def new[R](root: tuple[type[R], ...]) -> MyType[Union[type[R], ...]]: ...
    @overload
    @staticmethod
    def new[R](root: TypeArg[R]) -> MyType[R]: ...
    @overload
    @staticmethod
    def new[R](root: type[R] | MyType[R]) -> MyType[R]: ...
    @overload
    @staticmethod
    def new[R](root: R) -> MyType[R]: ...
    @staticmethod
    def new(root: TypeArg | Any | Empty = empty) -> MyType:
        """Create a new MyType instance by parsing a type OR inferring the full type of a value.

        Examples:
            Types parse; values infer::

                >>> from my import MyType
                >>> MyType.new(int)
                MyType[<class 'int'>](main=<class 'int'>)
                >>> MyType.new(5)
                MyType[<class 'int'>](main=<class 'int'>)
        """
        cls = MyType
        # 0. Handle edge & null cases, prep data
        if not isinstance(root, Hashable):
            # Unhashable roots (list, dict, set, ...) are always runtime values -- infer.
            return cls.typeof(root)
        if root in {empty, Empty, Any}:
            return cls.POS
        elif root in {None, NoneType, Never}:
            return cls.NEG
        elif (
            isinstance(root, (type, MyType, UnionType))
            or (isinstance(root, tuple) and all(isinstance(t, type) for t in root))
            or get_origin(root) is not None
            or Meta(root)
        ):
            # NOTE: `get_origin` catches parameterized generics & special forms
            # (e.g. `dict[str, int]`, `Literal[1]`), which are NOT `type` instances
            # and so must be `parse`d, not `typeof`'d.
            return cls.parse(root)
        else:
            # II. Infer annotations for untyped data
            return cls.typeof(root)

    @overload
    @classmethod
    def parse[Rm: MyType](cls, root: Rm, throw: bool = False) -> Rm: ...
    @overload
    @classmethod
    def parse[R](cls, root: type[R], throw: bool = False) -> MyType[R]: ...
    @overload
    @classmethod
    def parse[Rt: tuple[type, ...]](cls, root: Rt, throw: bool = False) -> MyType[Rt]: ...
    @overload
    @classmethod
    def parse(cls, root: UnionType, throw: bool = False) -> MyType: ...
    @overload
    @classmethod
    def parse(cls, root: TypeAliasType, throw: bool = False) -> MyType: ...
    @overload
    @classmethod
    def parse(cls, root: None, throw: bool = False) -> MyType[NoneType]: ...
    @overload
    @classmethod
    def parse(cls, root: object, throw: bool = False) -> MyType: ...
    @classmethod
    def parse[R](cls, root: object, throw: bool = False) -> MyType:
        """Decompose a given type so that other methods can intelligently handle each part in turn.

        By far the most likely usecase is for containers such as ``dict[str, int]`` (which becomes
        the tuple ``(dict, str, int)``) and ``list[int]`` (which becomes ``(list, int, None)``), but
        it's useful for other generics, unions (e.g. ``string | int``), and special non-type forms
        (e.g. ``Annotated`` and ``Literal``).

        Args:
            root: The type annotation to decompose -- either a type, a union of types, or None.
            throw: If True, will re-raise any exceptions encountered during parsing.
        Returns:
            A MyType instance with the root set to the original type, and the other fields
            populated according to the structure of that type.
        Examples:
            Decompose parameterized generics into their parts::

                >>> from my import MyType
                >>> MyType.parse(dict[str, int]).summarize()
                (<class 'dict'>, <class 'str'>, <class 'int'>)
                >>> MyType.parse(int | str).is_split
                True
        """
        if isinstance(root, MyType):
            # Already parsed -- re-deriving a uid from `str(root)` here would collapse an
            # unhandled/collapsed form (e.g. `Self`, `TypeVar`) onto whatever it collapsed to
            # (e.g. `NoneType`), since `self.root` no longer reflects the original annotation.
            return root
        try:
            # `str()`/`repr()` on a TypeVar only ever shows the parameter's own name (e.g. `~T`),
            # not its bound/constraints/default -- two unrelated `TypeVar('T', ...)` declarations
            # would otherwise collide onto the same cache entry despite `_resolve_typevar` giving
            # them different results. Key by identity instead, since each declaration is its own
            # distinct object.
            uid = id(root) if isinstance(root, TypeVar) else hash(str(root))
            if cached := cls.PARSE_CACHE[uid]:
                return cached

            cls.PARSE_CACHE[uid] = ret = cls(root=root, uid=uid)
            return ret
        except (ValueError, TypeError):
            # An unparseable annotation surfaces as a `TypeError` (e.g. an unhashable `str(root)`)
            # or a `ValueError` (pydantic `ValidationError` from `cls(...)`); both mean "can't
            # decompose this type", so degrade to a minimal `MyType(root=root)`. Narrowed from a
            # blanket `except Exception` so a genuinely-unexpected failure (e.g. `RecursionError`
            # from a self-referential annotation) propagates instead of being silently swallowed.
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
        Examples:
            Infer full container annotations from runtime values::

                >>> from my import MyType
                >>> str(MyType.typeof({'a': [1]}))
                'dict[str, list[int]]'
        """
        ty = cls._ty()
        origin = type(data)
        args = []
        # 0. Return immediately for null args and non-generics
        if not data or not hasattr(origin, '__class_getitem__'):
            inst = cls.parse(origin)
            if isinstance(data, Enum):
                # `parse(EnumClass)` carries the class's name->value constraints (needed when
                # casting *to* that enum), but the type of one *instance* is just the enum
                # itself -- strip them so a scalar member reads as atomic, like any other scalar.
                inst = inst.model_copy(update={'vals': None, 'keys': None})
            return inst

        if ty.is_vec(data):
            valtypes = ut.condense(map(cls.typeof, data))
            if isinstance(data, tuple):
                if len(set(valtypes)) == 1:
                    t = valtypes[0].root
                    assert t is not None
                    args = [t, Ellipsis]
                else:
                    args = [vt.root for vt in valtypes if vt.root is not None]
            else:
                args = [cls._join(valtypes)]
        elif ty.is_map(data):
            d = dict(data)
            keys = cls._join(cls.typeof(k) for k in d.keys())
            vals = cls._join(cls.typeof(v) for v in d.values())
            args = [keys, vals]

        return cls.parse(origin[*args] if args else origin)  # type: ignore

    @ft.cached_property
    def none(self) -> MyType[NoneType]:
        """A MyType instance that only matches None."""
        return MyType.NEG

    @ft.cached_property
    def all(self) -> MyType[Any]:
        """A MyType instance that matches everything."""
        return MyType.POS

    @pyd.field_validator('root', mode='before')
    @classmethod
    def _process_root(cls, root: Any) -> Any:
        if isinstance(root, MyType):
            return root.root
        elif isinstance(root, TypeVar):
            # A bare TypeVar carries no cast-able shape of its own -- concretize it to whatever
            # it stands in for (default/bound/constraint), rather than leaving it unresolved.
            return cls._resolve_typevar(root)
        elif isinstance(root, (TypeVarTuple, ParamSpec, ParamSpecArgs, ParamSpecKwargs)):
            # Unlike `TypeVar`, these have no single stand-in type to resolve to -- treat them as
            # unmatchable, same as `Callable`/`Protocol`/etc. NOTE: must check before `Meta(root)`
            # below, since `ParamSpecArgs`/`ParamSpecKwargs` instances are unhashable.
            return NoneType

        # I. Exit early for type builtins, and stop to recurse into any aliases
        if root in (Ellipsis, EllipsisType):
            return EllipsisType
        elif root in (None, NoneType):
            return NoneType
        elif (value := getattr(root, '__value__', None)) is not None:
            return cls._process_root(value)

        match Meta(root):
            case Meta.ALWAYS:
                return Any
            case Meta.NEVER:
                return NoneType
            case _:
                return root

    @pyd.model_validator(mode='after')
    def _process_src(self) -> Self:
        """Infer remaining instant attributes upon initialization."""
        # 0. Validate & parse the source type, but don't save the args yet
        if not self.root or not self.uid:
            return self
        self.name, self.origin, args = self._0_read(self.root)

        if branches := self._1_split(self.name, self.origin, args):
            # I. Split for divergent types (e.g. `Union[int, str]`)
            self.args = tuple(self._process_args(branches))
            self.main = UnionType
            return self
        elif self.origin is Literal:
            # II. Process set literals
            self.literal_members = list(args)
            self.args = tuple(set(map(MyType.new, args)))
            return self

        match Meta(self.root):
            case Meta.ALWAYS | Meta.NEVER:
                # II. Ignore "always"/unhandled forms, not setting `main` at all (stays falsy).
                # NOTE: `Any` is a `type` subclass in 3.11+, so it must be excluded here explicitly.
                return self
            case Meta.MONO:
                # III. Unwrap simple forms (e.g. `Annotated[str]`)
                if contents := mi.first(filter(bool, self._process_args(args)), None):
                    # Overwrite all our pydantic vars with the `contents`'s versions
                    # NOTE: keep our uid & root for caching purposes
                    self.__dict__.update(
                        {
                            k: v
                            for k, v in contents.__dict__.items()
                            if k in MyType.model_fields and k not in {'uid', 'root'}
                        }
                    )
            case _:
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
                        # Only a *populated* enum carries key/val constraints (names -> values);
                        # the bare `Enum` base stays unconstrained so subclasses are subsets of it.
                        if members := list(self.root.__members__.values()):
                            self.keys = MyType.new(str)
                            if not self.vals:
                                # Infer from the members' underlying `.value`, NOT the members
                                # themselves -- typeof(member) would re-parse this Enum and recurse.
                                self.vals = MyType.typeof(mi.first(m.value for m in members))
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
        for raw in args:
            arg: MyType = self.parse(raw)
            if arg.origin is Unpack:
                yield from arg.args
            else:
                yield arg

    def _process_generic(self, origin: type, args: tuple[MyType, ...]) -> None:
        """Wire up ``keys``/``vals`` (and tuple literals) from a generic origin and its args."""
        n = len(args or [])
        is_map = inspect.isclass(origin) and issubclass(origin, Mapping)
        if n == 0:
            # 0. No args -> just set the main type
            self.main = origin
        elif inspect.isclass(origin) and issubclass(origin, tuple):
            # I. Catch tuples (either monotyped or literal)
            if args[-1].root is EllipsisType:
                if n > 1:
                    # `or None`: an `Any` arg parses to a falsy MyType -> unconstrained.
                    self.vals = args[0] or None
                else:
                    self.args = tuple()
            else:
                self.literal_members = list(args)
        elif n == 1:
            arg = args[0]
            if is_map:
                # II. Catch mono-keyed maps (e.g. Counters)
                self.keys = arg or None
                if issubclass(origin, Counter):
                    self.vals = self.parse(int)
            else:
                # III. Catch any generics with singular values -- the most common kind by far
                self.vals = arg or None
        elif n == 2 and is_map:
            # IV. Catch double-keyed (key+val) maps
            self.keys, self.vals = args[0] or None, args[1] or None

    @classmethod
    def _join(cls, args: Iterable[TypeArg]) -> Any:
        """Condense multiple type arguments into a single type or union.

        Args:
            args: List of MyType instances to condense.
        Returns:
            Single type if all args are the same, UnionType otherwise.
        """
        types = {t for a in args if a is not None and (t := cls.new(a))}

        n = len(types)
        if n == 0:
            return Empty
        if n == 1:
            # `.root`, not `.main` -- `.main` collapses a nested generic like `list[int]` down to
            # its bare origin `list`, losing the inner arg (e.g. joining two `list[int]` values
            # would otherwise infer `list[list]` instead of `list[list[int]]`).
            return types.pop().root or Empty
        else:
            head: Any = types.pop().root or Empty
            for other in types:
                head = head | (other.root or Empty)
        return head

    @classmethod
    def get_name(cls, val: Any) -> str:
        """Get the name of a type or a value's type if possible, or '' if not."""
        return Meta._name(val)

    @classmethod
    def _resolve_typevar(cls, tvar: TypeVar) -> Any:
        """Concretize a bare (unsubstituted) TypeVar into a sensible stand-in type.

        Precedence -- most-specific signal first -- is: an explicit PEP 696 default (may itself be
        another TypeVar, e.g. a second parameter defaulting to the first, so resolve recursively),
        then the bound (the union itself, if the bound is a union -- a bound is a ceiling, not a
        menu, so the full union is exactly the information available and no member is more
        "correct" than another), then the union of all constraints (rather than only the first --
        constraints are an explicit closed menu of equally-valid choices, so discarding any of
        them is silently lossy), then `Any` as the last resort for a fully unconstrained TypeVar.

        Args:
            tvar: The TypeVar to concretize.
        Returns:
            A concrete type (or union) standing in for the TypeVar.
        """
        # `has_default()` is a 3.13 runtime API. PEP 695 type params on our 3.12 floor lack
        # it entirely; `typing_extensions` TypeVars always carry it.
        has_default = getattr(tvar, 'has_default', None)
        if has_default is not None and has_default():
            # `__default__` is only declared on 3.13+ / `typing_extensions` TypeVars, and
            # `has_default()` above already proved this one carries it.
            default = getattr(tvar, '__default__')
            return cls._resolve_typevar(default) if isinstance(default, TypeVar) else default
        elif bound := tvar.__bound__:
            return bound
        elif constraints := tvar.__constraints__:
            union: Any = constraints[0]
            for constraint in constraints[1:]:
                union = union | constraint
            return union
        return Any

    @classmethod
    def _0_read(cls, tvar: Any) -> tuple[str, type[Any] | None, tuple]:
        """Get the immediate basic values of this type, without any recursion.

        Args:
            tvar: Type to decompose.
        Returns:
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
                # Handle user defined generics that don't register origin/args properly. PEP 695
                # classes (`class Span[T](tuple[T, T])`) carry an implicit `Generic[T]` alongside
                # their real base, so filter it out before counting -- but if `Generic`/`Protocol`
                # is the *only* base (old-style `class Foo(Generic[T])`), it's the sole source of
                # type params and must be kept.
                if inspect.isclass(tvar):
                    orig_bases = get_original_bases(tvar)
                    bases = [b for b in orig_bases if get_origin(b) not in (Generic, Protocol)]
                    bases = bases or list(orig_bases)
                    if len(bases) == 1 and (_args := get_args(bases[0])):
                        origin = tvar
                        args = _args

        return name, origin, args

    @classmethod
    def _1_split(cls, name: str, origin: Any | None, args: tuple) -> tuple:
        """Decompose a union or tuple type into its member types.

        Args:
            name: Name of the type.
            origin: Origin of the type.
            args: Arguments of the type.
        Returns:
            Tuple of member types if it's a union/tuple, empty tuple otherwise.
        """
        n = len(args)
        if name == '' or n == 0:
            return args
        elif name in Meta.POLY.value or isinstance(origin, UnionType):
            return args
        else:
            return tuple()

    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `*` Public Methods
    # ------------------
    @property
    def is_split(self) -> bool:
        """Whether this type is a union of multiple types."""
        return self.main == UnionType

    @property
    def rtype(self) -> type | UnionType:
        """A version of the root that has been lightly coerced into being a regular type.

        Plain types and unions return themselves, and an ``Unpack`` unwraps to its content.
        Otherwise a split type collapses to the bare ``UnionType``, a parameterized generic yields
        its *first argument's* root (e.g. ``dict[str, int]`` -> ``str``, not ``dict``), and
        anything else falls back to ``Any``.
        """
        ret = self.root
        if isinstance(ret, (type, UnionType)):
            return ret
        elif self.origin is Unpack:
            return self.args[0].rtype
        elif self.is_split:
            return UnionType
        elif len(self.args) > 0 and isinstance(self.args[0].root, type):
            return self.args[0].root

        return Any

    #### `*M` #####################################################################################
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
        """Determine whether the preceding type is a valid subset of this one."""
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
        """Determine whether either of the two types contains the other."""
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
        """Determine whether either of the two types contains the other (reflected form)."""
        if isinstance(other, (type, MyType)):
            return self.ty.match(other, self, True)
        return False

    #### `*A` #####################################################################################
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
        """Determine whether the given type value is a subset of this type.

        Examples:
            Membership runs from the argument into this type::

                >>> from my import MyType
                >>> MyType(int | str).match(int)
                True
                >>> MyType(int).match(int | str)
                False
        """
        if isinstance(other, (type, MyType)):
            return self.ty.match(other, self)  # note that this checks the ARG for membership
        return False

    def check(self, data: object) -> TypeIs[T]:
        """Determine whether a given data value matches this type, recursing into containers.

        Args:
            data: The data value to check. Ideally not an exhaustable iter.
        Returns:
            True if *all* aspects of this type are satisfied by this data, including nested types.
        Examples:
            Validate values against the parsed type::

                >>> from my import MyType
                >>> t = MyType.parse(dict[str, int])
                >>> t.check({'a': 1}), t.check({'a': 'b'})
                (True, False)
        """
        # `Any` (always-true wildcard) and `None`/`NoneType` (concrete null) are all falsy
        # (`main is None`) yet still delegate; only a truly empty type short-circuits to `False`.
        if self or Meta(self.root) is Meta.ALWAYS or self.root is NoneType or self.root is None:
            return self.ty.check(data, self.root)
        return False

    def check_iter(self, data: Iterable) -> Iterator[bool]:
        """Yield a boolean for each element of ``data`` indicating if it matches this type.

        Args:
            data: The iterable of values to check. Ideally not an exhaustable iter.
        Yields:
            One boolean per element, True if that element matches this type.
        """
        return (self.check(v) for v in data)

    def literal_check(self, val: object) -> bool:
        """Determine whether a value satisfies this Literal or tuple-literal type."""
        return self.ty.is_literal(val, self)

    def is_map_item(self) -> bool:
        """Whether this type is a map item: a bare ``tuple`` or a ``tuple`` of exactly two types."""
        main = self.main
        if main is None or not (inspect.isclass(main) and issubclass(main, tuple)):
            return False
        if not self.literal_members and not self.vals:
            # Bare, unparameterized `tuple` -- a key/value pair of unknown types.
            return True
        return len(self.literal_members) == 2

    def members(self) -> Iterator[MyType]:
        """Yield all field types for Pydantic models or TypedDicts.

        Returns:
            Iterator of MyType instances for each field in the type.
        """
        if not (main := self.main):
            return
        elif issubclass(main, pyd.BaseModel):
            for field in ut.instance_fields(main).values():
                yield self.parse(field)
        elif is_typeddict(self.root):
            for field in self.root.__annotations__.values():
                yield self.parse(field)
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
        """The hierarchy ID of the most specific registered `IDXS` type that matches this one.

        Scans the registered index (longest keys first) and returns the ID of the first entry
        whose type matches (is a subset of) this one, or '0' when none do.
        """
        arr = sorted(
            self.IDXS.items(),
            key=lambda x: f'{len(x[0])}_{x[0]}',
            reverse=True,
        )
        return next(
            (idx for idx, tvar in arr if self.match(tvar)),
            '0',
        )

    @staticmethod
    def _calc_idx_dist(lhs: str, rhs: str) -> int:
        """Calculate a distance metric between two hierarchical IDs."""
        lhs, rhs = lhs.strip(), rhs.strip()
        if pre := list(mi.longest_common_prefix([lhs, rhs])):
            lhs, rhs = lhs[len(pre) :], rhs[len(pre) :]
        # older, younger = sorted((lhs, rhs), key=lambda s: f'{len(s)}_{s}')
        return len(lhs) + len(rhs)

    #### `*B` #####################################################################################


############
### DATA ###
############

# Bootstrap the two canonical singletons. We can't use `new()` here, since it short-circuits
# to `cls.POS`/`cls.NEG` for `Any`/`None`; instead construct them directly and make `POS`
# self-referential.
MyType.POS = MyType(root=Any)
MyType.NEG = MyType(root=None)
MyType.POS.vals = MyType.POS.keys = MyType.POS

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
# NOTE: built directly (not via `ut.val_map`) since `ut.ty` isn't wired up until Typist loads.
MyType.IDXS = {key: MyType.new(val) for key, val in _idx_data.items()}
