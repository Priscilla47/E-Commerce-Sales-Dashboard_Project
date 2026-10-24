from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sales_insights.analytics.revenue import order_count, total_revenue
from sales_insights.analytics.timeseries import revenue_over_time
from sales_insights.data.loader import load_orders

SAMPLE_DATA = Path(__file__).resolve().parents[2] / "data" / "sample_orders.csv"


def lines(rows: list[tuple[int, str | None, float]]) -> pd.DataFrame:
    """A minimal loaded table from (OrderID, Date, Revenue) rows."""
    frame = pd.DataFrame(rows, columns=["OrderID", "Date", "Revenue"])
    frame["Date"] = pd.to_datetime(frame["Date"])
    return frame


@pytest.fixture
def year_boundary() -> pd.DataFrame:
    """Three orders over four months and two years, with February 2025 left empty.

    2024-12-31: 10.0   2025-01-01: 20.0   2025-03-15: 5.0
    """
    return lines([(1, "2024-12-31", 10.0), (2, "2025-01-01", 20.0), (3, "2025-03-15", 5.0)])


def ts(*dates: str) -> list[pd.Timestamp]:
    return [pd.Timestamp(date) for date in dates]


# --- grouping by month, day and year ----------------------------------------------------


def test_monthly_revenue_on_the_shared_fixture(loaded_orders):
    result = revenue_over_time(loaded_orders, "M")
    # January: 20 + 500; February: 30 + 600 + 10; March: 500.
    assert list(result.columns) == ["period", "revenue", "orders"]
    assert result["period"].tolist() == ts("2025-01-01", "2025-02-01", "2025-03-01")
    assert result["revenue"].tolist() == pytest.approx([520.0, 640.0, 500.0])
    assert result["orders"].tolist() == [2, 3, 1]


def test_month_is_the_default_frequency(loaded_orders):
    pd.testing.assert_frame_equal(
        revenue_over_time(loaded_orders), revenue_over_time(loaded_orders, "M")
    )


def test_yearly_revenue_crosses_a_year_boundary(year_boundary):
    result = revenue_over_time(year_boundary, "Y")
    assert result["period"].tolist() == ts("2024-01-01", "2025-01-01")
    assert result["revenue"].tolist() == pytest.approx([10.0, 25.0])
    assert result["orders"].tolist() == [1, 2]


def test_monthly_revenue_crosses_a_year_boundary(year_boundary):
    result = revenue_over_time(year_boundary, "M")
    assert result["period"].tolist() == ts("2024-12-01", "2025-01-01", "2025-02-01", "2025-03-01")
    assert result["revenue"].tolist() == pytest.approx([10.0, 20.0, 0.0, 5.0])


def test_daily_revenue_has_one_row_per_day(loaded_orders):
    result = revenue_over_time(loaded_orders, "D")
    # From 2025-01-05 to 2025-03-01 is 27 + 28 + 1 = 56 days.
    assert len(result) == 56
    assert result["period"].iloc[0] == pd.Timestamp("2025-01-05")
    assert result["period"].iloc[-1] == pd.Timestamp("2025-03-01")
    on_20_jan = result[result["period"] == pd.Timestamp("2025-01-20")]
    assert on_20_jan["revenue"].tolist() == pytest.approx([500.0])
    assert on_20_jan["orders"].tolist() == [1]


def test_lines_of_one_order_count_as_one_order_in_a_period():
    data = lines([(1, "2025-01-05", 10.0), (1, "2025-01-05", 5.0), (2, "2025-01-09", 1.0)])
    result = revenue_over_time(data, "M")
    assert result["orders"].tolist() == [2]
    assert result["revenue"].tolist() == pytest.approx([16.0])


# --- gaps -------------------------------------------------------------------------------


def test_a_month_without_orders_is_filled_with_zero(year_boundary):
    result = revenue_over_time(year_boundary, "M")
    february = result[result["period"] == pd.Timestamp("2025-02-01")]
    assert february["revenue"].tolist() == [0.0]
    assert february["orders"].tolist() == [0]


def test_days_without_orders_are_filled_with_zero(loaded_orders):
    result = revenue_over_time(loaded_orders, "D")
    assert (result["orders"] == 0).sum() == 56 - 6
    quiet = result[result["orders"] == 0]
    assert (quiet["revenue"] == 0.0).all()


def test_a_year_without_orders_is_filled_with_zero():
    data = lines([(1, "2023-06-01", 10.0), (2, "2025-06-01", 20.0)])
    result = revenue_over_time(data, "Y")
    assert result["period"].tolist() == ts("2023-01-01", "2024-01-01", "2025-01-01")
    assert result["revenue"].tolist() == pytest.approx([10.0, 0.0, 20.0])


def test_periods_are_consecutive_and_sorted(loaded_orders):
    unsorted = loaded_orders.sample(frac=1, random_state=1)
    for freq, step in (("D", "1D"), ("M", None), ("Y", None)):
        periods = revenue_over_time(unsorted, freq)["period"]
        assert periods.is_monotonic_increasing
        if step:
            assert (periods.diff().dropna() == pd.Timedelta(step)).all()


# --- sums -------------------------------------------------------------------------------


