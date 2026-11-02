import datetime
from pathlib import Path

import pandas as pd
import pytest

from sales_insights.analytics.breakdowns import revenue_by_country
from sales_insights.analytics.filters import available_values, filter_orders
from sales_insights.analytics.revenue import total_revenue
from sales_insights.data.loader import load_orders

SAMPLE_DATA = Path(__file__).resolve().parents[2] / "data" / "sample_orders.csv"


def ids(df: pd.DataFrame) -> list[int]:
    return df["OrderID"].tolist()


# --- each filter alone, on the shared fixture ----------------------------------------------
# Dates: 1000 Jan 5, 1001 Jan 20, 1002 Feb 3, 1003 Feb 14, 1004 Feb 20, 1005 Mar 1.
# France: 1000, 1002, 1005. UK: 1001, 1003, 1004.


def test_no_filter_returns_every_row(loaded_orders):
    assert ids(filter_orders(loaded_orders)) == [1000, 1001, 1002, 1003, 1004, 1005]


def test_start_keeps_the_start_day_and_after(loaded_orders):
    assert ids(filter_orders(loaded_orders, start="2025-02-03")) == [1002, 1003, 1004, 1005]


def test_end_keeps_the_end_day_and_before(loaded_orders):
    assert ids(filter_orders(loaded_orders, end="2025-02-03")) == [1000, 1001, 1002]


def test_start_and_end_are_both_inclusive(loaded_orders):
    result = filter_orders(loaded_orders, start="2025-01-20", end="2025-02-14")
    assert ids(result) == [1001, 1002, 1003]


def test_same_start_and_end_selects_one_day(loaded_orders):
    assert ids(filter_orders(loaded_orders, start="2025-02-14", end="2025-02-14")) == [1003]


def test_end_includes_the_whole_day_when_dates_have_a_time(loaded_orders):
    timed = loaded_orders.copy()
    timed["Date"] = timed["Date"] + pd.Timedelta(hours=15)
    assert ids(filter_orders(timed, end="2025-01-20")) == [1000, 1001]
    assert ids(filter_orders(timed, start="2025-02-20")) == [1004, 1005]


@pytest.mark.parametrize(
    "bound",
    [
        "2025-02-03",
        datetime.date(2025, 2, 3),
        datetime.datetime(2025, 2, 3, 18, 30),
        pd.Timestamp("2025-02-03"),
    ],
)
def test_bounds_accept_text_dates_datetimes_and_timestamps(loaded_orders, bound):
    assert ids(filter_orders(loaded_orders, start=bound)) == [1002, 1003, 1004, 1005]


def test_countries_keeps_only_those_countries(loaded_orders):
    assert ids(filter_orders(loaded_orders, countries=["France"])) == [1000, 1002, 1005]


def test_several_countries(loaded_orders):
    assert ids(filter_orders(loaded_orders, countries=["France", "UK"])) == ids(loaded_orders)


def test_categories_keeps_only_those_categories(loaded_orders):
    assert ids(filter_orders(loaded_orders, categories={"Books"})) == [1000, 1002, 1004]


def test_none_means_no_filter_and_empty_means_nothing_selected(loaded_orders):
    assert len(filter_orders(loaded_orders, countries=None)) == 6
    assert len(filter_orders(loaded_orders, countries=[])) == 0
    assert len(filter_orders(loaded_orders, categories=())) == 0


def test_unknown_country_returns_no_rows(loaded_orders):
    assert len(filter_orders(loaded_orders, countries=["Atlantis"])) == 0


def test_a_single_text_is_one_value_not_a_list_of_letters(loaded_orders):
    assert ids(filter_orders(loaded_orders, countries="France")) == [1000, 1002, 1005]


def test_countries_are_matched_exactly(loaded_orders):
    assert len(filter_orders(loaded_orders, countries=["france"])) == 0


# --- combined filters ----------------------------------------------------------------------


