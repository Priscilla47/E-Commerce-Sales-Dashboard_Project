import base64
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")

import plotly.io as pio  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "src" / "sales_insights" / "dashboard" / "app.py"

# The expected figures are computed here with plain pandas from the raw file, not with the
# code under test.
SAMPLE = pd.read_csv(ROOT / "data" / "sample_orders.csv")
SAMPLE["Revenue"] = SAMPLE["UnitPrice"] * SAMPLE["Quantity"]
SAMPLE["Date"] = pd.to_datetime(SAMPLE["Date"])

HEADER = "OrderID,Date,Product,Category,UnitPrice,Quantity,CustomerID,Country\n"


@pytest.fixture
def app() -> AppTest:
    return AppTest.from_file(str(APP), default_timeout=60)


def figures(at: AppTest):
    """The figures drawn on the page, in order."""
    return [pio.from_json(chart.proto.spec) for chart in at.get("plotly_chart")]


def values(figure, axis):
    """The ``x`` or ``y`` of the first trace as a list (Streamlit sends numbers in binary)."""
    data = getattr(figure.data[0], axis)
    if data is None:
        return []
    if isinstance(data, dict):  # {"dtype": "f8", "bdata": "<base64>"}
        return list(np.frombuffer(base64.b64decode(data["bdata"]), dtype=data["dtype"]))
    return list(data)


