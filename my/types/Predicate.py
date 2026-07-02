############
### HEAD ###
############
### STANDARD
from __future__ import annotations
from collections import Counter
from typing import ClassVar, Any, Self
from collections.abc import Iterable, Iterator
import regex as re
import itertools as it
import more_itertools as mi
from copy import deepcopy

### EXTERNAL
import pydantic as pyd

### INTERNAL
from ..infra.types import Vec, Map, Maps, Atom, Struct, _Map, _Vec
from ..utils import ut
from ..typing import Typist, MyType, ty

# Create a local typist with the most permissive possible configuration.
typist = Typist(firsts=True, atomics=True, splits=True, wraps=True)


############
### BODY ###
############
class Predicate(pyd.BaseModel):
    """A Pydantic model wrapping `dict[str, list[str]]` for string-based "vibe-typing" usage.

    It accepts input from various sources: dictionaries, JSON strings, lists of colon-separated
    strings, or other Predicates. The validator normalizes all inputs to the canonical
    dictionary-of-lists format, optionally deduplicating values.

    Serialization supports nested dictionary structures using dot notation in keys. A field like
    `"user.name"` becomes `{"user": {"name": value}}` in the output. The serializer can target
    different types via generic parameters, with intelligent type coercion for leaves and nesting.
    This makes Predicate suitable for representing structured data that originates as flat
    key-value pairs but needs hierarchical output.
    """

    RGXS: ClassVar[dict[str, re.Pattern]] = ut.regex_dict(
        dict(
            newline=r'\n',
            nonword=r'\W+',
            period=r' *\. *',
            colon=r' *: *',
            comma=r' *, *',
            jsonesque=r'{[^:\}]+:[^}]+}',
        )
    )
    DECAST_TYPES: ClassVar[tuple[type, ...]] = (str, int, float, bool, bytes)

    data: dict[str, list[str]] = {}
    duplicates: bool = False
    overwrite: bool = False

    # -------------------
    # `.` Initial Methods
    # -------------------
    @classmethod
    def new(
        cls,
        *args: Struct | Atom | Self | None,
        duplicates: bool = False,
        overwrite: bool = False,
        **kwargs,
    ) -> Self:
        """Construct a new Predicate instance, flexibly coercing most mapping-like objects."""
        ret = cls(duplicates=duplicates, overwrite=overwrite)
        for arg in (*args, kwargs):
            ret._process_arg(arg)
        ret.data = {k: v for k, v in ret.data.items() if k and v}
        return ret

    @pyd.model_serializer
    def _serialize_predicate(self) -> dict[str, str | list[str] | dict]:
        """Pydantic serializer method to convert the Predicate to its internal dict format."""
        return self._abbreviate(self.data)

    # -------------------
    # `-` Private Methods
    # -------------------
    def _process_arg(self, arg: Struct | Atom | Self | None) -> None:
        if not arg:
            return
        elif isinstance(arg, Predicate):
            self += deepcopy(arg.data)
        elif ty.is_model(arg):
            self += ty.cast(arg, dict, {})
        elif ty.is_map(arg):
            self += dict(arg)
        elif isinstance(arg, str):
            arg = arg.strip()
            if self.RGXS['jsonesque'].fullmatch(arg) and (_casted := typist.cast(arg, dict)):
                self += _casted
        elif ty.is_vec(arg) and (mapped := ty.cast(arg, dict)) is not None:
            # A vec of (key, value) pairs, e.g. [('k1', ['A', 'B'])].
            self += mapped
        elif ty.is_iter(arg):
            for sub_arg in arg:
                self._process_arg(sub_arg)
        else:
            raise TypeError(f'Cannot accept {type(arg)} argument to Predicate.new().')

    @classmethod
    def _abbreviate(cls, data: _Map[str, list[str] | dict]) -> dict[str, str | list[str] | dict]:
        """Recursively simplify one-element arrays into strings."""
        ret: dict[str, Any] = {}
        for field, values in dict(data).items():
            if ty.is_map(values):
                # I. Recursive case
                ret[field] = cls._abbreviate(dict(values))
            else:
                # II. Decast simple, atomic types (i.e. int, float, and bool)
                if ut.any_has_any(values, '\n'):
                    values = list(map(cls._escape, values))
                _vals = typist.flex_deserialize(values)

                # III. Just return one value if that's all there is
                ret[field] = _vals[0] if len(_vals) == 1 else _vals

        return ret

    @staticmethod
    def _escape(text: str) -> str:
        return Predicate.RGXS['newline'].sub(r'\\n', text)

    @classmethod
    def _cast_arg(
        cls,
        field: str,
        val: Any,
        duplicates: bool = False,
    ) -> Iterator[tuple[str, list[str]]]:
        """Cast an argument to a sequence of field-value pairs, handling nested structures.

        Args:
            field: The base field name for this argument (used for recursion).
            val: The value to cast, which may be a nested structure.
            duplicates: Whether to allow duplicate values in the output lists.
        Returns:
            Map item iterator, where keys may include dot notation for nested structures.
        """
        _map = ty.cast(val, dict[str, list[str]])
        if _map is not None:
            yield from _map.items()
            return

        if ty.is_model(val):
            val = ty.cast(val, dict)
        if isinstance(val, Maps):
            prefix = f'{field}.' if field else ''
            for c_field, c_val in dict(val).items():
                yield from cls._cast_arg(f'{prefix}{c_field}', c_val, duplicates)
        else:
            # Cast to list[str] first -- val may be a bare scalar (e.g. 'val'), which
            # unique_everseen() would otherwise iterate character-by-character.
            vec = ty.cast(val, list[str]) or []
            if not duplicates:
                vec = list(mi.unique_everseen(vec))
            yield (field, vec)

    @classmethod
    def _cast_to_str(cls, val: Any) -> str:
        """Durably cast a value to a string.

        Args:
            val: The value to cast.
        Returns:
            A string representation of the value.
        """
        if val is None:
            return ''
        elif isinstance(val, str):
            ret = val
        if (fn := typist.get_str_method(val)) and (ret := typist.invoke(fn)) is not None:
            return ret
        return str(val)

    @classmethod
    def _deepen(
        cls,
        node_items: list[tuple[tuple[str, ...], list[str]]],
        kvar: MyType | None,
        vvar: MyType | None,
    ) -> dict[str, Any]:
        """Serialize a nested dictionary structure."""
        # I. Separate leaves from branches
        leaves, branches = mi.partition(lambda item: len(item[0]) > 1, node_items)
        ret = {}
        for key, val in leaves:
            _key = key[0]
            if kvar is not None:
                _key = typist.cast(_key, kvar)
                assert _key is not None, f'Failed to cast key {key[0]} to {kvar}.'

            _val = val
            if vvar is not None:
                _val = typist.cast(_val, vvar)
                assert _val is not None, f'Failed to cast {val} to {vvar}.'

            ret[_key] = _val

        # II. Group the keys by their first item and recurse
        for base, _items in it.groupby(branches, key=lambda item: item[0][0]):
            items = [(key[1:], vals) for key, vals in _items]
            lens = {len(key) for key, _ in items}
            assert 0 not in lens, f'A node w/ children cannot also have its own values: {items=}'
            ret[base] = cls._deepen(items, kvar, vvar)

        return ret

    # -------------------
    # `+` Primary Methods
    # -------------------
    def to_yaml(self, **kwargs) -> str:
        """Serialize the Predicate to a YAML string."""
        return ut.to_yaml(self._abbreviate(self.data))

    @classmethod
    def from_yaml(cls, text: str, **kwargs) -> Predicate:
        """Create a Predicate from a YAML string."""
        return cls.new(ut.from_yaml(text), **kwargs)

    def write(self, field: str, value: Atom | Struct, overwrite: bool | None = None):
        """Add a value to a field in this predicate, with custom overriding logic.

        Args:
            field: The field to write to.
            value: The value to write.
            overwrite: Whether to overwrite existing values. If `None`, uses the instance's
                `overwrite` setting.
        """
        overwrite = self.overwrite if overwrite is None else overwrite
        for key, val in self._cast_arg(field, value, self.duplicates):
            if overwrite or key not in self.data:
                self.data[key] = val
            else:
                if not self.duplicates:
                    val = list(it.filterfalse(self[key].__contains__, val))
                self.data[key].extend(val)

    # ------------------
    # `*` Public Methods
    # ------------------
    # --------------
    # `*0` Overrides
    # --------------
    def __len__(self) -> int:
        return len(self.data)

    def __bool__(self) -> bool:
        return bool(self.data)

    def __str__(self) -> str:
        return self.to_yaml()

    def __repr__(self) -> str:
        return f'{self._abbreviate(self.data)}'

    def __getitem__(self, field: str) -> list[str]:
        """Get the values associated with a field in the predicate.

        Args:
            field: The field to get values for.
        Returns:
            A list of string captures if the field exists, else an empty list.
        """
        return self.data.get(field, [])

    def __setitem__(self, field: str, val: Any):
        """Set the values for a field in the predicate, OVERWRITING ANY EXISTING VALUES."""
        self.write(field, val, overwrite=True)

    def __delitem__(self, field: str):
        """Remove a field from the predicate, if it exists."""
        if field in self.data:
            del self.data[field]

    def __contains__(self, other: object) -> bool:
        if isinstance(other, str):
            # I. Basic key check
            return other in self.data
        elif not isinstance(other, Maps) and isinstance(other, Iterable) and ty.all_are(other, str):
            # II. Check for a collection of keys -- excludes Maps, since iterating a dict yields
            # its (string) keys too, which would otherwise steal every dict `other` away from the
            # key:value comparison in branch III below.
            return self.has_all(*other)
        elif isinstance(other, (Vec, *Maps, Predicate)):
            # III. Check for key: value pairs (NOT paying attention to value ordering)
            _other = self.new(other, duplicates=self.duplicates)
            assert isinstance(_other, Predicate)  # no idea...
            if not self.has_all(*_other.keys()):
                return False

            if self.duplicates:
                # III.i. If duplicates are possible, we must compare occurrence counts
                for field, values in _other.items():
                    counts = Counter(self.data[field])
                    if any(counts[value] < count for value, count in Counter(values).items()):
                        return False
                return True
            else:
                # III.ii. Otherwise, just compare basic presence of each value
                return all(
                    ut.has_all(self[_field], *set(values)) for _field, values in _other.items()
                )
        else:
            return False

    def __eq__(self, other: object) -> bool:
        """Determines if two Predicates are equal, casting where possible.

        A Predicate is equal to another if they A) have the same keys, and B) each key has the same
        values, regardless of order.
        """
        if isinstance(other, Predicate):
            rhs = other
        else:
            try:
                rhs = Predicate.new(other, duplicates=self.duplicates)
            except Exception:
                return False

        if (
            len(self) != len(rhs)
            or set(self.keys()) != set(rhs.keys())
            or any(len(self[field]) != len(rhs[field]) for field in self.keys())
        ):
            return False

        for key in self.keys():
            counters = Counter(self[key]), Counter(rhs[key])
            if counters[0] != counters[1]:
                return False
        return True

    def __ne__(self, other: object) -> bool:
        return not (self == other)

    def __iadd__(self, other: object) -> Self:
        """Add all values from another predicate into this one, appending to existing fields."""
        if not other:
            return self
        elif items := ty.cast(other, dict[str, list[str]]):
            for key, value in items.items():
                self.write(key, value, overwrite=False)
            return self
        else:
            raise TypeError(f'Cannot add {type(other)} to Predicate')

    def __ior__(self, other: Map | Self) -> Self:
        """Update this predicate with fields from another, leaving overwriting up to defaults."""
        if not other:
            return self
        elif items := ty.cast(other, dict[str, list[str]]):
            for key, value in items.items():
                self.write(key, value)
            return self
        else:
            raise TypeError(f'Cannot merge {type(other)} into Predicate')

    def __iand__(self, other: Map | Vec | Self) -> Self:
        """Remove all values from this predicate that aren't present in the other."""
        if not other:
            self.data.clear()
        elif ty.check(other, _Vec[str]):
            for key in self.keyset - set(other):
                del self.data[key]
        else:
            #     rhs = ty.cast(other, dict[str, list[str]])
            pred = Predicate.new(other, duplicates=self.duplicates)
            shared_keys = self.keyset & pred.keyset
            self.data = {key: ut.common_elements(self[key], pred[key]) for key in shared_keys}
        return self

    def __isub__(self, other: Map | Vec | Self) -> Self:
        """Remove values from this predicate that are present in the other."""
        if not other:
            return self
        elif ty.check(other, _Vec[str]):
            for key in self.keyset & set(other):
                del self.data[key]
        elif items := ty.cast(other, dict[str, list[str]]):
            for key in self.keyset & set(items.keys()):
                self.data[key] = [v for v in self.data[key] if v not in items[key]]
                if len(self.data[key]) == 0:
                    del self.data[key]
        return self

    def __add__(self, other: Map | Self) -> Self:
        ret = self.model_copy(deep=True)
        ret += other
        return ret

    def __or__(self, other: Map | Self) -> Self:
        ret = self.model_copy(deep=True)
        ret |= other
        return ret

    def __and__(self, other: Map | Vec | Self) -> Self:
        ret = self.model_copy(deep=True)
        ret &= other
        return ret

    def __sub__(self, other: Map | Vec | Self) -> Self:
        ret = self.model_copy(deep=True)
        ret -= other
        return ret

    # ---------------
    # `*1` Properties
    # ---------------
    @property
    def size(self) -> int:
        """The number of individual values in this predicate (i.e. cells, not just rows)."""
        return sum(map(len, self.data.values()))

    @property
    def keyset(self) -> set[str]:
        """The set of keys in this predicate."""
        return set(self.data.keys())

    # --------------
    # `*2` Accessors
    # --------------
    def has_any(self, *fields: str) -> bool:
        """Check if any of the specified fields exist in the predicate."""
        return any(field in self.data for field in fields)

    def has_all(self, *fields: str) -> bool:
        """Check if all of the specified fields exist in the predicate."""
        return all(field in self.data for field in fields)

    def has_only(self, *fields: str) -> bool:
        """Check if the predicate contains only the specified fields."""
        return not (set(self.keys()) ^ set(fields))

    def keys(self) -> list[str]:
        """Get a list of all keys in the predicate."""
        return list(self.data.keys())

    def values(self) -> list[list[str]]:
        """Get a list of all values in the predicate."""
        return list(self.data.values())

    def items(self) -> list[tuple[str, list[str]]]:
        """Get a list of all key-value pairs in the predicate."""
        return list(self.data.items())

    def get(self, field: str, default: list[str] | None = None) -> list[str]:
        """Get the values associated with a field, or a default if the field is not present."""
        if default is None:
            default = []
        return self.data.get(field, default)

    def pop(self, field: str, default: list[str] | None = None) -> list[str]:
        """Remove and return a field's values, or a default if it doesn't exist."""
        if default is None:
            default = []
        return self.data.pop(field, default)

    def at(self, field: str, default: str = '') -> str:
        """Get the last unique value associated with a field, or a default if none exist."""
        if field in self:
            for i, val in enumerate(reversed(self.data[field])):
                if val and not any(pval.endswith(val) for pval in self.data[field][: i - 1]):
                    return val

        return default

    def pop_at(self, field: str, idx: int = -1, default: str = '') -> str:
        """Remove and return a value at a specific index for a field, or a default if not found."""
        if field in self.data and idx < len(self.data[field]):
            ret = self.data[field].pop(idx)

            if len(self.data[field]) == 0:
                del self.data[field]
        else:
            ret = default
        return ret

    # -------------
    # `*3` Mutators
    # -------------
    def add_to_set(self, field: str, value: Any) -> None:
        """Add a value to the set of values for a given field, creating it if necessary.

        Args:
            field: The field to add the value to.
            value: The value to add, which will be cast to a string and added if not present.
        """
        new = ty.cast(value, list[str])
        if new is None:
            raise TypeError(f'Cannot cast {value} to list[str] for field {field}.')
        self.data[field] = list(mi.unique_everseen([*self.data.get(field, []), *new]))
