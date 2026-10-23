"""Load an orders CSV file into a typed DataFrame."""

import re
from pathlib import Path

import numpy as np
import pandas as pd

from sales_insights.data.schema import (
    COLUMN_TYPES,
    COLUMNS,
    REVENUE_COLUMN,
    SchemaError,
    require_columns,
)


def load_orders(path: str | Path) -> pd.DataFrame:
    """Read an orders CSV file.

    The result has the schema columns in schema order, then any extra columns of the file,
    then a computed ``Revenue`` column (``UnitPrice * Quantity``). Empty cells are kept as
    missing values; checking them is the job of the validation step.

    Raises:
        FileNotFoundError: the file does not exist.
        SchemaError: the file is empty, lacks expected columns, or holds a value that cannot
            be read as its column's type.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Orders file not found: {path}")
    try:
        # Read everything as text first: "NA" is a real country code, not a missing value.
        raw = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    except pd.errors.EmptyDataError as error:
        raise SchemaError("The orders file is empty: it has no header row") from error
    except pd.errors.ParserError as error:
        detail = str(error).removeprefix("Error tokenizing data. C error: ").strip()
        raise SchemaError(f"The orders file is not valid CSV: {detail}") from error
    return _build_orders(raw)


def _build_orders(raw: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw.index, pd.RangeIndex):
        # pandas makes the first column the row index when every row has one value too many.
        raise SchemaError(
            "The orders file is not valid CSV: its rows have more values than the header"
        )
    _reject_duplicate_columns(raw.columns)
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


def _reject_duplicate_columns(columns: pd.Index) -> None:
    # pandas renames a repeated header "Quantity" to "Quantity.1" instead of failing.
    repeated = []
    for name in columns:
        match = re.fullmatch(r"(.+)\.\d+", name)
        if match and match.group(1) in columns and match.group(1) not in repeated:
            repeated.append(match.group(1))
    if repeated:
        raise SchemaError("Duplicate column(s) in the header: " + ", ".join(repeated))


def _to_date(values: pd.Series, column: str) -> pd.Series:
    parsed = pd.to_datetime(values, format="ISO8601", errors="coerce")
    _raise_on_invalid(values, values.notna() & parsed.isna(), column, "a date (YYYY-MM-DD)")
    return parsed


def _to_float(values: pd.Series, column: str) -> pd.Series:
    numbers = pd.to_numeric(values, errors="coerce").astype("float64")
    # inf and nan are readable as numbers but make no sense as prices.
    _raise_on_invalid(values, values.notna() & ~np.isfinite(numbers), column, "a finite number")
    return numbers


def _to_integer(values: pd.Series, column: str) -> pd.Series:
    numbers = pd.to_numeric(values, errors="coerce")
    invalid = values.notna() & (numbers.isna() | (numbers % 1 != 0))
    _raise_on_invalid(values, invalid, column, "a whole number")
    # Plain integers when nothing is missing, so downstream numpy code keeps working.
    return numbers.astype("Int64" if numbers.isna().any() else "int64")


def _raise_on_invalid(values: pd.Series, invalid: pd.Series, column: str, expected: str) -> None:
    if not invalid.any():
        return
    first = int(np.argmax(invalid.to_numpy()))
    count = int(invalid.sum())
    more = f" (and {count - 1} more)" if count > 1 else ""
    raise SchemaError(
        f"Column '{column}' must hold {expected}; line {first + 2} has {values.iloc[first]!r}{more}"
    )
