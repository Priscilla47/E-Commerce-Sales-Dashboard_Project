import numpy as np
import pandas as pd
import pytest

pytest.importorskip("plotly")

import plotly.graph_objects as go  # noqa: E402

from sales_insights.analytics.breakdowns import revenue_by  # noqa: E402
from sales_insights.analytics.products import top_products  # noqa: E402
from sales_insights.analytics.timeseries import revenue_over_time  # noqa: E402
from sales_insights.dashboard.charts import (  # noqa: E402
    revenue_by_chart,
    revenue_over_time_chart,
    top_products_chart,
)
from sales_insights.dashboard.theme import PALETTE  # noqa: E402


def _x(figure):
    return list(figure.data[0].x)


def _y(figure):
    return list(figure.data[0].y)


def _colours(figure):
    """Every colour the figure sets on its traces."""
    found = set()
    for trace in figure.data:
        for part in (getattr(trace, "marker", None), getattr(trace, "line", None)):
            colour = getattr(part, "color", None)
            if isinstance(colour, str):
                found.add(colour.upper())
    return found


# --- revenue_over_time_chart ------------------------------------------------------------------


@pytest.mark.parametrize("freq", ["D", "M", "Y"])
def test_the_time_chart_plots_exactly_the_analytics_values(loaded_orders, freq):
    expected = revenue_over_time(loaded_orders, freq)
    figure = revenue_over_time_chart(loaded_orders, freq)
    assert isinstance(figure, go.Figure)
    assert len(figure.data) == 1
    assert [pd.Timestamp(x) for x in _x(figure)] == list(expected["period"])
    assert _y(figure) == list(expected["revenue"])


def test_the_month_view_of_the_fixture_is_520_640_500(loaded_orders):
    figure = revenue_over_time_chart(loaded_orders, "M")
    assert _y(figure) == [520.0, 640.0, 500.0]
    assert [pd.Timestamp(x) for x in _x(figure)] == list(
        pd.to_datetime(["2025-01-01", "2025-02-01", "2025-03-01"])
    )


def test_an_empty_month_is_plotted_as_zero(loaded_orders):
    without_february = loaded_orders[loaded_orders["Date"].dt.month != 2]
    assert _y(revenue_over_time_chart(without_february, "M")) == [520.0, 0.0, 500.0]


def test_the_time_chart_says_what_it_shows(loaded_orders):
    month = revenue_over_time_chart(loaded_orders, "M")
    assert month.layout.title.text == "Revenue by month"
    assert month.layout.xaxis.title.text == "Month"
    assert month.layout.yaxis.title.text == "Revenue"
    assert revenue_over_time_chart(loaded_orders, "D").layout.xaxis.title.text == "Day"
    assert revenue_over_time_chart(loaded_orders, "Y").layout.title.text == "Revenue by year"


@pytest.mark.parametrize(
    ("freq", "tickformat", "dtick"),
    [("M", "%b %Y", "M1"), ("Y", "%Y", "M12"), ("D", None, None)],
)
def test_the_axis_ticks_match_the_period(loaded_orders, freq, tickformat, dtick):
    # A month chart must be labelled with months, not with arbitrary dates every two weeks.
    axis = revenue_over_time_chart(loaded_orders, freq).layout.xaxis
    assert (axis.tickformat, axis.dtick) == (tickformat, dtick)


def test_the_time_chart_shows_the_number_of_orders_when_hovering(loaded_orders):
    figure = revenue_over_time_chart(loaded_orders, "M")
    assert list(figure.data[0].customdata[:, 0]) == [2, 3, 1]
    assert "Orders" in figure.data[0].hovertemplate


@pytest.mark.parametrize("freq", ["W", "", "m", None, 1, "MS"])
def test_a_wrong_frequency_is_refused(loaded_orders, freq):
    with pytest.raises(ValueError, match="freq"):
        revenue_over_time_chart(loaded_orders, freq)


def test_the_time_chart_of_an_empty_table_is_an_empty_figure(loaded_orders):
    figure = revenue_over_time_chart(loaded_orders.iloc[0:0], "M")
    assert isinstance(figure, go.Figure)
    assert len(_x(figure)) == 0


# --- revenue_by_chart -------------------------------------------------------------------------


@pytest.mark.parametrize("column", ["Country", "Category"])
def test_the_breakdown_chart_plots_exactly_the_analytics_values(loaded_orders, column):
    expected = revenue_by(loaded_orders, column)
    figure = revenue_by_chart(loaded_orders, column)
    assert isinstance(figure, go.Figure)
    assert _x(figure) == list(expected[column])
    assert _y(figure) == list(expected["revenue"])


