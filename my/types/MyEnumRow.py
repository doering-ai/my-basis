############
### HEAD ###
############
### STANDARD
from typing import TypeVar

### EXTERNAL
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

### INTERNAL
from ..types.MyEnum import MyEnum

############
### DATA ###
############
E = TypeVar('E', bound=MyEnum)


############
### BODY ###
############
class MyEnumRow[E: MyEnum](sa.TypeDecorator):
    """SQLAlchemy type for storing MyEnum values as strings.

    Automatically converts between MyEnum instances and their string representations for database
    storage and retrieval.
    """

    impl = sa.String(64)

    def __init__(self, tvar: type[E], *args, **kwargs):
        """Create an SQLAlchemy-ready enum value."""
        super().__init__(*args, **kwargs)
        self.tvar = tvar

    def process_bind_param(self, value: E | None, dialect) -> str | None:
        """Serialize the enum into a simple string.

        Args:
            value: MyEnum instance or None.
            dialect: SQLAlchemy dialect (unused).
        Returns:
            String representation or None.
        """
        if value is None:
            return None
        return value.write()

    def process_result_value(self, value: str | None, dialect) -> E | None:
        """Deserialize a string-encoded enum.

        Args:
            value: String value from database or None.
            dialect: SQLAlchemy dialect (unused).
        Returns:
            MyEnum instance or None.
        """
        if value is None:
            return None
        return self.tvar.read(value)


class MyEnumSetRow[E: MyEnum](sa.TypeDecorator):
    """SQLAlchemy type for storing sets of MyEnum values as PostgreSQL arrays.

    Automatically converts between sets of MyEnum instances and arrays of strings for PostgreSQL
    storage and retrieval.
    """

    impl = psql.ARRAY
    cache_ok = True

    def __init__(self, tvar: type[E], *args, **kwargs):
        """Create an SQLAlchemy-ready enum set value."""
        super().__init__(*args, **kwargs)
        self.tvar = tvar

    def load_dialect_impl(self, dialect):
        """Use PostgreSQL array of strings as the underlying type."""
        return dialect.type_descriptor(psql.ARRAY(sa.String(64)))

    def bind_expression(self, bindvalue):  # type: ignore
        """Ensure proper casting when binding values."""
        return sa.cast(bindvalue, self)

    def process_bind_param(self, value: set[E] | list[E] | None, dialect) -> list[str] | None:
        """Serialize the collection into a list of strings.

        Args:
            value: Set or list of MyEnum instances, or None.
            dialect: SQLAlchemy dialect (unused).
        Returns:
            List of string representations or None.
        """
        if value is None:
            return None
        return [item.write() for item in value]

    def process_result_value(self, value: list[str] | None, dialect) -> set[E] | None:
        """Deserialize a list of string-encoded enums.

        Args:
            value: List of strings from database or None.
            dialect: SQLAlchemy dialect (unused).
        Returns:
            Set of MyEnum instances or None.
        """
        if value is None:
            return None
        return {self.tvar.read(item) for item in value}
