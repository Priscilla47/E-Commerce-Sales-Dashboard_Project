"""Turn what the user picked in the sidebar into the arguments of ``filter_orders``."""

import datetime
from collections.abc import Collection

import pandas as pd


def as_filter(selected: Collection[str], available: Collection[str]) -> list[str] | None:
    """The values to filter on, or None when every available value is selected.

    Selecting everything must not filter at all: an order whose country is missing belongs to
    no value of the selector, and would otherwise disappear from the figures. Selecting
    nothing is a real filter (it keeps no order).
    """
    if set(selected) == set(available):
        return None
    return list(selected)


def period_bounds(df: pd.DataFrame) -> tuple[datetime.date, datetime.date] | None:
    """The first and the last day of the orders, or None when no order has a date."""
    dates = df["Date"].dropna()
    if dates.empty:
        return None
    return dates.min().date(), dates.max().date()