def by_label(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


def upload(at: AppTest, content: str) -> AppTest:
    at.run()
    at.sidebar.radio[0].set_value("Upload a CSV").run()
    return at.sidebar.file_uploader[0].set_value(("orders.csv", content.encode(), "text/csv")).run()


# --- the three charts -------------------------------------------------------------------------


def test_the_page_draws_three_charts_in_order(app):
    app.run()
    assert not app.exception
    assert [figure.layout.title.text for figure in figures(app)] == [
        "Revenue by month",
        "Revenue by country",
        "Top 5 products by units sold",
    ]


def test_the_month_chart_equals_the_revenue_of_each_month_of_the_file(app):
    app.run()
    expected = SAMPLE.groupby(SAMPLE["Date"].dt.to_period("M"))["Revenue"].sum()
    first = figures(app)[0]
    assert values(first, "y") == pytest.approx(list(expected))
    assert len(values(first, "y")) == 5  # January to May 2025


def test_the_day_view_has_a_point_for_each_day_of_the_period(app):
    app.run()
    by_label(app.radio, "Revenue over time, by").set_value("Day").run()
    assert not app.exception
    first = figures(app)[0]
    assert first.layout.title.text == "Revenue by day"
    assert len(values(first, "y")) == (SAMPLE["Date"].max() - SAMPLE["Date"].min()).days + 1
    assert sum(values(first, "y")) == pytest.approx(SAMPLE["Revenue"].sum())


def test_the_time_scale_defaults_to_month_and_can_go_back(app):
    app.run()
    scale = by_label(app.radio, "Revenue over time, by")
    assert scale.value == "Month"
    scale.set_value("Day").run()
    by_label(app.radio, "Revenue over time, by").set_value("Month").run()
    assert figures(app)[0].layout.title.text == "Revenue by month"


def test_the_breakdown_chart_follows_the_selector(app):
    app.run()
    by_label(app.selectbox, "Break the revenue down by").set_value("Category").run()
    chart = figures(app)[1]
    expected = SAMPLE.groupby("Category")["Revenue"].sum().sort_values(ascending=False)
    assert chart.layout.title.text == "Revenue by category"
    assert list(values(chart, "x")) == list(expected.index)
    assert list(values(chart, "y")) == pytest.approx(list(expected))


def test_the_country_bars_are_the_countries_of_the_file_by_revenue(app):
    app.run()
    chart = figures(app)[1]
    expected = SAMPLE.groupby("Country")["Revenue"].sum().sort_values(ascending=False)
    assert list(values(chart, "y")) == pytest.approx(list(expected))
    assert sorted(values(chart, "x")) == sorted(expected.index)


# --- the products slider ----------------------------------------------------------------------


def test_the_slider_goes_from_one_to_the_number_of_products_and_starts_at_five(app):
    app.run()
    slider = by_label(app.slider, "Number of products")
    assert (slider.min, slider.max, slider.value) == (1, SAMPLE["Product"].nunique(), 5)


def test_the_products_chart_shows_as_many_bars_as_the_slider(app):
    app.run()
    by_label(app.slider, "Number of products").set_value(3).run()
    chart = figures(app)[2]
    expected = SAMPLE.groupby("Product")["Quantity"].sum().sort_values(ascending=False)
    assert len(values(chart, "x")) == 3
    assert sorted(values(chart, "y"), reverse=True) == list(expected.head(3))
    assert list(values(chart, "y")) == sorted(values(chart, "y"), reverse=True)


def test_the_slider_at_its_maximum_shows_every_product(app):
    app.run()
    slider = by_label(app.slider, "Number of products")
    slider.set_value(slider.max).run()
    assert not app.exception
    assert len(values(figures(app)[2], "x")) == SAMPLE["Product"].nunique()


# --- the charts follow the filters ------------------------------------------------------------


def test_the_charts_are_drawn_for_the_filtered_orders(app):
    app.run()
    country = sorted(SAMPLE["Country"].dropna().unique())[0]
    by_label(app.sidebar.multiselect, "Countries").set_value([country]).run()
    rows = SAMPLE[SAMPLE["Country"] == country]
    month_chart, country_chart, _ = figures(app)
    assert sum(values(month_chart, "y")) == pytest.approx(rows["Revenue"].sum())
    assert list(values(country_chart, "x")) == [country]


def test_a_filter_that_matches_nothing_gives_empty_charts_and_no_error(app):
    app.run()
    by_label(app.sidebar.multiselect, "Countries").set_value([]).run()
    assert not app.exception
    assert not app.error
    assert [len(values(figure, "x")) for figure in figures(app)] == [0, 0, 0]


# --- uploads ----------------------------------------------------------------------------------


def test_an_upload_with_one_product_has_no_slider_and_one_bar(app):
    app = upload(app, HEADER + "1,2025-01-05,Book,Books,10,2,C1,France\n")
    assert not app.exception
    assert len(app.slider) == 0
    assert list(values(figures(app)[2], "x")) == ["Book"]
    assert figures(app)[2].layout.title.text == "Top 1 product by units sold"


def test_an_upload_with_two_products_has_a_slider_from_one_to_two(app):
    app = upload(
        app,
        HEADER + "1,2025-01-05,Book,Books,10,2,C1,France\n2,2025-01-06,Pen,Office,2,9,C2,UK\n",
    )
    slider = by_label(app.slider, "Number of products")
    assert (slider.min, slider.max, slider.value) == (1, 2, 2)
    assert list(values(figures(app)[2], "x")) == ["Pen", "Book"]


def test_a_file_with_only_the_header_draws_empty_charts_without_error(app):
    app = upload(app, HEADER)
    assert not app.exception
    assert [len(values(figure, "x")) for figure in figures(app)] == [0, 0, 0]


def test_a_file_without_any_date_still_draws_the_other_charts(app):
    app = upload(app, HEADER + "1,,Book,Books,10,2,C1,France\n2,,Pen,Office,2,9,C2,UK\n")
    assert not app.exception
    month_chart, country_chart, products_chart = figures(app)
    assert len(values(month_chart, "x")) == 0
    assert sum(values(country_chart, "y")) == pytest.approx(38.0)
    assert len(values(products_chart, "x")) == 2


def test_no_chart_is_drawn_while_the_page_is_blocked(app):
    app.run()
    app.sidebar.radio[0].set_value("Upload a CSV").run()
    assert figures(app) == []


def test_a_text_in_the_file_cannot_break_a_chart(app):
    hostile = '"<script>alert(1)</script> & ** [x](y)"'
    app = upload(app, HEADER + f"1,2025-01-05,{hostile},Books,10,2,C1,France\n")
    assert not app.exception
    assert len(values(figures(app)[2], "x")) == 1