@pytest.mark.parametrize("freq", ["D", "M", "Y"])
def test_revenue_over_time_adds_up_to_the_total(loaded_orders, freq):
    result = revenue_over_time(loaded_orders, freq)
    assert result["revenue"].sum() == pytest.approx(total_revenue(loaded_orders))
    assert result["orders"].sum() == order_count(loaded_orders)


def test_the_sample_dataset_adds_up():
    sample = load_orders(SAMPLE_DATA)
    result = revenue_over_time(sample, "M")
    assert result["period"].tolist() == ts(
        "2025-01-01", "2025-02-01", "2025-03-01", "2025-04-01", "2025-05-01"
    )
    assert result["revenue"].sum() == pytest.approx(261333.44, abs=0.005)
    assert result["orders"].sum() == 500
    yearly = revenue_over_time(sample, "Y")
    assert yearly["revenue"].tolist() == pytest.approx([261333.44], abs=0.005)


# --- the edges of a period --------------------------------------------------------------


def test_first_and_last_days_of_a_month_land_in_that_month():
    data = lines(
        [
            (1, "2025-01-31", 1.0),
            (2, "2025-02-01", 2.0),
            (3, "2025-02-28", 4.0),
            (4, "2025-03-01", 8.0),
        ]
    )
    result = revenue_over_time(data, "M")
    assert result["period"].tolist() == ts("2025-01-01", "2025-02-01", "2025-03-01")
    assert result["revenue"].tolist() == pytest.approx([1.0, 6.0, 8.0])


def test_the_last_and_first_days_of_a_year_land_in_that_year():
    data = lines([(1, "2024-12-31", 1.0), (2, "2025-01-01", 2.0), (3, "2025-12-31", 4.0)])
    result = revenue_over_time(data, "Y")
    assert result["revenue"].tolist() == pytest.approx([1.0, 6.0])


def test_a_leap_day_belongs_to_february():
    data = lines([(1, "2024-02-29", 3.0), (2, "2024-03-01", 4.0)])
    result = revenue_over_time(data, "M")
    assert result["period"].tolist() == ts("2024-02-01", "2024-03-01")
    assert result["revenue"].tolist() == pytest.approx([3.0, 4.0])


def test_the_time_of_day_does_not_move_an_order_to_another_period():
    data = lines([(1, "2025-01-31 23:59:59", 1.0), (2, "2025-02-01 00:00:00", 2.0)])
    assert revenue_over_time(data, "M")["revenue"].tolist() == pytest.approx([1.0, 2.0])
    daily = revenue_over_time(data, "D")
    assert daily["period"].tolist() == ts("2025-01-31", "2025-02-01")


@pytest.mark.parametrize("freq", ["D", "M", "Y"])
def test_column_types_of_a_filled_result(year_boundary, freq):
    result = revenue_over_time(year_boundary, freq)
    assert result["revenue"].dtype == np.float64
    assert result["orders"].dtype == np.int64


def test_the_period_is_the_start_of_the_period_as_a_timestamp(loaded_orders):
    for freq, first in (("D", "2025-01-05"), ("M", "2025-01-01"), ("Y", "2025-01-01")):
        period = revenue_over_time(loaded_orders, freq)["period"]
        assert pd.api.types.is_datetime64_any_dtype(period)
        assert period.iloc[0] == pd.Timestamp(first)


# --- empty, single order, missing dates ---------------------------------------------------


@pytest.mark.parametrize("freq", ["D", "M", "Y"])
def test_empty_table_gives_an_empty_result_with_the_right_columns(loaded_orders, freq):
    result = revenue_over_time(loaded_orders.iloc[0:0], freq)
    assert result.empty
    assert list(result.columns) == ["period", "revenue", "orders"]
    assert pd.api.types.is_datetime64_any_dtype(result["period"])
    assert result["revenue"].dtype == np.float64
    assert result["orders"].dtype == np.int64


def test_a_single_order_gives_a_single_row(loaded_orders):
    single = loaded_orders.iloc[:1]  # 2025-01-05, revenue 20.0
    for freq, start in (("D", "2025-01-05"), ("M", "2025-01-01"), ("Y", "2025-01-01")):
        result = revenue_over_time(single, freq)
        assert result["period"].tolist() == ts(start)
        assert result["revenue"].tolist() == pytest.approx([20.0])
        assert result["orders"].tolist() == [1]


def test_lines_without_a_date_are_left_out():
    data = lines([(1, "2025-01-05", 10.0), (2, None, 99.0), (3, "2025-02-05", 5.0)])
    result = revenue_over_time(data, "M")
    assert result["revenue"].tolist() == pytest.approx([10.0, 5.0])
    assert result["orders"].tolist() == [1, 1]


def test_a_table_where_no_line_has_a_date_gives_an_empty_result():
    data = lines([(1, None, 10.0)])
    result = revenue_over_time(data, "M")
    assert result.empty
    assert list(result.columns) == ["period", "revenue", "orders"]


# --- invalid frequency --------------------------------------------------------------------


@pytest.mark.parametrize("freq", ["W", "Q", "H", "", "m", "MS", "year", None, 1])
def test_an_invalid_frequency_raises_value_error(loaded_orders, freq):
    with pytest.raises(ValueError, match="freq"):
        revenue_over_time(loaded_orders, freq)


def test_the_input_is_not_modified(loaded_orders):
    before = loaded_orders.copy()
    revenue_over_time(loaded_orders, "D")
    pd.testing.assert_frame_equal(loaded_orders, before)
