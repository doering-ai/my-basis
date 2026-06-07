############
### HEAD ###
############
### STANDARD
from typing import IO, Any
from collections.abc import (
    Callable,
    Iterable,
    AsyncIterable,
    ItemsView,
    Mapping,
    Set,
)
from collections import deque
from io import StringIO, BytesIO
from types import FunctionType, BuiltinFunctionType
from datetime import date, time, datetime, timedelta
from enum import Enum, Flag

### EXTERNAL
from pydantic import BaseModel

### INTERNAL
from ..infra.types import (
    Object,
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
    Dataclass,
)
from ..utils import ut

############
### BODY ###
############
