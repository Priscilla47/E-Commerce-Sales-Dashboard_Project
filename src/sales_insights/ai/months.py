"""The complete months of the revenue, shared by the forecast and the statistical facts."""

import numpy as np
import pandas as pd

from sales_insights.analytics.timeseries import revenue_over_time


def complete_months(df: pd.DataFrame) -> tuple[pd.DatetimeIndex, np.ndarray, list[str]]:
    """The revenue of each complete month, and what was left out.

    A month counts when the data reaches its last day; a last month that stops earlier is left
    out (and a note says so), because its small revenue would be read as a fall. Months without
    orders between the first and the last are kept with a revenue of 0.

    Returns the first day of each month, the revenue of each month and the notes.
    """
    series = revenue_over_time(df, "M")
    notes: list[str] = []
    if not series.empty:
        last = df["Date"].dropna().max()
        if last.day < last.days_in_month:
            series = series.iloc[:-1]
            notes.append(
                f"The last month ({last:%Y-%m}) was left out because the data stops on day "
                f"{last.day} of {last.days_in_month}."
            )
    return pd.DatetimeIndex(series["period"]), series["revenue"].to_numpy("float64"), notes
