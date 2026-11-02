"""Narrow a loaded orders table to a period, some countries and some categories.

Pure functions on a loaded orders table (see ``load_orders``). Every interface (the
dashboard, the command line, the AI layer) filters through ``filter_orders`` so that they all
agree on what "between these dates, in these countries" means.
"""

import datetime
from collections.abc import Collection

import pandas as pd

# The columns a user may pick values from.
FILTER_COLUMNS = ("Country", "Category")

DateLike = str | datetime.date | pd.Timestamp


def filter_orders(
    df: pd.DataFrame,
    start: DateLike | None = None,
    end: DateLike | None = None,
    countries: Collection[str] | str | None = None,
    categories: Collection[str] | str | None = None,
) -> pd.DataFrame:
    """The orders of ``df`` that match every filter given, as a new table.

    ``start`` and ``end`` are days, both included: an order made at any time of the ``end`` day
    is kept. ``countries`` and ``categories`` are exact values to keep. For each filter,
    ``None`` means "no filter", while an empty collection means "nothing selected" and keeps no
    row. The filters combine with AND. An order with a missing date never matches a date
    filter, and one with a missing country (or category) never matches a country (or category)
    filter.

    The result has the columns, types and index values of ``df`` (rows are only removed), and
    ``df`` itself is not changed.

    Raises:
        ValueError: a date cannot be read, ``start`` is after ``end``, or the table lacks the
            column a filter needs (or its dates are not dates).
    """
    first = _day(start, "start")
    last = _day(end, "end")
    if first is not None and last is not None and first > last:
        raise ValueError(
            f"The start date {first.date().isoformat()} is after the end date "
            f"{last.date().isoformat()}"
        )

    keep = pd.Series(True, index=df.index)
    if first is not None or last is not None:
        _require(df, "Date")
        dates = df["Date"]
        if not pd.api.types.is_datetime64_any_dtype(dates):
            raise ValueError("The column 'Date' does not hold dates; load the data first")
        if first is not None:
            keep &= dates >= _in_zone(first, dates, "start")
        if last is not None:
            keep &= dates < _in_zone(last, dates, "end") + pd.DateOffset(days=1)

    for column, values in (("Country", countries), ("Category", categories)):
        if values is not None:
            _require(df, column)
            wanted = [values] if isinstance(values, str) else list(values)
            keep &= df[column].isin(wanted)

    return df[keep].copy()


def available_values(df: pd.DataFrame, column: str) -> list[str]:
    """The distinct values of ``Country`` or ``Category`` in ``df``, sorted, without the missing.

    Meant to fill the selectors of an interface; the values can be given back to
    ``filter_orders``.

    Raises:
        ValueError: ``column`` is not ``Country`` or ``Category``, or the table lacks it.
    """
    if column not in FILTER_COLUMNS:
        raise ValueError(
            f"Cannot list the values of {column!r}; choose one of: {', '.join(FILTER_COLUMNS)}"
        )
    _require(df, column)
    return sorted(str(value) for value in df[column].dropna().unique())


def _require(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        raise ValueError(f"The data has no column {column!r}")


def _day(value: DateLike | None, name: str) -> pd.Timestamp | None:
    """The day (midnight) of a date given as text, date, datetime or timestamp."""
    if value is None:
        return None
    try:
        stamp = pd.Timestamp(value)
    except (ValueError, TypeError) as error:
        raise ValueError(f"Cannot read the {name} date {value!r} as a date") from error
    if pd.isna(stamp):
        raise ValueError(f"Cannot read the {name} date {value!r} as a date")
    return stamp.normalize()


def _in_zone(day: pd.Timestamp, dates: pd.Series, name: str) -> pd.Timestamp:
    """``day`` in the time zone of the ``dates`` column (naive for naive dates)."""
    zone = dates.dt.tz
    if zone is None:
        if day.tzinfo is not None:
            raise ValueError(f"The {name} date has a time zone but the dates of the data have none")
        return day
    if day.tzinfo is None:
        return day.tz_localize(zone)
    return day.tz_convert(zone).normalize()
