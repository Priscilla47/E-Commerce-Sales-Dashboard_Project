from pathlib import Path

import pandas as pd
import pytest

from sales_insights.ai.forecast import forecast_with_error
from sales_insights.cli.main import main
from sales_insights.dashboard.forecast_view import ForecastLabels, format_forecast
from sales_insights.data.loader import load_orders

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample_orders.csv"


def monthly(values, start="2023-01"):
    months = pd.period_range(start, periods=len(values), freq="M")
    return pd.DataFrame(
        {
            "OrderID": range(len(values)),
            "Date": [m.to_timestamp(how="end").normalize() for m in months],
            "Revenue": [float(v) for v in values],
        }
    )


def test_the_labels_of_the_sample_forecast_are_the_numbers_of_the_command(capsys):
    labels = format_forecast(forecast_with_error(load_orders(SAMPLE), 3))
    assert main(["--forecast", "3", str(SAMPLE)]) == 0
    lines = capsys.readouterr().out.splitlines()
    shown = [tuple(line.split()) for line in lines[2:5]]
    assert [tuple(row) for row in labels.rows] == shown
    assert lines[0] == f"Revenue forecast ({labels.method} method)"
    error_line = lines[5]
    assert f"MAE {labels.mae}," in error_line
    assert f"MAPE {labels.mape};" in error_line
    assert f"baseline: MAE {labels.baseline_mae}, MAPE {labels.baseline_mape}" in error_line
    assert labels.holdout == "the last 1 month"
    assert f"Error on {labels.holdout}, " in error_line


def test_the_labels_have_two_decimals_and_a_percent_with_one():
    labels = format_forecast(forecast_with_error(monthly([100, 110, 130, 125, 140, 150]), 2))
    assert isinstance(labels, ForecastLabels)
    for row in labels.rows:
        assert all(cell.count(".") == 1 and len(cell.split(".")[1]) == 2 for cell in row[1:])
    assert labels.mape.endswith("%") and len(labels.mape.split(".")[1]) == 2


def test_an_actual_value_of_zero_gives_n_a_for_the_percentage():
    labels = format_forecast(forecast_with_error(monthly([100, 110, 130, 125, 140, 0]), 1))
    assert labels.mape == "n/a"
    assert labels.baseline_mape == "n/a"
    assert labels.mae != "n/a"


def test_with_exactly_three_months_there_is_no_error_and_the_note_is_kept():
    labels = format_forecast(forecast_with_error(monthly([100, 110, 120]), 2))
    assert (labels.mae, labels.mape, labels.baseline_mae, labels.baseline_mape) == (None,) * 4
    assert labels.holdout is None
    assert "cannot be measured" in labels.note


def test_the_method_is_named_for_a_reader():
    short = format_forecast(forecast_with_error(monthly([1, 2, 3, 4, 5]), 1))
    long = format_forecast(forecast_with_error(monthly(range(100, 130)), 1))
    assert (short.method, long.method) == ("naive", "Holt-Winters")


def test_the_warnings_are_the_warnings_of_the_forecast():
    report = forecast_with_error(monthly([1, 2, 3, 4, 5]), 1)
    assert format_forecast(report).warnings == list(report.forecast.warnings)


def test_a_single_month_is_written_in_the_singular_and_several_in_the_plural():
    one = format_forecast(forecast_with_error(monthly([1, 2, 3, 4]), 1))
    three = format_forecast(forecast_with_error(monthly([1, 2, 3, 4, 5, 6]), 1))
    assert (one.holdout, three.holdout) == ("the last 1 month", "the last 3 months")


def test_the_labels_are_frozen():
    labels = format_forecast(forecast_with_error(monthly([1, 2, 3, 4, 5, 6]), 1))
    with pytest.raises(AttributeError):
        labels.mae = "0"  # type: ignore[misc]