def test_filters_combine_with_and(loaded_orders):
    result = filter_orders(
        loaded_orders,
        start="2025-02-01",
        countries=["UK"],
        categories=["Books"],
    )
    assert ids(result) == [1004]


def test_country_and_category_give_the_intersection(loaded_orders):
    result = filter_orders(loaded_orders, countries=["France"], categories=["Electronics"])
    assert ids(result) == [1005]


# --- no match, shape and purity ------------------------------------------------------------


def test_no_match_returns_an_empty_table_with_the_same_columns_and_dtypes(loaded_orders):
    result = filter_orders(loaded_orders, start="2030-01-01")
    assert len(result) == 0
    assert list(result.columns) == list(loaded_orders.columns)
    assert result.dtypes.equals(loaded_orders.dtypes)


def test_kept_rows_keep_their_index_values_and_revenue(loaded_orders):
    result = filter_orders(loaded_orders, countries=["UK"])
    assert result.index.tolist() == [1, 3, 4]
    assert result["Revenue"].tolist() == [500.0, 600.0, 10.0]
    assert result.dtypes.equals(loaded_orders.dtypes)


def test_the_input_is_not_changed(loaded_orders):
    before = loaded_orders.copy(deep=True)
    filter_orders(loaded_orders, start="2025-02-01", countries=["UK"], categories=["Books"])
    pd.testing.assert_frame_equal(loaded_orders, before)


def test_the_result_is_a_new_table_even_without_filters(loaded_orders):
    result = filter_orders(loaded_orders)
    result.loc[result.index[0], "Quantity"] = 99
    assert loaded_orders["Quantity"].iloc[0] != 99


def test_an_empty_input_gives_an_empty_result(loaded_orders):
    result = filter_orders(loaded_orders.iloc[0:0], countries=["UK"], start="2025-01-01")
    assert len(result) == 0
    assert list(result.columns) == list(loaded_orders.columns)


# --- invalid arguments ---------------------------------------------------------------------


def test_start_after_end_raises_and_names_both_dates(loaded_orders):
    with pytest.raises(ValueError, match=r"2025-03-01.*2025-01-01"):
        filter_orders(loaded_orders, start="2025-03-01", end="2025-01-01")


def test_a_date_that_is_not_a_date_raises_a_clear_error(loaded_orders):
    with pytest.raises(ValueError, match="not-a-date"):
        filter_orders(loaded_orders, start="not-a-date")


def test_a_missing_column_raises_a_clear_error(loaded_orders):
    with pytest.raises(ValueError, match="no column 'Country'"):
        filter_orders(loaded_orders.drop(columns="Country"), countries=["UK"])


def test_dates_that_are_still_text_raise_a_clear_error(orders):
    with pytest.raises(ValueError, match="Date"):
        filter_orders(orders, start="2025-01-01")


def test_a_filter_not_used_does_not_need_its_column(loaded_orders):
    # Only the columns of the filters that are asked for are required.
    result = filter_orders(loaded_orders.drop(columns=["Country", "Category"]), start="2025-03-01")
    assert ids(result) == [1005]


# --- time zones, missing values ------------------------------------------------------------


def test_dates_with_a_time_zone_are_compared_in_that_zone(loaded_orders):
    zoned = loaded_orders.copy()
    zoned["Date"] = zoned["Date"].dt.tz_localize("Europe/Paris")
    assert ids(filter_orders(zoned, start="2025-02-03", end="2025-02-14")) == [1002, 1003]


def test_a_bound_with_a_time_zone_is_also_accepted_on_zoned_dates(loaded_orders):
    zoned = loaded_orders.copy()
    zoned["Date"] = zoned["Date"].dt.tz_localize("UTC")
    assert ids(filter_orders(zoned, start=pd.Timestamp("2025-02-03", tz="UTC"))) == [
        1002,
        1003,
        1004,
        1005,
    ]


