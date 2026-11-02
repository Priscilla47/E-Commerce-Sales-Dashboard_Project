"""Chart builders: a table in, a Plotly figure out.

Each function asks ``analytics`` for the numbers and only decides how they are drawn. None of
them displays anything; the page does that with one call. A table with nothing to draw gives
``None`` instead of an empty frame, so that the page can say so. The data has no currency
column, so no title or axis names one.
"""

import pandas as pd
import plotly.graph_objects as go

from sales_insights.analytics.breakdowns import revenue_by
from sales_insights.analytics.products import top_products, unique_products
from sales_insights.analytics.timeseries import revenue_over_time
from sales_insights.dashboard.theme import PALETTE

# What the page says in place of a chart that has nothing to draw.
NOTHING_TO_DRAW = "No orders match these filters"
PERIOD_NAMES = {"D": "day", "M": "month", "Y": "year"}
# How to label the time axis: one tick for each month or year, not for arbitrary dates.
TICKS = {"M": {"tickformat": "%b %Y", "dtick": "M1"}, "Y": {"tickformat": "%Y", "dtick": "M12"}}
BREAKDOWN_COLUMNS = ("Country", "Category")


def _layout(figure: go.Figure, title: str, x_title: str, y_title: str) -> go.Figure:
    figure.update_layout(
        title={"text": title},
        xaxis={"title": {"text": x_title}},
        yaxis={"title": {"text": y_title}},
        showlegend=False,
        margin={"t": 60, "r": 20, "b": 40, "l": 20},
    )
    return figure


def revenue_over_time_chart(df: pd.DataFrame, freq: str = "M") -> go.Figure | None:
    """A line of the revenue for each day (``"D"``), month (``"M"``) or year (``"Y"``).

    Periods without orders are drawn at 0. Hovering a point also shows its number of orders.
    ``None`` when no order has a date.

    Raises:
        ValueError: ``freq`` is not ``"D"``, ``"M"`` or ``"Y"``.
    """
    series = revenue_over_time(df, freq)
    if series.empty:
        return None
    name = PERIOD_NAMES[freq]
    figure = go.Figure(
        go.Scatter(
            x=series["period"],
            y=series["revenue"],
            customdata=series[["orders"]].to_numpy(),
            mode="lines+markers",
            line={"color": PALETTE[0]},
            marker={"color": PALETTE[0]},
            hovertemplate="%{x}<br>Revenue: %{y}<br>Orders: %{customdata[0]}<extra></extra>",
        )
    )
    figure.update_xaxes(**TICKS.get(freq, {}))
    return _layout(figure, f"Revenue by {name}", name.capitalize(), "Revenue")


def revenue_by_chart(df: pd.DataFrame, column: str) -> go.Figure | None:
    """Bars of the revenue for each ``Country`` or ``Category``, the highest first.

    ``None`` when the table has no order.

    Raises:
        ValueError: ``column`` is not ``"Country"`` or ``"Category"``.
    """
    if column not in BREAKDOWN_COLUMNS:
        allowed = " or ".join(BREAKDOWN_COLUMNS)
        raise ValueError(f"Cannot draw revenue by {column!r}; choose {allowed}")
    breakdown = revenue_by(df, column)
    if breakdown.empty:
        return None
    names = [str(name) for name in breakdown[column]]
    figure = go.Figure(go.Bar(x=names, y=breakdown["revenue"], marker={"color": PALETTE[0]}))
    figure.update_xaxes(categoryorder="array", categoryarray=names)
    return _layout(figure, f"Revenue by {column.lower()}", column, "Revenue")


def top_products_chart(df: pd.DataFrame, n: int) -> go.Figure | None:
    """Bars of the units sold for the ``n`` best-selling products, the highest first.

    An ``n`` larger than the number of products shows all of them. ``None`` when there is
    nothing to show (no product, or ``n`` is 0).

    Raises:
        TypeError: ``n`` is not a whole number.
        ValueError: ``n`` is negative.
    """
    if isinstance(n, int) and not isinstance(n, bool):
        n = min(n, len(unique_products(df)))
    best = top_products(df, n)
    names = [str(name) for name in best["Product"]]
    shown = len(names)
    if not shown:
        return None
    figure = go.Figure(go.Bar(x=names, y=best["units"], marker={"color": PALETTE[1]}))
    figure.update_xaxes(categoryorder="array", categoryarray=names)
    noun = "product" if shown == 1 else "products"
    return _layout(figure, f"Top {shown} {noun} by units sold", "Product", "Units sold")
