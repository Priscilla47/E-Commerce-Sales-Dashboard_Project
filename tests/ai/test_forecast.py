import math

import numpy as np
import pandas as pd
import pytest

from sales_insights.ai.forecast import (
    Evaluation,
    Forecast,
    evaluate,
    forecast_revenue,
    mean_absolute_error,
    mean_absolute_percentage_error,
)


def orders_from(values, start="2023-01"):
    """One order a month, on the last day of the month, with the given revenue."""
    months = pd.period_range(start, periods=len(values), freq="M")
    return pd.DataFrame(
        {
            "OrderID": range(1, len(values) + 1),
            "Date": [month.to_timestamp(how="end").normalize() for month in months],
            "Revenue": [float(value) for value in values],
        }
    )


def linear(count):
    return [100 + 10 * month for month in range(1, count + 1)]


# --- the metrics, by hand ---------------------------------------------------------------------


def test_mae_of_four_points_by_hand():
    assert mean_absolute_error([100, 200, 300, 400], [110, 180, 330, 360]) == pytest.approx(25.0)


def test_mape_of_four_points_by_hand_is_in_percent():
    assert mean_absolute_percentage_error(
        [100, 200, 300, 400], [110, 180, 330, 360]
    ) == pytest.approx(10.0)


def test_mape_is_none_when_an_actual_value_is_zero():
    assert mean_absolute_percentage_error([100, 0, 300], [90, 5, 310]) is None


def test_mae_is_still_defined_when_an_actual_value_is_zero():
    assert mean_absolute_error([100, 0, 300], [90, 5, 310]) == pytest.approx(25 / 3)


def test_perfect_predictions_have_no_error():
    assert mean_absolute_error([5, 6], [5, 6]) == 0.0
    assert mean_absolute_percentage_error([5, 6], [5, 6]) == 0.0


@pytest.mark.parametrize("actual,predicted", [([], []), ([1, 2], [1])])
def test_the_metrics_refuse_empty_or_unequal_inputs(actual, predicted):
    with pytest.raises(ValueError):
        mean_absolute_error(actual, predicted)
    with pytest.raises(ValueError):
        mean_absolute_percentage_error(actual, predicted)


# --- forecast_revenue: the shape of the result ------------------------------------------------


def test_the_result_has_the_documented_columns_and_types():
    result = forecast_revenue(orders_from(linear(30)), 4)
    assert isinstance(result, Forecast)
    assert list(result.table.columns) == ["period", "forecast", "lower", "upper"]
    assert len(result.table) == 4
    assert pd.api.types.is_datetime64_any_dtype(result.table["period"])
    for column in ("forecast", "lower", "upper"):
        assert result.table[column].dtype == "float64"
    assert isinstance(result.warnings, tuple)


def test_the_periods_follow_the_last_month_without_gaps():
    result = forecast_revenue(orders_from(linear(30), start="2023-01"), 12)
    # 30 months from 2023-01 end in 2025-06.
    expected = pd.date_range("2025-07-01", periods=12, freq="MS")
    assert list(result.table["period"]) == list(expected)


def test_the_periods_cross_a_year_end():
    result = forecast_revenue(orders_from(linear(11), start="2023-01"), 3)
    assert list(result.table["period"]) == list(
        pd.to_datetime(["2023-12-01", "2024-01-01", "2024-02-01"])
    )


def test_lower_is_below_the_forecast_which_is_below_upper_on_every_row():
    noisy = [1000 + 50 * math.sin(i) + (i % 5) * 40 for i in range(36)]
    for method in ("naive", "holt_winters"):
        table = forecast_revenue(orders_from(noisy), 12, method).table
        assert (table["lower"] <= table["forecast"]).all()
        assert (table["forecast"] <= table["upper"]).all()


def test_nothing_is_rounded():
    table = forecast_revenue(orders_from([100 / 3] * 30), 3).table
    assert table["forecast"].tolist() == pytest.approx([100 / 3] * 3, rel=1e-12)
    assert table["forecast"].iloc[0] != round(table["forecast"].iloc[0], 2)


def test_the_forecast_never_goes_below_zero():
    falling = [max(250 - 10 * month, 0) + 5 for month in range(30)]
    table = forecast_revenue(orders_from(falling), 12).table
    assert (table[["forecast", "lower", "upper"]] >= 0).all().all()


# --- forecast_revenue: the models on synthetic series -----------------------------------------


def test_a_linear_trend_is_forecast_within_one_percent():
    # month 1..36 is the history, so the next values are 100 + 10 * 37 and so on.
    result = forecast_revenue(orders_from(linear(36)), 6)
    truth = [100 + 10 * month for month in range(37, 43)]
    assert result.method_used == "holt_winters"
    assert result.table["forecast"].tolist() == pytest.approx(truth, rel=0.01)


