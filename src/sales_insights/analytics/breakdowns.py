"""Revenue broken down by a text column, such as the country or the product category.

Pure functions on a loaded orders table (see ``load_orders``). A line whose label is missing
(an empty country, for example) forms a group of its own, so the groups always add up to the
total revenue.
"""

import pandas as pd

from sales_insights.analytics.revenue import total_revenue
from sales_insights.data.schema import COLUMN_TYPES

# The columns that hold labels, which makes them usable as a breakdown.
GROUP_COLUMNS = tuple(name for name, kind in COLUMN_TYPES.items() if kind == "text")


def revenue_by(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Revenue, number of orders and share of the total revenue for each value of ``column``.

    The result has the columns ``[column, "revenue", "orders", "share"]``, sorted by revenue
    from the highest, with ties ordered by name. ``orders`` counts distinct ``OrderID`` values;
    ``share`` is the revenue divided by the total revenue (0 to 1, and 0.0 when the total is 0).

    Raises:
        ValueError: ``column`` is not one of the text columns, or the table has no such column.
    """
    if column not in GROUP_COLUMNS:
        allowed = ", ".join(GROUP_COLUMNS)
        raise ValueError(f"Cannot break revenue down by {column!r}; choose one of: {allowed}")
    if column not in df.columns:
        raise ValueError(f"The data has no column {column!r}")

    result = (
        df.groupby(column, dropna=False, observed=True)
        .agg(revenue=("Revenue", "sum"), orders=("OrderID", "nunique"))
        .reset_index()
    )
    result["revenue"] = result["revenue"].astype("float64")
    result["orders"] = result["orders"].astype("int64")

    total = total_revenue(df)
    result["share"] = result["revenue"] / total if total else 0.0
    result["share"] = result["share"].astype("float64")

    result = result.sort_values(["revenue", column], ascending=[False, True], kind="stable")
    return result.reset_index(drop=True)


def revenue_by_country(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue, orders and share for each country (see ``revenue_by``)."""
    return revenue_by(df, "Country")


def revenue_by_category(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue, orders and share for each product category (see ``revenue_by``)."""
    return revenue_by(df, "Category")
