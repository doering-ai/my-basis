import typing
from typing import TypeVar
from .Typist import typist


json_data = '{"data": "here"}'

_dict = typist.from_json(json_data)
typing.assert_type(_dict, dict)

second = typist.from_json(json_data, list[dict])
typing.assert_type(second, list[dict])

error: int = "555555"


FileData = str | int | list | dict
F = TypeVar("F", bound=FileData, default=dict)
# Ft = TypeVar("Ft", bound=type[F], default=type[dict])
# _Explicit = TypeVar(
#     "_Explicit",
#     bound=type[dict] | type[list] | type[str] | type[int],
#     default=type[dict],
# )

# T = TypeVar("T")

# type Alias[T, DefaultT = int] = tuple[T, DefaultT]


def example(
    data: str,
    tvar: type[F] = type[dict],  # ty:ignore[invalid-parameter-default]
) -> F:
    if issubclass(tvar, dict):
        return tvar({})
    elif tvar is list:
        return tvar([])
    elif tvar is str:
        return ""
    elif tvar is int:
        return 0

    raise TypeError


result_default: dict = example("test str")
result_explicit: list = example("test str", list)
