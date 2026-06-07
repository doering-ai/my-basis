############
### HEAD ###
############
### STANDARD
from typing import overload, TypeIs, is_typeddict, Literal, Any, TypeGuard
from collections.abc import Iterator
from types import EllipsisType, NoneType
from collections.abc import Iterable, Callable
from enum import Enum
from dataclasses import is_dataclass
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
from .MyType import MyType
from ._common import TypeArg
from ..utils import ut


############
### BODY ###
############
class Check[T0, T1](pyd.BaseModel):
    """Utilities for qualifying the types of data objects."""

    data = T0
    root = TypeArg[T1]

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
        """Determine whether the given data is a valid instance of the given type."""
        # Special types
        if not self.t1:
            return True
        elif self.data is None:
            return self.root is NoneType
        elif self.data is Ellipsis:
            return self.root is EllipsisType
        elif (
            self.t0.origin
            and getattr(self.t0.origin, '__name__', '') in MyType.FILTERS['unhandled']
        ):
            return False

        # Composite types
        if self.t1.is_split:
            return any(option.check(self.data) for option in self.t1.args)
        elif self.t1.literal_members:
            return self.is_literal(self.data, self.t1)

        # Main cases: normal types, probably nested
        if self.t1.main is None:
            return False
        elif not isinstance(self.data, self.t1.main):
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
        return bool(main := MyType.new(tvar).main) and issubclass(main, Streams)

    @classmethod
    def is_stream(cls, data: object) -> TypeIs[Stream]:
        """Determine if a variable is a buff."""
        return isinstance(data, Streams)

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
        return bool(main := MyType.new(tvar).main) and issubclass(main, Strings)

    @classmethod
    def is_string(cls, data: object) -> TypeIs[String]:
        """Determine if a variable is a text."""
        return isinstance(data, Strings)

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
        return bool(main := MyType.new(tvar).main) and issubclass(main, Scalars)

    @classmethod
    def is_scalar(cls, data: object) -> TypeIs[Scalar]:
        """Determine if a variable is a num."""
        return isinstance(data, Scalars)

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
        return bool(main := MyType.new(tvar).main) and issubclass(main, Times)

    @classmethod
    def is_time(cls, data: object) -> TypeIs[Time]:
        """Determine if a variable is a time."""
        return isinstance(data, Times)

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
        return bool(main := MyType.new(tvar).main) and (
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
        return bool(main := MyType.new(tvar).main) and issubclass(main, Vecs)

    @classmethod
    def is_vec(cls, data: object) -> TypeIs[Vec]:
        """Determine if a variable is a vec."""
        return isinstance(data, Vecs)

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
        main = MyType.new(tvar).main
        if not main:
            return False
        elif issubclass(main, Maps):
            return True
        elif cls.is_iter_type(main):
            pass
        return False

    @classmethod
    def is_map(cls, data: object) -> TypeIs[Map]:
        """Determine if a variable is a map."""
        if data is None or isinstance(data, type):
            return False
        elif isinstance(data, Maps):
            return True
        elif cls.is_iter(data):
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
            bool(main := MyType.new(tvar).main)
            and issubclass(main, Iterable)
            and not issubclass(main, (str, bytes, *Streams))
        )

    @classmethod
    def is_iter(cls, data: object) -> TypeIs[Iter]:
        """Determine if a variable is an iterable that is NOT of another known type.."""
        return isinstance(data, Iterable) and not isinstance(data, (*Strings, *Structs))

    # ---- STRUCT ----
    @classmethod
    def is_struct_type(cls, tvar: type) -> TypeIs[type[Struct]]:
        """Determine if a variable is a struct type."""
        return isinstance(tvar, type) and (
            cls.is_vec_type(tvar) or cls.is_map_type(tvar) or cls.is_model_type(tvar)
        )

    @classmethod
    def is_struct(cls, data: object) -> TypeIs[Struct]:
        """Determine if a variable is a struct."""
        return cls.is_vec(data) or cls.is_map(data) or cls.is_model(data)

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

    @classmethod
    def is_func(cls, data: object) -> TypeIs[Func]:
        """Determine if a variable is a func."""
        return callable(data) or isinstance(data, Funcs)

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
        return bool(main := MyType.new(tvar).main) and (
            issubclass(main, pyd.BaseModel)
            or is_typeddict(main)
            or pyd.dataclasses.is_pydantic_dataclass(main)
            or is_dataclass(main)
        )

    @classmethod
    def is_model(cls, data: object) -> TypeIs[Model]:
        """Determine if a variable is a model."""
        return data is not None and cls.is_model_type(type(data))

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


ty = typecheck = Check
