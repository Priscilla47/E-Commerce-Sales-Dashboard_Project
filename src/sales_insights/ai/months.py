"""The complete months of the revenue, shared by the forecast and the statistical facts."""

import numpy as np
import pandas as pd

from sales_insights.analytics.timeseries import revenue_over_time

LARGEST_REVENUE = 1e100  # beyond this the squares of the errors would overflow a float


def check_scale(values: np.ndarray, doing: str = "forecast") -> None:
    """Refuse revenue so large that squaring it would overflow.

    Raises:
        ValueError: a value is above 1e100 (the message says what could not be done).
    """
    if values.size and not np.abs(values).max() <= LARGEST_REVENUE:
        raise ValueError(
            f"The revenue is too large to {doing}: a value holds more than {LARGEST_REVENUE:.0e}"
        )


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
