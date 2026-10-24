"""Revenue over time, ready for charts and forecasts.

A pure function on a loaded orders table (see ``load_orders``).
"""

import pandas as pd

# Accepted frequency -> the pandas alias of a period that starts on its first day.
FREQUENCIES = {"D": "D", "M": "MS", "Y": "YS"}

COLUMNS = ["period", "revenue", "orders"]


def revenue_over_time(df: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
    """Revenue and number of orders for each day (``"D"``), month (``"M"``) or year (``"Y"``).

    The result has the columns ``[period, revenue, orders]``, sorted by period. ``period`` is
    the first day of the period as a ``Timestamp``. Periods without orders between the first
    and the last one are kept with a revenue of 0 and 0 orders, so there are no gaps.
    ``orders`` counts distinct ``OrderID`` values. Lines without a date are left out.

    Raises:
        ValueError: ``freq`` is not ``"D"``, ``"M"`` or ``"Y"``.
    """
    if not isinstance(freq, str) or freq not in FREQUENCIES:
        raise ValueError(f"freq must be one of 'D', 'M' or 'Y', not {freq!r}")

    dated = df.dropna(subset=["Date"])
    if dated.empty:
        return pd.DataFrame(
            {
                "period": pd.Series(dtype="datetime64[ns]"),
                "revenue": pd.Series(dtype="float64"),
                "orders": pd.Series(dtype="int64"),
            }
        )

    result = (
        dated.set_index("Date")
        .resample(FREQUENCIES[freq])
        .agg(revenue=("Revenue", "sum"), orders=("OrderID", "nunique"))
        .reset_index()
        .rename(columns={"Date": "period"})
    )
    result["revenue"] = result["revenue"].astype("float64")
    result["orders"] = result["orders"].astype("int64")
    return result[COLUMNS]
