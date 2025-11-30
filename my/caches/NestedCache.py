############
### HEAD ###
############
### STANDARD
from typing import Generic, Hashable, Iterator
import functools as ft
import more_itertools as mi

### EXTERNAL
import pydantic as pyd

### INTERNAL
from ..infra import Keys, Value


############
### BODY ###
############
class NestedCache(pyd.BaseModel, Generic[Keys, Value]):
    signature: tuple

    children: dict[Hashable, 'NestedCache'] = {}
    data: dict = {}
    size: int = 0

    max_size: int = pyd.Field(default=2**12, gt=0)  # 4096
    bucket_size: int = pyd.Field(default=2**8, gt=0)  # 256

    @ft.cached_property
    def depth(self) -> int:
        return len(self.signature)

    def __getitem__(self, keys: list | tuple) -> Value | None:
        if len(keys) != self.depth:
            return None

        key, *keys = keys
        if self.depth == 1:
            val = self.data.pop(key, None)
            if val is None:
                return None
            self.data[key] = val
            return val
        else:
            val = self.children.pop(key, None)
            if val is None:
                return None

            # Add the value back to the top of the dict
            self.children[key] = val
            return val[keys]

    def set(self, keys: list | tuple, value: Value) -> int:
        if len(keys) != self.depth:
            raise ValueError('Keys must match the depth of the cache')

        key, *keys = keys
        if self.depth == 1:
            count = 1 if key not in self.data else 0
            self.data[key] = value
            self.size += count
            return count
        else:
            if key not in self.children:
                self.children[key] = NestedCache(signature=self.signature[1:])
            ret = self.children[key].set(keys, value)
            self.size += ret
            return ret

    def __setitem__(self, keys: list | tuple, value: Value) -> None:
        self.set(keys, value)
        if self.size > self.max_size:
            self.prune(self.bucket_size)

    def delete(self, keys: list | tuple) -> int:
        if len(keys) != self.depth:
            return 0

        key, *keys = keys
        if self.depth == 1:
            if key in self.data:
                del self.data[key]
                self.size -= 1
                return 1
        else:
            if key in self.children:
                ret = self.children[key].delete(keys)
                if ret > 0:
                    if not self.children[key].size:
                        del self.children[key]
                    self.size -= ret
                    return ret
        return 0

    def __len__(self) -> int:
        return self.size

    def __contains__(self, keys: list | tuple) -> bool:
        return self[keys] is not None

    def __bool__(self) -> bool:
        return self.size > 0

    def items(self) -> Iterator[tuple[Keys, Value]]:
        if self.depth == 1:
            for key, val in self.data.items():
                yield (key,), val  # type: ignore
        else:
            for key, child in self.children.items():
                for keys, val in child.items():
                    yield (key, *keys), val  # type: ignore

    def keys(self) -> Iterator[Keys]:
        yield from (key for key, _ in self.items())

    def values(self) -> Iterator[Value]:
        yield from (val for _, val in self.items())

    def prune(self, n: int) -> int:
        if self.depth == 1:
            orig = len(self.data)
            for key in mi.take(n, self.data.keys()):
                del self.data[key]
            count = orig - len(self.data)

        else:
            count = 0
            for _, child in self.children.items():
                if not child:
                    continue
                target = round((child.size / self.size) * n)
                count += child.prune(target)

        self.size -= count
        return count
