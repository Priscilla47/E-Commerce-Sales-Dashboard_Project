import datetime
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")

import plotly.io as pio  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from sales_insights.ai.forecast import forecast_with_error  # noqa: E402
from sales_insights.cli.main import main  # noqa: E402
from sales_insights.dashboard.forecast_view import format_forecast  # noqa: E402
from sales_insights.data.loader import load_orders  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "src" / "sales_insights" / "dashboard" / "app.py"
SAMPLE = ROOT / "data" / "sample_orders.csv"
HEADER = "OrderID,Date,Product,Category,UnitPrice,Quantity,CustomerID,Country\n"


@pytest.fixture
def app() -> AppTest:
    return AppTest.from_file(str(APP), default_timeout=60).run()


def forecast_tab(at):
    return next(tab for tab in at.tabs if tab.label == "Forecast")


def by_label(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


def cells(tab):
    """The table of the forecast as the rows of text the page shows."""
    return [list(map(str, row)) for row in tab.dataframe[0].value.itertuples(index=False)]


def upload(at, content):
    at.sidebar.radio[0].set_value("Upload a CSV").run()
    return at.sidebar.file_uploader[0].set_value(("orders.csv", content.encode(), "text/csv")).run()


def months_file(count):
    lines = [HEADER.rstrip("\n")]
    for index in range(count):
        year, month = 2023 + index // 12, index % 12 + 1
        day = (
            datetime.date(year + month // 12, month % 12 + 1, 1) - datetime.timedelta(days=1)
        ).day
        lines.append(
            f"{index},{year}-{month:02d}-{day:02d},Book,Books,{100 + 10 * index},1,C{index},France"
        )
    return "\n".join(lines) + "\n"


# --- the tab ----------------------------------------------------------------------------------


def test_the_page_has_an_overview_a_forecast_and_an_insights_tab(app):
    assert [tab.label for tab in app.tabs] == ["Overview", "Forecast", "Insights"]
    assert not app.exception


def test_the_cards_stay_above_the_tabs_and_the_three_charts_in_the_overview(app):
    assert len(app.metric) == 8  # the four cards, then the four error measures of the forecast
    assert [metric.label for metric in app.metric[:4]] == [
        "Revenue",
        "Orders",
        "Average order value",
        "Customers",
    ]
    assert not app.tabs[0].metric
    assert len(app.tabs[0].get("plotly_chart")) == 3
    assert len(forecast_tab(app).get("plotly_chart")) == 1


def test_the_selector_offers_1_to_12_months_and_starts_at_3(app):
    selector = by_label(forecast_tab(app).selectbox, "Months to forecast")
    assert list(selector.options) == [str(n) for n in range(1, 13)]
    assert selector.value == 3


def test_the_forecast_chart_shows_the_history_the_forecast_and_the_band(app):
    figure = pio.from_json(forecast_tab(app).get("plotly_chart")[0].proto.spec)
    assert figure.layout.title.text == "Revenue forecast"
    assert [trace.name for trace in figure.data if trace.name] == [
        "95% interval",
        "History",
        "Forecast",
    ]


# --- the numbers are the numbers of the command and of the code -------------------------------


def test_the_table_of_the_tab_is_the_table_of_the_command(app, capsys):
    assert main(["--forecast", "3", str(SAMPLE)]) == 0
    printed = [line.split() for line in capsys.readouterr().out.splitlines()[2:5]]
    assert cells(forecast_tab(app)) == printed


def test_the_metrics_are_the_error_line_of_the_command(app, capsys):
    main(["--forecast", "3", str(SAMPLE)])
    error_line = capsys.readouterr().out.splitlines()[5]
    metrics = {metric.label: metric.value for metric in forecast_tab(app).metric}
    assert set(metrics) == {"MAE", "MAPE", "Baseline MAE", "Baseline MAPE"}
    assert f"MAE {metrics['MAE']}, MAPE {metrics['MAPE']}; " in error_line
    assert f"baseline: MAE {metrics['Baseline MAE']}, MAPE {metrics['Baseline MAPE']}" in error_line


def test_the_tab_equals_the_report_of_the_code(app):
    labels = format_forecast(forecast_with_error(load_orders(SAMPLE), 3))
    assert [tuple(row) for row in cells(forecast_tab(app))] == [tuple(r) for r in labels.rows]


def test_choosing_6_months_gives_six_rows_and_six_points(app):
    by_label(forecast_tab(app).selectbox, "Months to forecast").set_value(6).run()
    tab = forecast_tab(app)
    assert len(cells(tab)) == 6
    figure = pio.from_json(tab.get("plotly_chart")[0].proto.spec)
    forecast_line = next(trace for trace in figure.data if trace.name == "Forecast")
    assert len(forecast_line.x) == 6


# --- what the tab says ------------------------------------------------------------------------


def text_of(tab):
    parts = [e.value for e in tab.caption] + [e.value for e in tab.warning]
    parts += [e.value for e in tab.info] + [e.value for e in tab.markdown]
    return "\n".join(str(part) for part in parts)


def test_the_tab_says_it_is_an_estimate_and_which_method_made_it(app):
    text = text_of(forecast_tab(app))
    assert "estimate" in text
    assert "naive method" in text
    assert "4 complete months" in text


def test_the_warnings_of_the_forecast_are_shown_in_plain_words(app):
    warnings = " ".join(box.value for box in forecast_tab(app).warning)
    assert "2025-05" in warnings and "left out" in warnings
    assert "24" in warnings
    assert "cannot see the seasons" in warnings


def test_the_error_is_described_as_measured_on_the_last_months(app):
    assert "last 1 month" in text_of(forecast_tab(app))


def test_a_long_history_is_forecast_with_holt_winters_and_has_no_warning(app):
    app = upload(app, months_file(30))
    tab = forecast_tab(app)
    assert "Holt-Winters method" in text_of(tab)
    assert not tab.warning
    assert len(tab.metric) == 4


def test_with_exactly_three_months_there_is_a_forecast_but_no_error(app):
    app = upload(app, months_file(3))
    tab = forecast_tab(app)
    assert len(cells(tab)) == 3
    assert len(tab.metric) == 0
    assert "cannot be measured with 3 months" in text_of(tab)


# --- when there is not enough to forecast -----------------------------------------------------


def test_with_too_short_a_history_the_tab_says_what_the_command_says(app, capsys, tmp_path):
    app = upload(app, months_file(2))
    tab = forecast_tab(app)
    path = tmp_path / "two.csv"
    path.write_text(months_file(2))
    assert main(["--forecast", "3", str(path)]) == 84
    reason = capsys.readouterr().err.split("error: ", 1)[1].strip()
    assert [box.value for box in tab.info] == [reason]
    assert not tab.get("plotly_chart")
    assert not tab.metric
    assert not app.exception


def test_a_period_with_less_than_three_complete_months_says_so(app):
    app.sidebar.date_input[0].set_value(
        (datetime.date(2025, 2, 1), datetime.date(2025, 3, 31))
    ).run()
    tab = forecast_tab(app)
    assert any("at least 3 months of history, found 2" in box.value for box in tab.info)
    assert not app.exception


def test_filtering_everything_out_says_so_in_the_tab_and_does_not_raise(app):
    by_label(app.sidebar.multiselect, "Countries").set_value([]).run()
    tab = forecast_tab(app)
    assert any("found 0" in box.value for box in tab.info)
    assert not app.exception and not app.error


def test_the_forecast_follows_the_filters(app):
    before = cells(forecast_tab(app))
    country = sorted(load_orders(SAMPLE)["Country"].dropna().unique())[0]
    by_label(app.sidebar.multiselect, "Countries").set_value([country]).run()
    assert cells(forecast_tab(app)) != before


def test_a_file_without_any_date_does_not_raise(app):
    app = upload(app, HEADER + "1,,Book,Books,10,2,C1,France\n")
    assert not app.exception
    assert any("found 0" in box.value for box in forecast_tab(app).info)


def test_text_from_the_file_cannot_break_the_forecast_tab(app):
    hostile = '"<b>x</b> **y** [z](w)"'
    app = upload(app, months_file(4).replace("Book", hostile))
    assert not app.exception
    assert len(cells(forecast_tab(app))) == 3


def test_a_revenue_too_large_to_forecast_is_explained_in_the_tab_and_does_not_raise(app):
    content = months_file(30).replace(",100,", ",1e308,", 1)
    app = upload(app, content)
    assert not app.exception
    assert any("too large to forecast" in box.value for box in forecast_tab(app).info)
    assert not forecast_tab(app).get("plotly_chart")
    assert len(app.metric[0].value.replace(",", "")) > 300  # the card shows the full amount
