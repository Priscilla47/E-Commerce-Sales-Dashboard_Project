"""Chart builders: a table in, a Plotly figure out.

Each function asks ``analytics`` for the numbers and only decides how they are drawn. None of
them displays anything; the page does that with one call. A table with nothing to draw gives
``None`` instead of an empty frame, so that the page can say so. The data has no currency
column, so no title or axis names one.
"""

import html

import pandas as pd
import plotly.graph_objects as go

from sales_insights.analytics.breakdowns import revenue_by
from sales_insights.analytics.products import top_products, unique_products
from sales_insights.analytics.timeseries import revenue_over_time
from sales_insights.dashboard.theme import PALETTE, with_alpha

# What the page says in place of a chart that has nothing to draw.
NOTHING_TO_DRAW = "No orders match these filters"
PERIOD_NAMES = {"D": "day", "M": "month", "Y": "year"}
# How to label the time axis: one tick for a month or a year, not for arbitrary dates.
TICKS = {"M": {"tickformat": "%b %Y"}, "Y": {"tickformat": "%Y", "dtick": "M12"}}


def month_dtick(months: int) -> str:
    """The distance between two labels of a month axis, so that the labels never crowd."""
    for limit, step in ((12, 1), (36, 3), (72, 6)):
        if months <= limit:
            return f"M{step}"
    return "M12"


BREAKDOWN_COLUMNS = ("Country", "Category")
FORECAST_COLUMNS = ("period", "forecast", "lower", "upper")


def _label(name: object) -> str:
    """A name from the data as Plotly must receive it: Plotly reads a few HTML tags and entities
    in labels, so ``<b>x</b>`` or ``&amp;`` in a product name would be shown changed."""
    return html.escape(str(name), quote=False)


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
    if freq == "M":
        figure.update_xaxes(dtick=month_dtick(len(series)))
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
    names = [_label(name) for name in breakdown[column]]
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
    names = [_label(name) for name in best["Product"]]
    shown = len(names)
    if not shown:
        return None
    figure = go.Figure(go.Bar(x=names, y=best["units"], marker={"color": PALETTE[1]}))
    figure.update_xaxes(categoryorder="array", categoryarray=names)
    noun = "product" if shown == 1 else "products"
    return _layout(figure, f"Top {shown} {noun} by units sold", "Product", "Units sold")


def forecast_chart(history: pd.DataFrame, forecast: pd.DataFrame) -> go.Figure | None:
    """The monthly revenue so far, the forecast, and the band between its limits.

    ``history`` has the columns ``period`` and ``revenue`` and ``forecast`` has ``period``,
    ``forecast``, ``lower`` and ``upper`` (as ``forecast_with_error`` returns them). ``None`` when
    there is no forecast to draw.

    Raises:
        ValueError: a table does not have the columns above.
    """
    for table, columns in ((history, ("period", "revenue")), (forecast, FORECAST_COLUMNS)):
        missing = [name for name in columns if name not in table.columns]
        if missing:
            raise ValueError(f"The table has no column {', '.join(missing)}")
    if forecast.empty:
        return None
    periods = forecast["period"]
    figure = go.Figure(
        [
            go.Scatter(
                x=periods,
                y=forecast["upper"],
                mode="lines",
                line={"width": 0, "color": PALETTE[1]},
                showlegend=False,
                hoverinfo="skip",
            ),
            go.Scatter(
                x=periods,
                y=forecast["lower"],
                name="95% interval",
                mode="lines",
                line={"width": 0, "color": PALETTE[1]},
                fill="tonexty",
                fillcolor=with_alpha(PALETTE[1], 0.2),
                hoverinfo="skip",
            ),
            go.Scatter(
                x=history["period"],
                y=history["revenue"],
                name="History",
                mode="lines+markers",
                line={"color": PALETTE[0]},
                marker={"color": PALETTE[0]},
            ),
            go.Scatter(
                x=periods,
                y=forecast["forecast"],
                name="Forecast",
                mode="lines+markers",
                line={"color": PALETTE[1], "dash": "dash"},
                marker={"color": PALETTE[1]},
            ),
        ]
    )
    figure.update_xaxes(**TICKS["M"], dtick=month_dtick(len(history) + len(forecast)))
    _layout(figure, "Revenue forecast", "Month", "Revenue")
    figure.update_layout(showlegend=True, legend={"orientation": "h", "y": -0.2})
    return figure