def test_the_end_day_is_a_calendar_day_even_when_the_clocks_change(loaded_orders):
    # In Paris the clocks went forward on 30 March 2025, so that day has 23 hours.
    changing = loaded_orders.iloc[:3].copy()
    changing["Date"] = pd.to_datetime(
        ["2025-03-30 23:30", "2025-03-31 00:30", "2025-03-31 12:00"]
    ).tz_localize("Europe/Paris")
    assert ids(filter_orders(changing, end="2025-03-30")) == [1000]
    assert ids(filter_orders(changing, start="2025-03-31")) == [1001, 1002]


def test_a_bound_with_a_time_zone_is_refused_on_dates_without_one(loaded_orders):
    with pytest.raises(ValueError, match="time zone"):
        filter_orders(loaded_orders, start=pd.Timestamp("2025-02-03", tz="UTC"))


def test_a_missing_date_is_dropped_by_a_date_filter_and_kept_otherwise(loaded_orders):
    holes = loaded_orders.copy()
    holes.loc[2, "Date"] = pd.NaT
    assert 1002 not in ids(filter_orders(holes, start="2025-01-01"))
    assert 1002 in ids(filter_orders(holes, countries=["France"]))


def test_a_missing_country_never_matches_a_country_filter(loaded_orders):
    holes = loaded_orders.copy()
    holes["Country"] = holes["Country"].astype("object")
    holes.loc[0, "Country"] = None
    assert ids(filter_orders(holes, countries=["France"])) == [1002, 1005]


# --- available_values ----------------------------------------------------------------------


def test_available_values_are_sorted_and_distinct(loaded_orders):
    assert available_values(loaded_orders, "Country") == ["France", "UK"]
    assert available_values(loaded_orders, "Category") == ["Books", "Electronics"]


def test_available_values_skip_missing_values(loaded_orders):
    holes = loaded_orders.copy()
    holes["Country"] = holes["Country"].astype("object")
    holes.loc[[0, 1], "Country"] = [None, float("nan")]
    assert available_values(holes, "Country") == ["France", "UK"]


def test_available_values_of_an_empty_table_is_an_empty_list(loaded_orders):
    assert available_values(loaded_orders.iloc[0:0], "Country") == []


def test_available_values_returns_plain_python_texts(loaded_orders):
    values = available_values(loaded_orders, "Category")
    assert isinstance(values, list)
    assert all(type(value) is str for value in values)


@pytest.mark.parametrize("column", ["Product", "UnitPrice", "Nope"])
def test_available_values_only_for_country_and_category(loaded_orders, column):
    with pytest.raises(ValueError, match="Country, Category"):
        available_values(loaded_orders, column)


# --- on the real sample data ---------------------------------------------------------------


def test_revenues_of_the_country_filters_add_up_to_the_total():
    orders = load_orders(SAMPLE_DATA)
    countries = available_values(orders, "Country")
    assert countries
    parts = [total_revenue(filter_orders(orders, countries=[c])) for c in countries]
    missing_country = total_revenue(orders[orders["Country"].isna()])
    assert sum(parts) + missing_country == pytest.approx(total_revenue(orders))


def test_filtering_by_country_agrees_with_the_breakdown():
    orders = load_orders(SAMPLE_DATA)
    breakdown = revenue_by_country(orders).dropna(subset=["Country"])
    for country, revenue in zip(breakdown["Country"], breakdown["revenue"], strict=True):
        filtered = filter_orders(orders, countries=[country])
        assert total_revenue(filtered) == pytest.approx(revenue)


def test_split_by_date_loses_nothing_on_the_sample_data():
    orders = load_orders(SAMPLE_DATA)
    middle = orders["Date"].sort_values().iloc[len(orders) // 2]
    before = filter_orders(orders, end=middle - pd.Timedelta(days=1))
    after = filter_orders(orders, start=middle)
    dated = orders["Date"].notna().sum()
    assert len(before) + len(after) == dated