def test_a_constant_series_is_forecast_as_that_constant_with_an_interval_that_is_not_negative():
    for method in ("naive", "holt_winters"):
        table = forecast_revenue(orders_from([500] * 30), 6, method).table
        assert table["forecast"].tolist() == pytest.approx([500] * 6)
        assert ((table["upper"] - table["lower"]) >= 0).all()


def test_a_seasonal_series_keeps_its_seasons():
    season = [100, 120, 150, 180, 200, 220, 210, 190, 160, 130, 110, 90]
    result = forecast_revenue(orders_from(season * 3), 12)
    assert result.method_used == "holt_winters"
    assert result.table["forecast"].tolist() == pytest.approx(season, rel=0.05)


def test_one_outlier_month_does_not_break_the_forecast():
    values = [1000] * 30
    values[14] = 100_000
    table = forecast_revenue(orders_from(values), 6).table
    assert table[["forecast", "lower", "upper"]].notna().all().all()
    assert (table["lower"] <= table["forecast"]).all()
    assert (table["forecast"] <= table["upper"]).all()
    assert (table["forecast"] >= 0).all()


def test_the_interval_widens_with_the_horizon_when_the_series_is_noisy():
    noisy = [1000 + (i * 37 % 11) * 25 for i in range(10)]
    for method, history in (
        ("naive", noisy),
        ("holt_winters", [1000 + (i * 37 % 11) * 25 for i in range(30)]),
    ):
        table = forecast_revenue(orders_from(history), 6, method).table
        width = (table["upper"] - table["lower"]).tolist()
        assert width == sorted(width)
        assert width[-1] > width[0] > 0, method


def test_a_seasonal_naive_interval_is_as_wide_within_a_year():
    noisy = [1000 + (i * 37 % 11) * 25 for i in range(30)]
    table = forecast_revenue(orders_from(noisy), 6, "naive").table
    assert (table["upper"] - table["lower"]).nunique() == 1


# --- forecast_revenue: the naive method -------------------------------------------------------


def test_naive_repeats_the_same_month_of_the_previous_year():
    values = list(range(100, 124))  # 24 months, 2023-01 to 2024-12
    table = forecast_revenue(orders_from(values), 3, "naive").table
    assert table["forecast"].tolist() == [112.0, 113.0, 114.0]  # Jan to Mar 2024, a year earlier


def test_naive_with_less_than_a_year_repeats_the_last_value():
    result = forecast_revenue(orders_from([10, 20, 30, 40, 50]), 3, "naive")
    assert result.table["forecast"].tolist() == [50.0, 50.0, 50.0]
    assert result.method_used == "naive"


def test_naive_with_less_than_a_year_says_it_cannot_see_seasons():
    result = forecast_revenue(orders_from([10, 20, 30, 40, 50]), 3, "naive")
    assert any("year" in warning for warning in result.warnings)


# --- forecast_revenue: the fallback and the errors --------------------------------------------


def test_fewer_than_24_months_fall_back_to_naive_with_a_flag_and_a_warning():
    result = forecast_revenue(orders_from(linear(10)), 3, "holt_winters")
    assert result.method_used == "naive"
    assert result.fell_back is True
    assert result.history_months == 10
    assert any("24" in warning for warning in result.warnings)


def test_24_months_are_enough_for_holt_winters():
    result = forecast_revenue(orders_from(linear(24)), 3)
    assert (result.method_used, result.fell_back) == ("holt_winters", False)
    assert result.history_months == 24
    assert result.warnings == ()


def test_asking_for_naive_is_not_a_fallback():
    assert forecast_revenue(orders_from(linear(30)), 3, "naive").fell_back is False


@pytest.mark.parametrize("months", [0, 13, -1, 100])
def test_months_outside_1_to_12_raise_value_error_that_names_the_range(months):
    with pytest.raises(ValueError, match="1 to 12"):
        forecast_revenue(orders_from(linear(30)), months)


@pytest.mark.parametrize("months", [2.5, "3", None, True])
def test_months_must_be_a_whole_number(months):
    with pytest.raises(TypeError):
        forecast_revenue(orders_from(linear(30)), months)


def test_a_numpy_integer_is_accepted_for_months():
    assert len(forecast_revenue(orders_from(linear(30)), np.int64(2)).table) == 2


def test_an_unknown_method_is_refused():
    with pytest.raises(ValueError, match="method"):
        forecast_revenue(orders_from(linear(30)), 3, "magic")


@pytest.mark.parametrize("count", [0, 1, 2])
def test_fewer_than_3_months_of_history_say_how_many_are_needed(count):
    with pytest.raises(ValueError, match=rf"at least 3 months.*{count}"):
        forecast_revenue(orders_from(linear(count)) if count else orders_from([]), 3)


