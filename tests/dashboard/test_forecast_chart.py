import pandas as pd
import pytest

pytest.importorskip("plotly")

import plotly.graph_objects as go  # noqa: E402

from sales_insights.ai.forecast import forecast_with_error  # noqa: E402
from sales_insights.dashboard.charts import forecast_chart  # noqa: E402
from sales_insights.dashboard.theme import PALETTE  # noqa: E402


def _months():
    """Eight months of history, one order on the last day of each (the fixture has three)."""
    months = pd.period_range("2025-01", periods=8, freq="M")
    return pd.DataFrame(
        {
            "OrderID": range(8),
            "Date": [m.to_timestamp(how="end").normalize() for m in months],
            "Revenue": [100.0, 120.0, 90.0, 150.0, 130.0, 170.0, 160.0, 190.0],
        }
    )


@pytest.fixture
def report():
    return forecast_with_error(_months(), 3)


def trace(figure, name):
    return next(item for item in figure.data if item.name == name)


def test_the_chart_has_the_history_the_forecast_and_the_band(report):
    figure = forecast_chart(report.history, report.forecast.table)
    assert isinstance(figure, go.Figure)
    assert {item.name for item in figure.data} >= {"History", "Forecast", "95% interval"}


def test_the_forecast_line_is_exactly_the_forecast_table(report):
    table = report.forecast.table
    line = trace(forecast_chart(report.history, table), "Forecast")
    assert list(line.y) == table["forecast"].tolist()
    assert [pd.Timestamp(x) for x in line.x] == list(table["period"])


def test_the_history_line_is_exactly_the_history(report):
    line = trace(forecast_chart(report.history, report.forecast.table), "History")
    assert list(line.y) == report.history["revenue"].tolist()
    assert [pd.Timestamp(x) for x in line.x] == list(report.history["period"])


def test_the_band_runs_from_the_lower_to_the_upper_limit(report):
    table = report.forecast.table
    figure = forecast_chart(report.history, table)
    band = trace(figure, "95% interval")
    assert list(band.y) == table["lower"].tolist()
    assert band.fill == "tonexty"
    upper = next(item for item in figure.data if list(item.y) == table["upper"].tolist())
    assert upper.showlegend is False
    # The upper trace comes right before the lower one, which fills up to it.
    assert list(figure.data).index(upper) + 1 == list(figure.data).index(band)


def test_the_titles_say_what_is_shown(report):
    figure = forecast_chart(report.history, report.forecast.table)
    assert figure.layout.title.text == "Revenue forecast"
    assert figure.layout.xaxis.title.text == "Month"
    assert figure.layout.yaxis.title.text == "Revenue"
    assert "€" not in figure.layout.yaxis.title.text + figure.layout.title.text


def test_the_lines_use_the_palette_and_the_forecast_is_dashed(report):
    figure = forecast_chart(report.history, report.forecast.table)
    assert trace(figure, "History").line.color.upper() == PALETTE[0].upper()
    assert trace(figure, "Forecast").line.color.upper() == PALETTE[1].upper()
    assert trace(figure, "Forecast").line.dash == "dash"
    for item in figure.data:
        colour = item.line.color
        assert colour is None or colour.upper() in {c.upper() for c in PALETTE}


def test_the_legend_is_shown(report):
    assert forecast_chart(report.history, report.forecast.table).layout.showlegend is True


def test_an_empty_forecast_gives_none(report):
    assert forecast_chart(report.history, report.forecast.table.iloc[0:0]) is None


def test_an_empty_history_still_draws_the_forecast(report):
    figure = forecast_chart(report.history.iloc[0:0], report.forecast.table)
    assert isinstance(figure, go.Figure)
    assert len(trace(figure, "History").y) == 0


def test_the_inputs_are_not_changed(report):
    history, table = report.history.copy(deep=True), report.forecast.table.copy(deep=True)
    forecast_chart(report.history, report.forecast.table)
    pd.testing.assert_frame_equal(report.history, history)
    pd.testing.assert_frame_equal(report.forecast.table, table)


def test_the_chart_prints_nothing(report, capsys):
    forecast_chart(report.history, report.forecast.table)
    assert capsys.readouterr() == ("", "")


def test_a_table_without_the_expected_columns_is_refused(report):
    with pytest.raises(ValueError, match="column"):
        forecast_chart(report.history, report.forecast.table.drop(columns=["lower"]))
    with pytest.raises(ValueError, match="column"):
        forecast_chart(report.history.drop(columns=["revenue"]), report.forecast.table)
