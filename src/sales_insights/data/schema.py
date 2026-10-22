"""Expected structure of an orders file."""

from collections.abc import Iterable


class SchemaError(ValueError):
    """The orders data does not match the expected schema."""


# Column name -> kind of value, in the order the columns appear in a loaded table.
COLUMN_TYPES = {
    "OrderID": "integer",
    "Date": "date",
    "Product": "text",
    "Category": "text",
    "UnitPrice": "float",
    "Quantity": "integer",
    "CustomerID": "text",
    "Country": "text",
}
COLUMNS = tuple(COLUMN_TYPES)

# Computed from UnitPrice and Quantity when the data is loaded.
REVENUE_COLUMN = "Revenue"


def missing_columns(columns: Iterable[str]) -> list[str]:
    """Return the expected columns that are absent, in schema order."""
    present = set(columns)
    return [column for column in COLUMNS if column not in present]


def require_columns(columns: Iterable[str]) -> None:
    """Raise SchemaError, naming every missing column, if any expected column is absent."""
    missing = missing_columns(columns)
    if missing:
        raise SchemaError("Missing required column(s): " + ", ".join(missing))
