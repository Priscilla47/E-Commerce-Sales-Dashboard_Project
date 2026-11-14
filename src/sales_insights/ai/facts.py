"""Statistical facts about the sales: what is true, as numbers, with no sentence.

The facts are the only thing a language model is later allowed to talk about (see
``insights``). Every number comes from an ``analytics`` function or from a simple formula on its
result, and nothing here needs a model, reads a file, prints or rounds.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from sales_insights.ai.months import complete_months
from sales_insights.analytics.breakdowns import revenue_by
from sales_insights.analytics.products import top_products
from sales_insights.analytics.revenue import order_count

FLAT_BELOW = 0.01  # a slope under 1% of the mean revenue a month is no trend
ANOMALY_Z = 2.0  # a month further than 2 standard deviations from the mean
MIN_MONTHS_FOR_ANOMALIES = 6
SHARE_CHANGE_POINTS = 5.0  # a share that moved by at least 5 points
SHARE_COLUMNS = ("Country", "Category")
_EDGE = 9  # decimals kept when comparing with a limit, so that 2.0000000001 is 2
_NOISE = 1e-9  # a spread under this share of the largest month is rounding, not a difference


@dataclass(frozen=True)
class Trend:
    """``direction`` is ``up``, ``down`` or ``flat``; the slope is in revenue per month."""

    direction: str
    slope_per_month: float


@dataclass(frozen=True)
class Month:
    period: str  # "YYYY-MM"
    revenue: float


@dataclass(frozen=True)
class Anomaly:
    period: str
    revenue: float
    z_score: float


@dataclass(frozen=True)
class ShareChange:
    """The share of the revenue of a country or category in the two halves of the period."""

    column: str
    value: str
    first_share: float
    second_share: float
    change_points: float  # second minus first, in percentage points


@dataclass(frozen=True)
class TopProduct:
    name: str
    units: int


@dataclass(frozen=True)
class Facts:
    """What is true about the sales. A field is None, or empty, when there is nothing to say."""

    orders: int
    period_start: str | None
    period_end: str | None
    trend: Trend | None
    best_month: Month | None
    worst_month: Month | None
    anomalies: tuple[Anomaly, ...]
    anomalies_note: str | None
    share_changes: tuple[ShareChange, ...]
    top_product: TopProduct | None
    notes: tuple[str, ...]

    def as_dict(self) -> dict:
        """The facts as plain JSON-ready values (dicts, lists, text, numbers and None)."""
        period = None
        if self.period_start is not None:
            period = {"start": self.period_start, "end": self.period_end}

        def one(item):
            return (
                None if item is None else {k: getattr(item, k) for k in item.__dataclass_fields__}
            )

        return {
            "orders": self.orders,
            "period": period,
            "trend": one(self.trend),
            "best_month": one(self.best_month),
            "worst_month": one(self.worst_month),
            "anomalies": [one(a) for a in self.anomalies],
            "anomalies_note": self.anomalies_note,
            "share_changes": [one(c) for c in self.share_changes],
            "top_product": one(self.top_product),
            "notes": list(self.notes),
        }


def _slope(values: np.ndarray) -> float:
    """Least-squares slope of ``values`` against 0, 1, 2, ... (revenue per month)."""
    x = np.arange(len(values), dtype="float64")
    centred = x - x.mean()
    return float(np.sum(centred * (values - values.mean())) / np.sum(centred**2))


def _trend(values: np.ndarray) -> Trend:
    slope = _slope(values)
    mean = float(np.mean(np.abs(values)))
    relative = abs(slope) / mean if mean else 0.0
    if round(relative, _EDGE) < FLAT_BELOW:
        direction = "flat"
    else:
        direction = "up" if slope > 0 else "down"
    return Trend(direction, slope)


def _anomalies(periods: pd.DatetimeIndex, values: np.ndarray) -> tuple[Anomaly, ...]:
    std = float(np.std(values))
    # Months equal to the cent can differ by a rounding error once summed (4907.85 against
    # 4907.849999999999); such a spread is no spread, or every flat series would have anomalies.
    if std <= _NOISE * max(float(np.max(np.abs(values))), 1.0):
        return ()
    z = (values - values.mean()) / std
    return tuple(
        Anomaly(f"{period:%Y-%m}", float(value), float(score))
        for period, value, score in zip(periods, values, z, strict=True)
        if round(abs(float(score)), _EDGE) > ANOMALY_Z
    )


def _share_changes(df: pd.DataFrame) -> tuple[tuple[ShareChange, ...], str | None]:
    """The share changes, and a note when there are no two halves to compare."""
    dates = df["Date"].dropna()
    if dates.empty or dates.min() == dates.max():
        return (), "Share changes need orders on at least two different days."
    middle = dates.min() + (dates.max() - dates.min()) / 2
    first, second = df[df["Date"] < middle], df[df["Date"] >= middle]
    found: list[ShareChange] = []
    for column in (c for c in SHARE_COLUMNS if c in df.columns):
        before = revenue_by(first, column).set_index(column)["share"]
        after = revenue_by(second, column).set_index(column)["share"]
        for value in before.index.union(after.index):
            if pd.isna(value):
                continue
            a, b = float(before.get(value, 0.0)), float(after.get(value, 0.0))
            points = (b - a) * 100
            if round(abs(points), _EDGE) >= SHARE_CHANGE_POINTS:
                found.append(ShareChange(column, str(value), a, b, points))
    ordered = sorted(found, key=lambda c: (-abs(c.change_points), c.column, c.value))
    return tuple(ordered), None


def compute_facts(df: pd.DataFrame) -> Facts:
    """The facts about a loaded orders table (what ``load_orders`` returns).

    Months are the complete months (a last month that the data does not finish is left out and
    a note says so; a first month that starts after its day 1 is kept, with a note). Anomalies
    are months more than 2 standard deviations (of the population of months) from the mean, and
    need 6 months. Share changes compare the first and the second half of the period, by date,
    for the columns of ``SHARE_COLUMNS`` that the table has.
    """
    periods, values, notes = complete_months(df)
    dates = df["Date"].dropna()
    best = worst = trend = None
    if len(values):
        best = Month(f"{periods[int(np.argmax(values))]:%Y-%m}", float(values.max()))
        worst = Month(f"{periods[int(np.argmin(values))]:%Y-%m}", float(values.min()))
        first = dates.min()
        if first.day > 1:
            notes.append(
                f"The first month ({first:%Y-%m}) starts on day {first.day}: the data may "
                "not hold all of it, so its revenue can be low for that reason only."
            )
    if len(values) >= 2:
        trend = _trend(values)
    elif not dates.empty:
        notes.append(f"A trend needs at least 2 complete months, found {len(values)}.")

    anomalies: tuple[Anomaly, ...] = ()
    anomalies_note = None
    if len(values) >= MIN_MONTHS_FOR_ANOMALIES:
        anomalies = _anomalies(periods, values)
    elif not dates.empty:
        anomalies_note = (
            f"Anomalies need at least {MIN_MONTHS_FOR_ANOMALIES} complete months, "
            f"found {len(values)}."
        )

    share_changes: tuple[ShareChange, ...] = ()
    if not df.empty:
        share_changes, share_note = _share_changes(df)
        if share_note:
            notes.append(share_note)

    top = None
    if "Product" in df.columns and df["Product"].notna().any():
        ranking = top_products(df, 1)
        if len(ranking):
            top = TopProduct(str(ranking["Product"].iloc[0]), int(ranking["units"].iloc[0]))

    return Facts(
        orders=order_count(df),
        period_start=None if dates.empty else f"{dates.min():%Y-%m-%d}",
        period_end=None if dates.empty else f"{dates.max():%Y-%m-%d}",
        trend=trend,
        best_month=best,
        worst_month=worst,
        anomalies=anomalies,
        anomalies_note=anomalies_note,
        share_changes=share_changes,
        top_product=top,
        notes=tuple(notes),
    )
