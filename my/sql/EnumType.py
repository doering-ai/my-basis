############
### HEAD ###
############
### STANDARD
from typing import TypeVar, Generic, Type

### EXTERNAL
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

### INTERNAL
from ..base.MyEnum import MyEnum

############
### DATA ###
############
E = TypeVar('E', bound=MyEnum)


############
### BODY ###
############
class EnumType(sa.TypeDecorator, Generic[E]):
    impl = sa.String(64)

    def __init__(self, tvar: Type[E], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tvar = tvar

    def process_bind_param(self, value: E | None, dialect) -> str | None:
        if value is None:
            return None
        return value.write()

    def process_result_value(self, value: str | None, dialect) -> E | None:
        if value is None:
            return None
        return self.tvar.read(value)


class EnumSetType(sa.TypeDecorator, Generic[E]):
    impl = psql.ARRAY
    cache_ok = True

    def __init__(self, tvar: Type[E], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tvar = tvar

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(psql.ARRAY(sa.String(64)))

    def bind_expression(self, bindvalue):
        """Ensure proper casting when binding values."""
        return sa.cast(bindvalue, self)

    def process_bind_param(self, value: set[E] | list[E] | None, dialect) -> list[str] | None:
        if value is None:
            return None
        return [item.write() for item in value]

    def process_result_value(self, value: list[str] | None, dialect) -> set[E] | None:
        if value is None:
            return None
        return {self.tvar.read(item) for item in value}
