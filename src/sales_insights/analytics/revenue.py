"""Revenue building blocks on a loaded orders table.

All functions are pure: they read the table they are given (as returned by ``load_orders``,
with its computed ``Revenue`` column) and return plain Python numbers. Nothing is rounded
here; round when you display a value.

Cells that are missing (an empty quantity, for example) are skipped by the sums, not
propagated. Run the validation step first if you need to know about them.
"""

import pandas as pd


def total_revenue(df: pd.DataFrame) -> float:
    """The sum of ``Revenue`` (unit price x quantity) over every line; 0.0 for no lines."""
    return float(df["Revenue"].sum())


def order_count(df: pd.DataFrame) -> int:
    """The number of distinct ``OrderID`` values. Several lines of one order count once."""
    return int(df["OrderID"].nunique())


def average_order_value(df: pd.DataFrame) -> float:
    """Total revenue divided by the number of orders; 0.0 when there are no orders."""
    orders = order_count(df)
    if orders == 0:
        return 0.0
    return total_revenue(df) / orders


def units_sold(df: pd.DataFrame) -> int:
    """The sum of ``Quantity`` over every line; 0 for no lines."""
    return int(df["Quantity"].sum())
