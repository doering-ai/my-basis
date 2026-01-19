############
### HEAD ###
############
# Standard imports
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Self,
    TypeGuard,
    Unpack,
)
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
import collections.abc as tyabc
import itertools as it
import types
import typing as ty
import inspect
import contextlib as ctx

# Modular imports
import pydantic as pyd
import more_itertools as mi

# Local imports
from ..infra import Series
from ..utils import ut
from ..caches import Cache

# SpecialFormField = Annotated[ty._SpecialForm, ut.pyd_schemify(ty._SpecialForm)]


############
### BODY ###
############
class MyType(pyd.BaseModel):
    """A wrapper for any type annotation that normalizes the wide variety of interfaces."""

    #: If any of these types are passed into `parse()`, no work will be done and an "inactive"
    #: instance will be returned (i.e. it will only have `src_type` defined, and will be falsey).
    UNHANDLED_TYPES: ClassVar[set[str]] = {
        '',
        'Any',
        'object',
        # Functional
        'Generator',
        'Iterator',
        'Coroutine',
        # Special Forms
        'Callable',  # deprecated
        'Type',  # deprecated
        'NoReturn',
        'TypeGuard',
        # >= 3.10
        'Self',
        'Never',
        'LiteralString',  # Too complicated & rare
        'Concatenate',
        'TypeAlias',  # Should never come up
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
        ### IMPORTANT: TypeVars are completely unhandled as of now. Could do it tho with .__bound__
        'TypeVar',
        'TypeVarTuple',
    }
    SIMPLE_FORMS: ClassVar[set[str]] = {
        'ClassVar',
        'Optional',
        'Annotated',
        'Required',
        'NotRequired',
        'Final',
    }

    PARSE_CACHE: ClassVar[Cache[str, 'MyType']] = Cache()
    RAISE: ClassVar[bool] = False

    src_type: type | Any | None = None

    main_type: type | None = None
    val_type: Optional['MyType'] = None
    key_type: Optional['MyType'] = None

    name: str = ''
    uid: str = ''
    origin: type | None = None
    args: tuple['MyType', ...] = tuple()
    literal_members: list[Any] = []
    is_split: bool = False

    # -------------------
    # `.` Initial Methods
    # -------------------
    @classmethod
    def parse(cls, src_type: Any, throw: bool = True) -> 'MyType':
        """Decompose a given type so that other methods can intelligently handly each part in turn.

        By far the most likely usecase is for containers such as `dict[str, int]` (which becomes the
        tuple `(dict, str, int)`) and `list[int]` (which becomes `(list, int, None)`), but it's
        useful for other generics, unions (e.g. `string | int`), and special non-type forms
        (e.g. `Annotated` and `Literal`). See `MyType.UNHANDLED_TYPES` for a best-effort list
        of unhandled annotations.

        Args:
            src_type: The type annotation to decompose -- either a type, a union of types, or None.
            throw: If True, will re-raise any exceptions encountered during parsing.
        Returns:
            1. The **main type** (e.g. `dict`, `list`, `int`, etc.) or `None` if unparseable.
            2. The **key type** (for mappings) or `None`.
            3. The **value type** (for any generics with just one type arg) or `None`.
        """
        if isinstance(src_type, MyType):
            return src_type
        elif src_type is Ellipsis:
            src_type = types.EllipsisType

        try:
            uid = str(src_type)
            if cached := cls.PARSE_CACHE[uid]:
                return cached

            cls.PARSE_CACHE[uid] = ret = cls(src_type=src_type, uid=uid)
            return ret
        except Exception:
            if cls.RAISE or throw:
                raise
            else:
                # Return without attempting to make it valid
                return cls(src_type=src_type)

    @classmethod
    def metaparse(cls, src_data: object) -> 'MyType':
        """Infer the type annotation of a given data value, recursing into containers.

        Args:
            src_data: Data value to infer type from.
        Returns:
            Parsed MyType instance representing the inferred type.
        """
        origin = type(src_data)
        args = []
        if not src_data or not hasattr(origin, '__class_getitem__'):
            return cls.parse(origin)

        elif isinstance(src_data, Series):
            val_types = list(filter(bool, map(cls.metaparse, src_data)))
            if isinstance(src_data, tuple):
                if len(set(val_types)) == 1:
                    t = val_types[0].src_type
                    assert t is not None
                    args = [t, Ellipsis]
                else:
                    args = [vt.src_type for vt in val_types if vt.src_type is not None]
            else:
                args = [cls._condense_args(val_types)]
        elif isinstance(src_data, Mapping):
            key_types = list(filter(bool, map(cls.metaparse, src_data.keys())))
            val_types = list(filter(bool, map(cls.metaparse, src_data.values())))
            args = [cls._condense_args(key_types), cls._condense_args(val_types)]

        return cls.parse(origin[*args] if args else origin)

    @classmethod
    def _condense_args(cls, args: list['MyType']) -> type | ty._SpecialForm:
        """Condense multiple type arguments into a single type or union.

        Args:
            args: List of MyType instances to condense.
        Returns:
            Single type if all args are the same, UnionType otherwise.
        """
        uniques = list(filter(bool, (arg.src_type for arg in set(args))))
        if len(uniques) == 1:
            return uniques[0]
        else:
            acc, *rest = uniques
            for other in rest:
                acc = acc | other
            return acc

    @pyd.model_validator(mode='after')
    def _process_src(self) -> Self:
        # 0. Validate & parse the source type
        if not self.src_type or not self.uid:
            return self
        self.name, self.origin, _args = self._read(self.src_type)

        # I. Catch edge cases: Unhandled types, simple wrappers, unions, and literals
        if options := self._split(self.name, self.origin, _args):
            if len(options) == 1 and self.origin is Unpack:
                options = ty.get_args(options[0])
            self.args = tuple(self._process_args(options))
            self.is_split = True
            self.main_type = types.UnionType
            return self
        elif self.name in self.UNHANDLED_TYPES:
            return self
        elif self.name in self.SIMPLE_FORMS:
            if contents := mi.first(filter(bool, self._process_args(_args)), None):
                # Overwrite all our pydantic vars with the `contents`'s versions
                # NOTE: keep our uid & src_type, for caching purposes
                self.main_type = contents.main_type
                self.key_type = contents.key_type
                self.val_type = contents.val_type
                self.is_split = contents.is_split
                self.name = contents.name
                self.origin = contents.origin
                self.args = (*contents.args,)
                self.literal_members = contents.literal_members
            return self
        elif self.origin is Literal:
            self.literal_members = list(_args)
            self.args = tuple(map(self.parse, set(map(type, _args))))
            return self

        # II. Process args for all remaining types, though only generics should have them
        self.args = tuple(self._process_args(_args))
        if self.origin:
            # III. Catch generics
            self.main_type = self.origin
            if not self.args:
                pass
            elif issubclass(self.origin, tuple):
                # III.i. Catch tuples (either monotyped or literal)
                if self.args[-1].src_type is types.EllipsisType:
                    if len(self.args) > 1:
                        self.val_type = self.args[0]
                    else:
                        self.args = tuple()
                else:
                    self.literal_members = list(self.args)
            elif len(self.args) == 1:
                arg = self.args[0]
                if issubclass(self.origin, tyabc.Mapping):
                    # III.ii. Catch mono-keyed maps
                    self.key_type = arg
                    if issubclass(self.origin, Counter):
                        self.val_type = self.parse(int)
                else:
                    # III.iii. Catch sequences
                    self.val_type = arg
            elif len(self.args) == 2 and issubclass(self.origin, tyabc.Mapping):
                # III.iv. Catch maps
                self.key_type, self.val_type = self.args

        elif isinstance(self.src_type, type):
            if issubclass(self.src_type, Counter):
                # IV. Niche case: Counters imply int values
                self.main_type = Counter
                self.val_type = self.parse(int)
            else:
                # V. MAIN CASE: Catch atomic and un-parametrized types
                self.main_type = self.src_type

        return self

    # -------------------
    # `-` Private Methods
    # -------------------
    def _process_args(self, args: tuple) -> Iterator['MyType']:
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

    def literal_check(self, value: Any) -> bool:
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
                and self.args[-1].src_type is not Ellipsis
                and len(value) == len(self.args)
                # Check them in turn
                and all(arg.check(val) for val, arg in zip(value, self.args, strict=True))
            )
        return False

    @classmethod
    def _is_type(cls, tvar: Any) -> TypeGuard[type | types.GenericAlias]:
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
    def _parseable(cls, tvar: Any) -> TypeGuard[type | tuple[type, ...]]:
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
    def _read(cls, tvar: Any) -> tuple[str, type | None, tuple]:
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

        # Handle user defined generics that don't register origin/args properly
        with ctx.suppress(Exception):
            if (
                not (origin or args)
                and inspect.isclass(tvar)
                and len(orig_bases := types.get_original_bases(tvar)) == 1
            ):
                base = orig_bases[0]
                _origin = ty.get_origin(base)
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

    # ------------------
    # `*` Public Methods
    # ------------------
    def __bool__(self) -> bool:
        return self.main_type is not None or len(self.literal_members) > 0

    def __str__(self) -> str:
        return f'{self.src_type}'

    def __repr__(self) -> str:
        parts = []
        if self.main_type is not None:
            parts.append(f'main={self.main_type}')
        if self.key_type is not None:
            parts.append(f'key={self.key_type}')
        if self.val_type is not None:
            parts.append(f'val={self.val_type}')
        if self.literal_members:
            parts.append('LITERAL')
        return f'MyType[{self.src_type}]' + (f'({", ".join(parts)})' if parts else '')

    def __eq__(self, other: object) -> bool:
        if isinstance(other, MyType):
            return self.uid == other.uid
        elif isinstance(other, type):
            return self.uid == str(other)
        elif other is None:
            return self.main_type is None
        return False

    def __hash__(self) -> int:
        return hash(self.uid)

    def check(self, data: object) -> bool:
        """Check if a given data value matches this type, recursing into containers where needed.

        Args:
            data: The data value to check. Ideally not an exhaustable iter.
        Returns:
            True if *all* aspects of this type are satisfied by this data, including nested types.
        """
        if data is None:
            return False

        elif self.is_split:
            return any(option.check(data) for option in self.args)

        elif self.src_type in (Any, object):
            return True

        elif self.literal_members:
            return self.literal_check(data)

        elif self.main_type is None:
            return False

        elif not isinstance(data, self.main_type):
            return False

        elif type(data).__name__ in self.UNHANDLED_TYPES:
            return False

        elif self.key_type is not None and self.val_type is not None:
            if items := ut.map_items(data):
                keys, vals = mi.unzip(items)
                return all(
                    it.chain(
                        self.key_type.check_iter(keys),
                        self.val_type.check_iter(vals),
                    )
                )

        elif self.val_type is not None and isinstance(data, Iterable):
            return all(self.val_type.check_iter(data))

        return True

    def check_iter(self, iterable: Iterable) -> Iterator[bool]:
        """Check if values in an iterable match this type.

        Args:
            iterable: The iterable of values to check.
        Yields:
            Boolean for each value indicating if it matches this type.
        """
        yield from map(self.check, iterable)

    def members(self) -> Iterator['MyType']:
        """Yield all field types for Pydantic models or TypedDicts.

        Returns:
            Iterator of MyType instances for each field in the type.
        """
        if not self.main_type:
            return
        elif issubclass(self.main_type, pyd.BaseModel):
            yield from map(self.parse, ut.instance_fields(self.main_type).values())
        elif ty.is_typeddict(self.src_type):
            yield from map(self.parse, self.src_type.__annotations__.values())

    def issubclass(self, tvar: 'type | types.UnionType | MyType | None') -> bool:
        """Check if this type is a subclass of another type.

        Args:
            tvar: The type to check against (can be type, UnionType, MyType, or None).
        Returns:
            True if this type is a subclass of tvar.
        """
        if isinstance(tvar, MyType):
            if self.origin is Literal and tvar.origin is Literal:
                return True
            tvar = tvar.main_type

        if self.origin is Literal and tvar is Literal:
            return True
        if self.main_type is None or tvar is None:
            return False

        return issubclass(self.main_type, tvar)

    def summarize(self) -> tuple[type | None, type | None, type | None]:
        """Get a simplified summary of this type with just the main types.

        Returns:
            Tuple of (main_type, key_type, value_type) where key and value
            are extracted from their respective MyType wrappers.
        """
        if not self:
            return (None, None, None)
        return (
            self.main_type,
            self.key_type.main_type if self.key_type else None,
            self.val_type.main_type if self.val_type else None,
        )

    def is_map_item(self) -> bool:
        """Check if this type represents a mapping item (2-tuple key-value pair).

        Returns:
            True if this is a tuple[K, V] with exactly 2 non-None type args.
        """
        return self.main_type is tuple and len(self.args) == 2 and None not in self.args
