import pandas as pd
import pytest

from sales_insights.ai.months import complete_months


def table(dates, revenue=None):
    revenue = revenue if revenue is not None else [100.0] * len(dates)
    return pd.DataFrame(
        {"OrderID": range(len(dates)), "Date": pd.to_datetime(dates), "Revenue": revenue}
    )


def test_every_month_that_reaches_its_last_day_counts():
    periods, values, notes = complete_months(table(["2025-01-31", "2025-02-28", "2025-03-31"]))
    assert list(periods) == list(pd.to_datetime(["2025-01-01", "2025-02-01", "2025-03-01"]))
    assert values.tolist() == [100.0, 100.0, 100.0]
    assert notes == []


def test_a_last_month_that_the_data_does_not_finish_is_left_out_and_said():
    periods, values, notes = complete_months(table(["2025-01-31", "2025-02-28", "2025-03-01"]))
    assert len(periods) == len(values) == 2
    assert len(notes) == 1 and "2025-03" in notes[0] and "day 1 of 31" in notes[0]


def test_a_leap_day_finishes_february():
    _, values, notes = complete_months(table(["2024-01-31", "2024-02-29"]))
    assert len(values) == 2 and notes == []
    _, values, notes = complete_months(table(["2024-01-31", "2024-02-28"]))
    assert len(values) == 1 and "day 28 of 29" in notes[0]


def test_months_without_orders_inside_the_data_are_zero():
    _, values, _ = complete_months(table(["2025-01-31", "2025-03-31"]))
    assert values.tolist() == [100.0, 0.0, 100.0]


@pytest.mark.parametrize("dates", [[], [None]])
def test_a_table_without_dates_has_no_month_and_no_note(dates):
    frame = table(dates) if dates else table([]).astype({"Date": "datetime64[ns]"})
    periods, values, notes = complete_months(frame)
    assert len(periods) == len(values) == 0 and notes == []


def test_the_table_is_not_changed():
    frame = table(["2025-01-31", "2025-02-10"])
    before = frame.copy(deep=True)
    complete_months(frame)
    pd.testing.assert_frame_equal(frame, before)