def test_the_bars_are_sorted_by_revenue_from_the_highest(loaded_orders):
    figure = revenue_by_chart(loaded_orders, "Country")
    assert _x(figure) == ["UK", "France"]
    assert _y(figure) == [1110.0, 550.0]
    # The axis keeps that order instead of sorting the names.
    assert list(figure.layout.xaxis.categoryarray) == ["UK", "France"]


def test_the_breakdown_chart_says_what_it_shows(loaded_orders):
    country = revenue_by_chart(loaded_orders, "Country")
    assert country.layout.title.text == "Revenue by country"
    assert country.layout.xaxis.title.text == "Country"
    assert country.layout.yaxis.title.text == "Revenue"
    category = revenue_by_chart(loaded_orders, "Category")
    assert category.layout.title.text == "Revenue by category"
    assert category.layout.xaxis.title.text == "Category"


@pytest.mark.parametrize("column", ["Product", "CustomerID", "Revenue", "country", "", None])
def test_only_country_and_category_are_accepted(loaded_orders, column):
    with pytest.raises(ValueError, match="Country"):
        revenue_by_chart(loaded_orders, column)


def test_the_breakdown_chart_of_an_empty_table_is_an_empty_figure(loaded_orders):
    figure = revenue_by_chart(loaded_orders.iloc[0:0], "Country")
    assert len(_x(figure)) == 0


# --- top_products_chart -----------------------------------------------------------------------


def test_the_products_chart_plots_exactly_the_analytics_values(loaded_orders):
    expected = top_products(loaded_orders, 3)
    figure = top_products_chart(loaded_orders, 3)
    assert isinstance(figure, go.Figure)
    assert _x(figure) == list(expected["Product"])
    assert _y(figure) == list(expected["units"])
    assert _x(figure) == ["Book", "Laptop", "Phone"]
    assert _y(figure) == [6, 2, 2]


def test_n_limits_the_number_of_bars(loaded_orders):
    figure = top_products_chart(loaded_orders, 1)
    assert _x(figure) == ["Book"]
    assert figure.layout.title.text == "Top 1 product by units sold"


def test_a_larger_n_than_the_number_of_products_shows_them_all(loaded_orders):
    figure = top_products_chart(loaded_orders, 50)
    assert _x(figure) == ["Book", "Laptop", "Phone"]
    assert figure.layout.title.text == "Top 3 products by units sold"


def test_the_products_chart_says_what_it_shows(loaded_orders):
    figure = top_products_chart(loaded_orders, 2)
    assert figure.layout.title.text == "Top 2 products by units sold"
    assert figure.layout.xaxis.title.text == "Product"
    assert figure.layout.yaxis.title.text == "Units sold"
    assert list(figure.layout.xaxis.categoryarray) == ["Book", "Laptop"]


def test_zero_products_is_an_empty_figure(loaded_orders):
    assert len(_x(top_products_chart(loaded_orders, 0))) == 0


def test_a_numpy_integer_is_accepted(loaded_orders):
    assert _x(top_products_chart(loaded_orders, np.int64(2))) == ["Book", "Laptop"]


def test_a_negative_n_is_refused(loaded_orders):
    with pytest.raises(ValueError):
        top_products_chart(loaded_orders, -1)


@pytest.mark.parametrize("n", [2.0, "2", None, True])
def test_n_must_be_a_whole_number(loaded_orders, n):
    with pytest.raises(TypeError):
        top_products_chart(loaded_orders, n)


def test_the_products_chart_of_an_empty_table_is_an_empty_figure(loaded_orders):
    assert len(_x(top_products_chart(loaded_orders.iloc[0:0], 5))) == 0


# --- all the builders -------------------------------------------------------------------------


def _all_figures(table):
    return [
        revenue_over_time_chart(table, "M"),
        revenue_by_chart(table, "Country"),
        revenue_by_chart(table, "Category"),
        top_products_chart(table, 3),
    ]


def test_the_builders_print_nothing(loaded_orders, capsys):
    _all_figures(loaded_orders)
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_the_builders_do_not_change_the_table(loaded_orders):
    before = loaded_orders.copy(deep=True)
    _all_figures(loaded_orders)
    pd.testing.assert_frame_equal(loaded_orders, before)


def test_the_series_use_only_colours_of_the_shared_palette(loaded_orders):
    palette = {colour.upper() for colour in PALETTE}
    for figure in _all_figures(loaded_orders):
        colours = _colours(figure)
        assert colours, "the series has a colour of the palette, not the library default"
        assert colours <= palette


def test_the_figures_claim_no_currency(loaded_orders):
    # The data has no currency column, so no title or axis may name one.
    for figure in _all_figures(loaded_orders):
        texts = [figure.layout.title.text, figure.layout.yaxis.title.text]
        assert not any(symbol in text for text in texts for symbol in "€$£")
