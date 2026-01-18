############
### HEAD ###
############
# Standard imports
from typing import (
    Self,
    Any,
    ClassVar,
    TypeGuard,
    Literal,
    Callable,
    Iterable,
    Iterator,
    Unpack,
    Optional,
)
import typing as ty
import collections.abc as tyabc
from collections import Counter
import types
import itertools as it

# Modular imports
import pydantic as pyd
import more_itertools as mi

# Local imports
from ..utils import ut
from ..caches import Cache


############
### BODY ###
############
class MyType(pyd.BaseModel):
    UNHANDLED_TYPES: ClassVar[set[str]] = {
        "",
        "Any",
        "object",
        # Functional
        "Generator",
        "Iterator",
        "Coroutine",
        # Special Forms
        "Callable",  # deprecated
        "Type",  # deprecated
        "NoReturn",
        "TypeGuard",
        # >= 3.10
        "Self",
        "Never",
        "LiteralString",  # Too complicated & rare
        "Concatenate",
        "TypeAlias",  # Should never come up
        # >= 3.13
        "TypeIs",
        "ReadOnly",
        # from types module:
        "NoneType",
        "EllipsisType",
        "NotImplementedType",
        "CapsuleType",
        "Ellipsis",
        # Possible, but not yet handled:
        "TypedDict",  # treat like BaseModel
        "NamedTuple",  # treat like tuple but w/ names
        "Protocol",  # try isinstance
    }
    SIMPLE_FORMS: ClassVar[set[str]] = {
        "ClassVar",
        "Optional",
        "Annotated",
        "Required",
        "NotRequired",
        "Final",
    }

    PARSE_CACHE: ClassVar[Cache[str, "MyType"]] = Cache()
    RAISE: ClassVar[bool] = False

    src_type: Any | None = None

    main_type: type | None = None
    val_type: Optional["MyType"] = None
    key_type: Optional["MyType"] = None

    name: str = ""
    uid: str = ""
    origin: type | None = None
    args: tuple["MyType", ...] = tuple()
    literal_members: list[Any] = []
    is_split: bool = False

    # -------------------
    # `.` Initial Methods
    # -------------------
    @classmethod
    def parse(cls, tvar: Any) -> "MyType":
        """Decompose a given type so that other methods can intelligently handly each part in turn.

        By far the most likely usecase is for containers such as `dict[str, int]` (which becomes the
        tuple `(dict, str, int)`) and `list[int]` (which becomes `(list, int, None)`), but it's
        useful for other generics, unions (e.g. `string | int`), and special non-type forms
        (e.g. `Annotated` and `Literal`). See `MyType.UNHANDLED_TYPES` for a best-effort list
        of unhandled annotations.

        Args:
            tvar: The type annotation to decompose -- either a type, a union of types, or None.
        Returns:
            1. The **main type** (e.g. `dict`, `list`, `int`, etc.) or `None` if unparseable.
            2. The **key type** (for mappings) or `None`.
            3. The **value type** (for any generics with just one type arg) or `None`.
        """
        try:
            return cls._parse(tvar)
        except Exception:
            if cls.RAISE:
                raise
            else:
                return cls(src_type=tvar)

    @classmethod
    def _parse(cls, src_type: Any) -> "MyType":
        if isinstance(src_type, MyType):
            return src_type

        uid = str(src_type)
        if cached := cls.PARSE_CACHE[uid]:
            return cached

        cls.PARSE_CACHE[uid] = ret = cls(src_type=src_type, uid=uid)
        return ret

    @pyd.model_validator(mode="after")
    def _process_src(self) -> Self:
        # 0. Validate & parse the source type
        if not self.src_type or not self.uid:
            return self
        self.name, self.origin, _args = self._read(self.src_type)

        # I. Catch edge cases: Unions, Unhandled types, simple wrappers, and Literals
        if options := self._split(self.src_type):
            self.args = tuple(map(self._parse, options))
            self.is_split = True
            self.main_type = self.origin if self.origin is not None else types.UnionType
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
            self.literal_members = list(sorted(_args))
            self.args = tuple(map(self.parse, set(map(type, _args))))
            return self

        if self.origin:
            # III. Catch generics
            self.main_type = self.origin
            self.args = tuple(self._process_args(_args))
            if not self.args:
                pass
            elif issubclass(self.origin, tuple):
                # III.i. Catch tuples (either monotyped or literal)
                if self.args[-1].src_type is Ellipsis:
                    if len(self.args) > 1:
                        self.val_type = self.args[0]
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

        elif issubclass(self.src_type, Counter):
            # IV. Niche case: Counters imply int values
            self.main_type = Counter
            self.val_type = self.parse(int)

        elif isinstance(self.src_type, type):
            # V. Catch atomic types
            self.main_type = self.src_type

        return self

    # -------------------
    # `-` Private Methods
    # -------------------
    def _process_args(self, args: tuple) -> Iterator["MyType"]:
        for arg in map(self.parse, args):
            if arg.origin is Unpack:
                yield from arg.args
            else:
                yield arg

    def literal_check(self, value: Any) -> bool:
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
                and all(
                    arg.check(val) for val, arg in zip(value, self.args, strict=True)
                )
            )
        return False

    @classmethod
    def _is_type(cls, tvar: Any) -> TypeGuard[type | types.GenericAlias]:
        return bool(
            tvar is not None
            and (name := getattr(tvar, "__name__", ""))
            and name not in cls.UNHANDLED_TYPES
        )

    @classmethod
    def _parseable(cls, tvar: Any) -> TypeGuard[type | tuple[type, ...]]:
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
        if tvar is None or isinstance(tvar, tuple):
            return "", None, tuple()
        name = str(getattr(tvar, "__name__", ""))
        origin = ty.get_origin(tvar)
        args = ty.get_args(tvar)

        if (
            not (origin or args)
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
    def _split(cls, tvar: Any) -> tuple:
        """Decompose a union or tuple type into its member types."""
        if isinstance(tvar, tuple):
            return tvar
        elif getattr(tvar, "__name__", "") in {"Union", "Unpack"} or isinstance(
            tvar, types.UnionType
        ):
            return ty.get_args(tvar)
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
        return f"{self.src_type}"

    def __repr__(self) -> str:
        parts = []
        if self.main_type is not None:
            parts.append(f"main={self.main_type}")
        if self.key_type is not None:
            parts.append(f"key={self.key_type}")
        if self.val_type is not None:
            parts.append(f"val={self.val_type}")
        if self.literal_members is not None:
            parts.append("[LIT]")
        return f"MyType[{self.src_type}]" + (f"({', '.join(parts)})" if parts else "")

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
        """Check if all values in an iterable match a type variable."""
        yield from map(self.check, iterable)

    def members(self) -> Iterator["MyType"]:
        """Yield all member types of this type variable."""
        if not self.main_type:
            return
        elif issubclass(self.main_type, pyd.BaseModel):
            yield from map(self.parse, ut.instance_fields(self.main_type).values())
        elif ty.is_typeddict(self.src_type):
            yield from map(self.parse, self.src_type.__annotations__.values())

    def issubclass(self, tvar: "type | types.UnionType | MyType | None") -> bool:
        """Check if this type variable is a subclass of another type variable."""
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
        """Get a simplified summary of this type variable.

        Returns:
            A tuple of the main type, key type, and value type (if any).
        """
        if not self:
            return (None, None, None)
        return (
            self.main_type,
            self.key_type.main_type if self.key_type else None,
            self.val_type.main_type if self.val_type else None,
        )
