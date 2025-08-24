############
### HEAD ###
############
# Standard imports
from typing import TypeVar, Generic, Hashable
import more_itertools as mi

# External imports
import pydantic as pyd

# Internal imports

############
### BODY ###
############
# Specific type helpers
Key = TypeVar('Key', bound=Hashable)
Value = TypeVar('Value')


class Cache(pyd.BaseModel, Generic[Key, Value]):
    data: dict[Key, Value] = {}
    maxsize: int = pyd.Field(default=2**12, gt=0)  # 4096
    bucket_size: int = pyd.Field(default=2**8, gt=0)  # 256

    def __getitem__(self, key: Key) -> Value | None:
        if (ret := self.data.pop(key, None)) is not None:
            self.data[key] = ret  # move it to the bottom of the map
        return None

    def __setitem__(self, key: Key, value: Value) -> None:
        if key not in self.data and len(self.data) >= self.maxsize:
            self.prune(self.bucket_size)
        self.data[key] = value

    def __len__(self) -> int:
        return len(self.data)

    def __contains__(self, key: Key) -> bool:
        return key in self.data

    def items(self) -> list[tuple[Key, Value]]:
        return list(self.data.items())

    def keys(self) -> list[Key]:
        return list(self.data.keys())

    def values(self) -> list[Value]:
        return list(self.data.values())

    def prune(self, n: int) -> None:
        for key in mi.take(n, self.data.keys()):
            del self.data[key]