def test_missing_months_are_filled_by_analytics_and_counted():
    values = orders_from(linear(10))
    gap = values.drop(index=[4, 5])  # two months without orders
    result = forecast_revenue(gap, 2, "naive")
    assert result.history_months == 10


def test_a_last_month_that_the_data_does_not_finish_is_left_out_and_said():
    complete = orders_from(linear(6), start="2025-01")  # Jan to Jun, each on its last day
    partial = pd.concat(
        [
            complete,
            pd.DataFrame({"OrderID": [99], "Date": [pd.Timestamp("2025-07-01")], "Revenue": [1.0]}),
        ]
    )
    result = forecast_revenue(partial, 2, "naive")
    assert result.history_months == 6
    assert result.table["period"].iloc[0] == pd.Timestamp("2025-07-01")
    assert any("2025-07" in warning for warning in result.warnings)
    assert result.table["forecast"].tolist() == [160.0, 160.0]


def test_a_last_month_that_reaches_its_last_day_is_kept():
    result = forecast_revenue(orders_from(linear(6), start="2025-01"), 1, "naive")
    assert result.history_months == 6
    assert not any("left out" in warning for warning in result.warnings)


def test_the_table_is_not_changed_and_nothing_is_printed(capsys):
    table = orders_from(linear(30))
    before = table.copy(deep=True)
    forecast_revenue(table, 3)
    evaluate(table, "holt_winters")
    pd.testing.assert_frame_equal(table, before)
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


# --- evaluate ---------------------------------------------------------------------------------


def test_evaluate_the_model_beats_the_baseline_on_a_linear_trend():
    evaluation = evaluate(orders_from(linear(36)), "holt_winters", holdout=3)
    assert isinstance(evaluation, Evaluation)
    assert evaluation.model.mae < evaluation.baseline.mae
    assert evaluation.model.mae == pytest.approx(0.0, abs=1e-6)
    assert evaluation.baseline.mae == pytest.approx(120.0)  # a year of +10 a month
    assert evaluation.holdout == 3


def test_evaluate_trains_on_all_but_the_holdout_and_tests_on_the_holdout():
    values = [100.0] * 27 + [200.0, 200.0, 200.0]
    evaluation = evaluate(orders_from(values), "naive", holdout=3)
    # Naive repeats the same months of the year before: 100 each, against 200.
    assert evaluation.model.mae == pytest.approx(100.0)
    assert evaluation.model.mape == pytest.approx(50.0)


def test_evaluate_gives_a_none_mape_when_an_actual_value_is_zero():
    values = [100.0] * 29 + [0.0]
    evaluation = evaluate(orders_from(values), "naive", holdout=3)
    assert evaluation.model.mape is None
    assert evaluation.baseline.mape is None
    assert evaluation.model.mae > 0


def test_evaluate_reports_the_method_really_used_and_the_history():
    evaluation = evaluate(orders_from(linear(10)), "holt_winters", holdout=3)
    assert evaluation.method_used == "naive"
    assert evaluation.history_months == 7  # what was left to train on
    assert any("24" in warning for warning in evaluation.warnings)
    assert evaluation.model.mae == pytest.approx(evaluation.baseline.mae)


def test_evaluate_with_too_little_history_to_train_says_how_many_months_are_needed():
    with pytest.raises(ValueError, match="at least 3 months"):
        evaluate(orders_from(linear(5)), "holt_winters", holdout=3)


@pytest.mark.parametrize("holdout", [0, -1, 13])
def test_evaluate_refuses_a_holdout_outside_1_to_12(holdout):
    with pytest.raises(ValueError, match="holdout"):
        evaluate(orders_from(linear(36)), "naive", holdout=holdout)


def test_evaluate_refuses_a_holdout_that_is_not_a_whole_number():
    with pytest.raises(TypeError):
        evaluate(orders_from(linear(36)), "naive", holdout=2.5)


def test_evaluate_refuses_an_unknown_method():
    with pytest.raises(ValueError, match="method"):
        evaluate(orders_from(linear(36)), "magic")


def test_the_baseline_is_always_the_naive_method():
    evaluation = evaluate(orders_from(linear(36)), "naive", holdout=3)
    assert evaluation.model.mae == pytest.approx(evaluation.baseline.mae)


# --- what the module is allowed to do ---------------------------------------------------------


def test_the_forecast_code_reads_no_file_and_prints_nothing():
    from pathlib import Path

    import sales_insights.ai.forecast as module

    source = Path(module.__file__).read_text()
    for forbidden in ("read_csv", "open(", "print(", "round(", ".round("):
        assert forbidden not in source, forbidden
