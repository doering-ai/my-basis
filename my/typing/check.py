############
### HEAD ###
############
### STANDARD
from typing import overload, TypeIs, Literal, Any, TypeGuard
from collections.abc import Iterator
from types import EllipsisType, NoneType
from collections.abc import Iterable, Callable, Hashable
from enum import Enum
import inspect
import functools as ft

### EXTERNAL
import pydantic as pyd
import more_itertools as mi

### INTERNAL
from ..infra.types import (
    _Map,
    _Vec,
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
from .MyType import MyType, TypeArg
from ._TypingBase import _TypingBase
from ..utils import ut
from .match import tym
from .Metatype import Metatype as Meta


############
### BODY ###
############
class TypeCheck[T0, T1](_TypingBase, pyd.BaseModel):
    """Utilities for qualifying the types of data objects."""

    data: T0 = None  # type: ignore[assignment]
    root: TypeArg[T1] = None

    @ft.cached_property
    def t0(self) -> MyType[T0]:
        """The parsed type of the data."""
        return MyType.typeof(self.data)  # type: ignore[bad-return]

    @ft.cached_property
    def t1(self) -> MyType[T1]:
        """The parsed target type."""
        return MyType.new(self.root)  # type: ignore[bad-return]

    @ft.cached_property
    def is_split(self) -> bool:
        """Whether this type is a union or literal."""
        return self.t1.is_split

    # -------------------
    # `.` Initial Methods
    # -------------------
    def __call__(self) -> bool:
        """Determine whether the given data is a valid instance of the given type.

        This serves as the primary interface for the vast majority of caller usecases.
        """
        # I. Setup, validate
        target = self.t1.main
        if target is None:
            return True

        # II. Composite types
        if self.t1.is_split:
            return any(option.check(self.data) for option in self.t1.args)
        elif self.t1.literal_members:
            return self.is_literal(self.data, self.t1)

        # III. Special Forms
        match self.data, target, Meta(target):
            # III.i. `None` shortcuts
            case None, _target, _:
                return target is NoneType
            case _data, None, _:
                return False

            # III.ii. `types` Shortcuts shortcuts
            case _data, _target, _ if _target is NoneType or _data is None:
                return _target is NoneType and _data is None
            case _data, _target, _ if _target is NoneType or _data is None:
                return _target is EllipsisType and _data is Ellipsis
            case _, _, Meta.UNIV:
                return True
            case _, _, Meta.NONE:
                return False
            case _data, _target, Meta.TYPE:
                if _target is EllipsisType:
                    return self.data is Ellipsis
                return False

        # IV. Main cases: normal types, probably nested
        if self.t1.main is None or not isinstance(self.data, self.t1.main):
            return False
        elif self.t1.keys and self.t1.vals and self.is_map(self.data):
            if items := ut.map_items(self.data):
                keys, vals = mi.unzip(items)
                return self.check_all(keys, self.t1.keys) and self.check_all(vals, self.t1.vals)
        elif self.t1.vals and isinstance(self.data, Iterable):
            return self.check_all(self.data, self.t1.vals)

        return False

    # -------------------
    # `-` Private Methods
    # -------------------
    # -------------------
    # `+` Primary Methods
    # -------------------

    # ------------------
    # `*` Public Methods
    # ------------------
    @classmethod
    def is_stream(cls, data: object) -> TypeIs[Stream]:
        """Determine if a variable is a buff."""
        return isinstance(data, Stream)

    @classmethod
    def is_string(cls, data: object) -> TypeIs[String]:
        """Determine if a variable is a text."""
        return isinstance(data, String)

    @classmethod
    def is_scalar(cls, data: object) -> TypeIs[Scalar]:
        """Determine if a variable is a num."""
        return isinstance(data, Scalar)

    @classmethod
    def is_time(cls, data: object) -> TypeIs[Time]:
        """Determine if a variable is a time."""
        return isinstance(data, Time)

    @classmethod
    def is_atom(cls, data: object) -> TypeIs[Atom]:
        """Determine if a variable is an atom."""
        return (
            cls.is_string(data)
            or cls.is_scalar(data)
            or cls.is_time(data)
            or isinstance(data, Enum)
        )

    @classmethod
    def is_vec(cls, data: object) -> TypeIs[Vec]:
        """Determine if a variable is a vec."""
        return isinstance(data, Vec)

    @classmethod
    def is_map(cls, data: object) -> TypeIs[Map]:
        """Determine if a variable is a map."""
        if data is None or isinstance(data, type):
            return False
        elif isinstance(data, Map):
            return True
        elif cls.is_iter(data):
            pass
        return False

    @classmethod
    def is_map_item(cls, data: object) -> bool:
        """Check if this type represents a mapping item (2-tuple key-value pair).

        Returns:
            True if this is a tuple[K, V] with exactly 2 non-None type args.
        """
        return bool(
            data and isinstance(data, tuple) and len(data) == 2 and isinstance(data[0], Hashable)
        )

    @classmethod
    def is_iter(cls, data: object) -> TypeIs[Iter]:
        """Determine if a variable is an iterable that is NOT of another known type.."""
        return isinstance(data, Iterable) and not any(
            ut.apply((cls.is_string, cls.is_vec, cls.is_map), data)
        )

    @classmethod
    def is_struct(cls, data: object) -> TypeIs[Struct]:
        """Determine if a variable is a struct."""
        return any(ut.apply((cls.is_vec, cls.is_map, cls.is_model), data))

    @classmethod
    def is_func(cls, data: object) -> TypeIs[Func]:
        """Determine if a variable is a func."""
        return callable(data) or isinstance(data, Funcs)

    @classmethod
    def is_model(cls, data: object) -> TypeIs[Model]:
        """Determine if a variable is a model."""
        return data is not None and tym.is_model_type(type(data))

    @classmethod
    def is_literal[L](cls, data: Any, tvar: MyType[L]) -> TypeGuard[L]:
        """Check if a data matches this literal type.

        Args:
            data: The data to check.
            tvar: The literal type to check against.
        Returns:
            True if data matches the literal members.
        """
        origin, members, args = tvar.origin, tvar.literal_members, tvar.args
        if not members:
            return False
        elif origin is Literal:
            return data in members
        elif isinstance(origin, type) and issubclass(origin, tuple):
            return bool(
                (origin is not None and issubclass(origin, tuple) and isinstance(data, origin))
                and (args and args[-1].root is not EllipsisType and len(data) == len(args))
                and all(arg.check(data) for data, arg in zip(data, args, strict=True))
            )
        return False

    @classmethod
    def describe_func[**Pp](
        cls, fn: Callable[Pp, Any]
    ) -> tuple[dict[str, MyType], tuple[MyType, ...]]:
        """Return a string description of a function's signature."""
        sig = inspect.signature(fn)
        params = {name: param.annotation for name, param in sig.parameters.items()}
        if (_ret := sig.return_annotation) is inspect.Signature.empty:
            return (params, tuple())
        tvar = MyType.new(_ret)
        return params, (tvar.args if tvar.is_split else (tvar,))

    @classmethod
    def check[T](cls, data: object, tvar: TypeArg[T]) -> TypeIs[T]:
        """Determine whether the given data is a valid instance of the given type.

        Args:
            data: The data value to check. Ideally not an exhaustable iter.
            tvar: The type to check against. Can be a raw type, a MyType, or a TypeArg.
        Returns:
            True if *all* aspects of this type are satisfied by this data, including nested types.
        """
        inst = cls(data=data, root=tvar)
        return inst()

    @overload
    @classmethod
    def check_all[V](cls, data: _Map, tvar: TypeArg[V]) -> TypeIs[_Map[Any, V]]: ...
    @overload
    @classmethod
    def check_all[V](cls, data: _Vec, tvar: TypeArg[V]) -> TypeIs[_Vec[V]]: ...
    @overload
    @classmethod
    def check_all[V](cls, data: Iterable, tvar: TypeArg[V]) -> TypeIs[Iterable[V]]: ...
    @classmethod
    def check_all(cls, data: Iterable, tvar: TypeArg) -> bool:
        """Check if values in an iterable match this type.

        Args:
            data: The iterable of values to check.
            tvar: The type to check each value against.
        Yields:
            Boolean for each value indicating if it matches this type.
        """
        if isinstance(data, Iterator):
            _head, data = mi.spy(data)
        return all(cls.check(v, tvar) for v in data)


tyc = typecheck = TypeCheck
