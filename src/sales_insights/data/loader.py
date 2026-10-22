"""Load an orders CSV file into a typed DataFrame."""

import io
from pathlib import Path

import pandas as pd

from sales_insights.data.schema import (
    COLUMN_TYPES,
    COLUMNS,
    REVENUE_COLUMN,
    SchemaError,
    require_columns,
)
from sales_insights.data.storage import Storage


def load_orders(source: str | Path | Storage, name: str | None = None) -> pd.DataFrame:
    """Read an orders CSV file, from a path or from a storage.

    ``load_orders("data/orders.csv")`` reads a file; ``load_orders(storage, "orders.csv")``
    reads the named file of a Storage.

    The result has the schema columns in schema order, then any extra columns of the file,
    then a computed ``Revenue`` column (``UnitPrice * Quantity``). Empty cells are kept as
    missing values; checking them is the job of the validation step.

    Raises:
        FileNotFoundError: the file does not exist.
        SchemaError: the file is empty, lacks expected columns, or holds a value that cannot
            be read as its column's type.
        TypeError: a storage is given without a name, or a name without a storage.
    """
    if isinstance(source, Storage):
        if name is None:
            raise TypeError("A file name is required when loading from a storage")
        return _read_csv(io.BytesIO(source.read(name)))
    if name is not None:
        raise TypeError("A file name can only be used together with a storage")
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"Orders file not found: {path}")
    return _read_csv(path)


def _read_csv(source: Path | io.BytesIO) -> pd.DataFrame:
    try:
        # Read everything as text first: "NA" is a real country code, not a missing value.
        raw = pd.read_csv(source, dtype=str, keep_default_na=False, na_values=[""])
    except pd.errors.EmptyDataError as error:
        raise SchemaError("The orders file is empty: it has no header row") from error
    return _build_orders(raw)


def _build_orders(raw: pd.DataFrame) -> pd.DataFrame:
    require_columns(raw.columns)
    extras = [c for c in raw.columns if c not in COLUMNS and c != REVENUE_COLUMN]
    orders = raw[[*COLUMNS, *extras]].copy()

    for column, kind in COLUMN_TYPES.items():
        if kind == "date":
            orders[column] = _to_date(orders[column], column)
        elif kind == "float":
            orders[column] = _to_float(orders[column], column)
        elif kind == "integer":
            orders[column] = _to_integer(orders[column], column)

    orders[REVENUE_COLUMN] = (orders["UnitPrice"] * orders["Quantity"]).astype("float64")
    return orders


def _to_date(values: pd.Series, column: str) -> pd.Series:
    parsed = pd.to_datetime(values, format="ISO8601", errors="coerce")
    _raise_on_invalid(values, values.notna() & parsed.isna(), column, "a date (YYYY-MM-DD)")
    return parsed


def _to_float(values: pd.Series, column: str) -> pd.Series:
    numbers = pd.to_numeric(values, errors="coerce")
    _raise_on_invalid(values, values.notna() & numbers.isna(), column, "a number")
    return numbers.astype("float64")


def _to_integer(values: pd.Series, column: str) -> pd.Series:
    numbers = pd.to_numeric(values, errors="coerce")
    invalid = values.notna() & (numbers.isna() | (numbers % 1 != 0))
    _raise_on_invalid(values, invalid, column, "a whole number")
    # Plain integers when nothing is missing, so downstream numpy code keeps working.
    return numbers.astype("Int64" if numbers.isna().any() else "int64")


def _raise_on_invalid(values: pd.Series, invalid: pd.Series, column: str, expected: str) -> None:
    if not invalid.any():
        return
    first = invalid.idxmax()
    count = int(invalid.sum())
    more = f" (and {count - 1} more)" if count > 1 else ""
    raise SchemaError(
        f"Column '{column}' must hold {expected}; line {first + 2} has {values[first]!r}{more}"
    )
