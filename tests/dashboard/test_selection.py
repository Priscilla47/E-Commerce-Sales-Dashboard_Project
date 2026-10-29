import datetime

import pandas as pd

from sales_insights.dashboard.selection import as_filter, period_bounds


def test_all_values_selected_means_no_filter():
    assert as_filter(["France", "UK"], ["France", "UK"]) is None
    assert as_filter(["UK", "France"], ["France", "UK"]) is None


def test_some_values_selected_is_a_filter():
    assert as_filter(["UK"], ["France", "UK"]) == ["UK"]


def test_nothing_selected_is_an_empty_filter_not_no_filter():
    assert as_filter([], ["France", "UK"]) == []


def test_nothing_available_and_nothing_selected_is_no_filter():
    assert as_filter([], []) is None


def test_period_bounds_are_the_first_and_last_day(loaded_orders):
    assert period_bounds(loaded_orders) == (datetime.date(2025, 1, 5), datetime.date(2025, 3, 1))


def test_period_bounds_ignore_missing_dates(loaded_orders):
    holes = loaded_orders.copy()
    holes.loc[0, "Date"] = pd.NaT
    assert period_bounds(holes) == (datetime.date(2025, 1, 20), datetime.date(2025, 3, 1))


def test_period_bounds_of_no_dates_is_none(loaded_orders):
    assert period_bounds(loaded_orders.iloc[0:0]) is None
    nat = loaded_orders.copy()
    nat["Date"] = pd.NaT
    assert period_bounds(nat) is None


def test_period_bounds_with_a_time_zone(loaded_orders):
    zoned = loaded_orders.copy()
    zoned["Date"] = zoned["Date"].dt.tz_localize("Europe/Paris")
    assert period_bounds(zoned) == (datetime.date(2025, 1, 5), datetime.date(2025, 3, 1))
