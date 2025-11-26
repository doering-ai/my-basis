############
### HEAD ###
############
### STANDARD
from collections import Counter, deque
from typing import (
    ClassVar,
    Iterable,
    Iterator,
    Mapping,
    TypeVar,
    Any,
)
import regex as re
import itertools as it
import more_itertools as mi

### EXTERNAL
import pydantic as pyd
import logfire
import json

### INTERNAL
from ..base import utils as ut
from .Typist import Typist, TypeArg

typist = Typist(firsts=True, splits=True)

############
### DATA ###
############
NEWLINE_RGX = re.compile(r'\n')
NONWORD_RGX = re.compile(r'\W+')
PERIOD_RGX = re.compile(r' *\. *')
COLON_RGX = re.compile(r' *: *')
COMMA_RGX = re.compile(r' *, *')

SplitItems = list[tuple[tuple[str, ...], list[str]]]

T = TypeVar('T')
Map = TypeVar('Map')
Key = TypeVar('Key')
Value = TypeVar('Value')
SubType = TypeVar('SubType', bound='Predicate')

Series = list | tuple | set | deque


############
### BODY ###
############
class Predicate(pyd.BaseModel):
    DECAST_TYPES: ClassVar[tuple[type, ...]] = (str, int, float, bool, bytes)

    data: dict[str, list[str]] = {}
    duplicates: bool = False
    overwrite: bool = False

    # -------------------
    # `0` Initial Methods
    # -------------------
    @classmethod
    def new(cls: type[SubType], data: Any | None = None, **kwargs) -> SubType:
        """
        Create a new Predicate instance from the given data, which can be a dictionary, a list of
        tuples, or another Predicate.
        """
        if isinstance(data, cls):
            return data.model_copy(deep=True, update=kwargs)
        elif data is None:
            data = {}
        return cls(data=data, **kwargs)

    @pyd.model_validator(mode='before')
    @classmethod
    def _validate_data(cls, kwargs: dict[str, Any]) -> dict[str, Any]:
        # I. Base case: parse maps and lists of items (i.e. 2-tuples)
        data = kwargs.pop('data', {})
        items = ut.map_items(data)
        if not items:
            try:
                if isinstance(data, str) and (_json := json.loads(data, strict=False)):
                    # II.i. Parse JSON objects
                    items = ut.map_items(_json)
                elif (
                    isinstance(data, Series)
                    and typist.all_are(data, str)
                    and ut.all_has_all(data, ':')
                ):
                    if all(text.startswith('{') and text.endswith('}') for text in data):
                        # II.ii. Parse lists of JSON objects
                        if all(_jsons := [json.loads(text, strict=False) for text in data]):
                            items = list(mi.flatten(map(ut.map_items, _jsons)))
                    elif _json := json.loads(f'{{{", ".join(data)}}}', strict=False):
                        # II.iii. Parse lists of JSON fields
                        items = ut.map_items(_json)
            except Exception:
                items = []

        # III. Finally, rely on the cast() function for standardizing everything
        duplicates = kwargs.get('duplicates', False)
        cast_items = mi.flatten(cls.cast(str(field), val, duplicates) for field, val in items)
        kwargs['data'] = {field: val for field, val in cast_items if bool(field and val)}
        return kwargs

    @pyd.model_serializer
    def serialize(
        self, fields: Iterable[str] | None = None, tvar: type[T] | None = None
    ) -> T | dict:
        """Cast data to one of a few supported types."""
        fields = fields if fields is not None else self.keys()
        source = {field: self[field] for field in sorted(fields) if field in self}

        # I. Handle the nocast and empty cases
        if not source or tvar is None:
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

        # III. Cast data to the requested type
        return self._serialize_cast(source, tvar)

    # -------------------
    # `-` Private Methods
    # -------------------
    @classmethod
    def _abbreviate(cls, data: Mapping[str, list[str] | dict]) -> dict[str, Any]:
        """Find one-element arrays and simplify them to just be strings."""
        ret: dict[str, Any] = {}
        for field, values in data.items():
            if isinstance(values, Mapping):
                # I. Recursive case
                ret[field] = cls._abbreviate(values)
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
        return NEWLINE_RGX.sub(r'\\n', text)

    def _serialize_cast(self, source: dict[str, list[str]], req_tvar: type[T] | None = None) -> T:
        """
        Serialize a dictionary structure, casting keys and values to the requested types.
        """
        # II. Cast the keys and values appropriately
        tvar, ktype, vtype = typist.parse(req_tvar)
        if ktype is str:
            ktype = None
        ret: dict = {}

        if (
            ktype
            or (vtype and not typist.match(vtype, Mapping))
            or not ut.any_has_any(source.keys(), '.')
        ):
            # III. Skip nesting if the types or values don't permit it
            ret = dict(
                zip(
                    typist.flexcast_all(source.keys(), ktype),
                    typist.flexcast_all(source.values(), vtype),
                    strict=False,
                )
            )
        else:
            # IV. Separate out and handle nested fields
            leaves, nodes = map(list, mi.partition(lambda item: '.' in item[0], source.items()))
            if leaves:
                # IV.i. Handle leaves as above, without casting keys
                ret = {field: typist.flexcast(vals, vtype) for field, vals in leaves}

            if nodes:
                # IV.ii. Group into nested dictionaries based on the first key
                node_items = list(sorted((tuple(key.split('.')), values) for key, values in nodes))
                ret |= self._serialize_nested(node_items, vtype)

        # V. Wrap the final product in the requested final type, if present
        return typist.flexcast(ret, tvar) if tvar else ret  # type:ignore

    def _serialize_nested(
        self, node_items: list[tuple[tuple[str, ...], list[str]]], tvar: TypeArg = None
    ) -> dict[str, Any]:
        """
        Serialize a nested dictionary structure, casting keys and values to the requested types.
        """
        ret: dict[str, Any] = {}
        for base, _items in it.groupby(node_items, key=lambda item: item[0][0]):
            items = [(key[1:], vals) for key, vals in _items]
            lens = {len(key) for key, _ in items}
            assert 0 not in lens, f'Found empty keys in {items=}'

            if lens == {1}:
                ret[base] = {key[0]: typist.flexcast(val, tvar) for key, val in items}
            else:
                ret[base] = self._serialize_nested(items, tvar)
        return ret

    @classmethod
    def cast_to_list(cls, val: Any, duplicates: bool = False) -> list[str]:
        if isinstance(val, str):
            return [val]
        elif isinstance(val, Series):
            data = list(map(cls.cast_to_str, val))
            return data if duplicates else list(mi.unique_everseen(data))
        else:
            return [cls.cast_to_str(val)]

    @classmethod
    def cast_to_str(cls, val: Any) -> str:
        if val is None:
            return ''
        elif isinstance(val, str):
            ret = val
        elif hasattr(val, '__str__'):
            return str(val)
        elif hasattr(val, 'toString'):
            ret = val.toString()
        elif hasattr(val, 'to_string'):
            ret = val.to_string()
        else:
            logfire.error(f'Passed non-serializable value `{val}` of type {type(val)}')
            return 'ERROR'
        return ret

    # -------------------
    # `+` Primary Methods
    # -------------------
    def to_yaml(self, **kwargs) -> str:
        return typist.to_yaml(self._abbreviate(self.serialize()), **kwargs)

    @classmethod
    def from_yaml(cls, text: str, **kwargs) -> 'Predicate':
        """
        Create a Predicate from a YAML string.
        """
        data = typist.from_yaml(text)
        assert isinstance(data, dict), f'Expected a dictionary, got {type(data)}'
        return cls.new(data, **kwargs)

    def write(self, field: str, value: Any, overwrite: bool | None = None):
        overwrite = self.overwrite if overwrite is None else overwrite
        for key, val in self.cast(field, value, self.duplicates):
            if overwrite or key not in self.data:
                self.data[key] = val
            else:
                if not self.duplicates:
                    val = list(it.filterfalse(self[key].__contains__, val))
                self.data[key].extend(val)

    @classmethod
    def cast(
        cls,
        field: str,
        val: Any,
        duplicates: bool = False,
    ) -> Iterator[tuple[str, list[str]]]:
        if isinstance(val, Mapping | Predicate):
            yield from cls.import_map(val, field, duplicates)
        else:
            yield (field, cls.cast_to_list(val, duplicates))

    @classmethod
    def import_map(
        cls,
        data: 'Mapping|Predicate',
        parent: str = '',
        duplicates: bool = False,
    ) -> Iterator[tuple[str, list[str]]]:
        """
        Cast a dictionary to a list of predicate slots, expanding nested dictionaries by separating
        keys with `.` characters.
        """
        parent = f'{parent}.' if parent else ''
        for field, val in data.items():
            key = f'{parent}{field}'
            if isinstance(val, Mapping | Predicate):
                yield from cls.import_map(val, parent=key)
            else:
                yield (key, cls.cast_to_list(val, duplicates))

    # ------------------
    # `x` Public Methods
    # ------------------
    def __str__(self) -> str:
        return self.to_yaml()

    def __repr__(self) -> str:
        return f'{self._abbreviate(self.data)}'

    def __getitem__(self, field: str) -> list[str]:
        """
        Get the values associated with a field in the predicate.
        If the field does not exist, return an empty list.
        """
        return self.data.get(field, [])

    def __setitem__(self, field: str, val: Any):
        self.write(field, val, overwrite=True)

    def __delitem__(self, field: str):
        """
        Remove a field from the predicate.
        If the field does not exist, do nothing.
        """
        if field in self.data:
            del self.data[field]

    def __bool__(self) -> bool:
        return bool(self.data)

    def __contains__(self, obj: object) -> bool:
        if isinstance(obj, str):
            # I. Basic key check
            return obj in self.data
        elif isinstance(obj, Series) and typist.all_are(obj, str):
            # II. Check for a collection of keys
            return self.has_all(*obj)  # type: ignore
        else:
            # III. Check for key: value pairs (NOT paying attention to value ordering)
            other = Predicate.new(obj, duplicates=self.duplicates)
            if not self.has_all(*other.keys()):
                return False

            if self.duplicates:
                # III.i. If duplicates are possible, we must compare occurrence counts
                for field, values in other.items():
                    counts = Counter(self.data[field])
                    if any(counts[value] < count for value, count in Counter(values).items()):
                        return False
                return True
            else:
                # III.ii. Otherwise, just compare basic presence of each value
                return all(
                    ut.has_all(self[_field], *set(values)) for _field, values in other.items()
                )

    def __eq__(self, other: object) -> bool:
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

        for field in self.keys():
            counters = Counter(self[field]), Counter(rhs[field])
            if counters[0] != counters[1]:
                return False
        return True

    def __ne__(self, other: object) -> bool:
        return not (self == other)

    def __iadd__(self: SubType, other: object) -> SubType:
        for field, value in ut.map_items(other):
            self.write(field, value, overwrite=False)
        return self

    def __ior__(self: SubType, other: object) -> SubType:
        for field, value in ut.map_items(other):
            self.write(field, value, overwrite=True)
        return self

    def __iand__(self: SubType, other: object) -> SubType:
        filter_items = Predicate.new(other, duplicates=self.duplicates).items()
        self.data = {
            field: ut.common_elements(self[field], values)
            for field, values in filter_items
            if field in self.data
        }
        return self

    def __isub__(self: SubType, other: object) -> SubType:
        if not other:
            pass
        elif isinstance(other, Series) and typist.all_are(other, str):
            for field in filter(self.__contains__, set(other)):
                del self.data[field]
        elif items := ut.map_items(other):
            for field, values in filter(lambda item: item[0] in self.data, items):
                values = self.cast_to_list(values, self.duplicates)
                self.data[field] = list(it.filterfalse(values.__contains__, self.data[field]))
                if len(self.data[field]) == 0:
                    del self.data[field]
        else:
            raise TypeError(f'Cannot subtract {type(other)} from Predicate')
        return self

    def __add__(self: SubType, other: object) -> SubType:
        ret = self.model_copy(deep=True)
        ret += other
        return ret

    def __or__(self: SubType, other: object) -> SubType:
        ret = self.model_copy(deep=True)
        ret |= other
        return ret

    def __and__(self: SubType, other: object) -> SubType:
        ret = self.model_copy(deep=True)
        ret &= other
        return ret

    def __sub__(self: SubType, other: object) -> SubType:
        ret = self.model_copy(deep=True)
        ret -= other
        return ret

    def __len__(self) -> int:
        return len(self.data)

    # Properties
    @property
    def size(self) -> int:
        return sum(map(len, self.data.values()))

    @property
    def keyset(self) -> set[str]:
        return set(self.data.keys())

    # Helpers
    def has_any(self, *fields: str) -> bool:
        return any(field in self.data for field in fields)

    def has_all(self, *fields: str) -> bool:
        return all(field in self.data for field in fields)

    def has_only(self, *fields: str) -> bool:
        return not (set(self.keys()) ^ set(fields))

    def keys(self) -> list[str]:
        return list(self.data.keys())

    def values(self) -> list[list[str]]:
        return list(self.data.values())

    def items(self) -> list[tuple[str, list[str]]]:
        return list(self.data.items())

    def get(self, field: str, default: list[str] | None = None) -> list[str]:
        if default is None:
            default = []
        return self.data.get(field, default)

    def pop(self, field: str, default: list[str] | None = None) -> list[str]:
        if default is None:
            default = []
        return self.data.pop(field, default)

    def at(self, field: str, default: str = '') -> str:
        if field in self:
            for i, val in enumerate(reversed(self.data[field])):
                if val and not any(pval.endswith(val) for pval in self.data[field][: i - 1]):
                    return val

        return default

    def pop_at(self, field: str, idx: int = -1, default: str = '') -> str:
        if field in self.data and idx < len(self.data[field]):
            ret = self.data[field].pop(idx)

            if len(self.data[field]) == 0:
                del self.data[field]
        else:
            ret = default
        return ret

    def add_to_set(self, field: str, value: Any):
        """
        Add a value to the set of values for a given field.
        If the field does not exist, it will be created.
        """
        _val = self.cast_to_list(value, duplicates=False)
        if field not in self.data:
            self.data[field] = _val
        else:
            target = self.data[field]
            target.extend(it.filterfalse(target.__contains__, _val))
