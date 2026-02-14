############
### HEAD ###
############
### STANDARD
from collections import Counter
from typing import ClassVar, Any, Self
from collections.abc import Iterable, Iterator, Mapping
import regex as re
import itertools as it
import more_itertools as mi

### EXTERNAL
import pydantic as pyd
import json

### INTERNAL
from ..infra import T, Series, Map, _Series
from ..utils import ut
from ..typing import Typist, MyType

# Create a local typist with the most permissive possible configuration.
typist = Typist(firsts=True, atomics=True, splits=True, wraps=True)

re.DEFAULT_VERSION = re.VERSION1


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
        *args: Any,
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
    def serialize(
        self,
        fields: Iterable[str] | None = None,
        tvar: type[T] | None = None,
    ) -> T | dict:
        """Cast data to one of a few supported types."""
        fields = fields if fields is not None else self.keys()
        source: dict[str, Any] = {field: self[field] for field in sorted(fields) if field in self}

        # I. Handle the nocast and empty cases
        if not source:
            return source

        # II. Handle trivial casting targets
        if tvar is str:
            return json.dumps(source, ensure_ascii=True).replace('\n', ' ')  # type:ignore
        elif tvar == list[str]:
            return [
                f'"{field}": {json.dumps(val, ensure_ascii=True)}' for field, val in source.items()
            ]  # type:ignore
        elif tvar is Predicate:
            return Predicate.new(source)  # type:ignore
        elif tvar is None:
            tvar = dict[str, Any]  # type:ignore

        # III. Prepare to cast the data by parsing the tvar argument, if possible
        target = typist.parse(tvar)
        if not target:
            return source
        kvar, vvar = target.key_type, target.val_type

        # IV. Expand nested structures into new dicts
        if ut.any_has_any(source.keys(), '.') and (
            vvar is None or typist.match(vvar, Mapping, intersect=True)
        ):
            ret = {}
            leaves, nodes = mi.partition(lambda item: '.' in item[0], source.items())
            ret |= dict(leaves)
            if node_items := [(tuple(key.split('.')), values) for key, values in sorted(nodes)]:
                ret |= self._deepen(node_items, kvar, vvar)
        else:
            ret = source

        # V. Wrap the final product in the requested final type
        _cast = typist.cast(ret, target)
        return _cast if _cast is not None else source

    # -------------------
    # `-` Private Methods
    # -------------------
    def _process_arg(self, arg: Any) -> None:
        if not arg:
            return
        elif isinstance(arg, Predicate):
            self += arg
        elif ut.is_map(arg):
            self += dict(arg)
        elif isinstance(arg, str):
            arg = arg.strip()
            if self.RGXS['jsonesque'].fullmatch(arg) and (_casted := typist.cast(arg, dict)):
                self += _casted
        elif isinstance(arg, Iterable):
            for sub_arg in arg:
                self._process_arg(sub_arg)
        else:
            raise TypeError(f'Cannot accept {type(arg)} argument to Predicate.new().')

    @classmethod
    def _abbreviate(cls, data: Mapping[str, list[str] | dict]) -> dict[str, Any]:
        """Find one-element arrays and simplify them to just be strings."""
        ret: dict[str, Any] = {}
        for field, values in data.items():
            if isinstance(values, Mapping):
                # I. Recursive case
                ret[field] = cls._abbreviate(values)  # type: ignore
            else:
                # II. Decast simple, atomic types (i.e. int, float, and bool)
                if ut.any_has_any(values, '\n'):  # type: ignore
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
        if isinstance(val, Mapping | Predicate):
            prefix = f'{field}.' if field else ''
            for c_field, c_val in val.items():
                yield from cls._cast_arg(f'{prefix}{c_field}', c_val, duplicates)
        else:
            yield (field, cls._cast_to_list(val, duplicates))

    @classmethod
    def _cast_to_list(cls, val: Any, duplicates: bool = False) -> list[str]:
        """Cast a value to a list of strings, optionally deduplicating entries.

        Args:
            val: The value to cast.
            duplicates: Whether to allow duplicate entries in the output list.
        Returns:
            A list of strings.
        """
        if isinstance(val, str):
            return [val]
        elif isinstance(val, Series):
            data = list(map(cls._cast_to_str, val))
            return data if duplicates else list(mi.unique_everseen(data))
        else:
            return [cls._cast_to_str(val)]

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
        return typist.to_yaml(self._abbreviate(self.serialize()), **kwargs)

    @classmethod
    def from_yaml(cls, text: str, **kwargs) -> 'Predicate':
        """Create a Predicate from a YAML string."""
        return cls.new(typist.from_yaml(text), **kwargs)

    def write(self, field: str, value: Any, overwrite: bool | None = None):
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
        elif isinstance(other, Series) and typist.all_are(other, str):
            # II. Check for a collection of keys
            return self.has_all(*other)
        elif isinstance(other, dict | list | Predicate):
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

    def __iadd__(self, other: Map | Self) -> Self:
        """Add all values from another predicate into this one, appending to existing fields."""
        if not other:
            return self
        if isinstance(other, Predicate):
            other = other.data

        if items := ut.map_items(other):
            for key, value in items:
                self.write(key, value, overwrite=False)
            return self
        else:
            raise TypeError(f'Cannot add {type(other)} to Predicate')

    def __ior__(self, other: Map | Self) -> Self:
        """Update this predicate with fields from another, leaving overwriting up to defaults."""
        if not other:
            return self
        if isinstance(other, Predicate):
            other = other.data

        if items := ut.map_items(other):
            for key, value in items:
                self.write(key, value)
            return self
        else:
            raise TypeError(f'Cannot merge {type(other)} into Predicate')

    def __iand__(self, other: Map | _Series[str] | Self) -> Self:
        """Remove all values from this predicate that aren't present in the other."""
        if isinstance(other, Predicate):
            other = other.data

        if not other:
            self.data.clear()
        elif isinstance(other, Series) and typist.all_are(other, str):
            for key in self.keyset - set(other):
                del self.data[key]
        else:
            if not isinstance(other, Predicate):
                pred = Predicate.new(other, duplicates=self.duplicates)
            shared_keys = self.keyset & pred.keyset
            self.data = {key: ut.common_elements(self[key], other[key]) for key in shared_keys}
        return self

    def __isub__(self, other: Map | _Series[str] | Self) -> Self:
        """Remove values from this predicate that are present in the other."""
        if isinstance(other, Predicate):
            other = other.data

        if not other:
            pass
        elif isinstance(other, Series) and typist.all_are(other, str):
            for key in self.keyset & set(other):
                del self.data[key]
        else:
            if not isinstance(other, Predicate):
                other = Predicate.new(other, duplicates=self.duplicates)
            for key in self.keyset & other.keyset:
                self.data[key] = [v for v in self.data[key] if v not in other[key]]
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

    def __and__(self, other: Map | _Series[str] | Self) -> Self:
        ret = self.model_copy(deep=True)
        ret &= other
        return ret

    def __sub__(self, other: Map | _Series[str] | Self) -> Self:
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
    def add_to_set(self, field: str, value: Any):
        """Add a value to the set of values for a given field, creating it if necessary."""
        _val = self._cast_to_list(value, duplicates=False)
        if field not in self.data:
            self.data[field] = _val
        else:
            target = self.data[field]
            target.extend(it.filterfalse(target.__contains__, _val))
