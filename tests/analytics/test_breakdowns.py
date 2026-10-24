import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sales_insights.analytics.breakdowns import (
    revenue_by,
    revenue_by_category,
    revenue_by_country,
)
from sales_insights.analytics.revenue import total_revenue
from sales_insights.data.loader import load_orders

SAMPLE_DATA = Path(__file__).resolve().parents[2] / "data" / "sample_orders.csv"


def groups(rows: list[tuple[int, str | None, float]]) -> pd.DataFrame:
    """A minimal loaded table from (OrderID, Country, Revenue) rows."""
    return pd.DataFrame(rows, columns=["OrderID", "Country", "Revenue"])


# --- hand-computed results on the shared fixture ------------------------------------------


def test_revenue_by_country(loaded_orders):
    result = revenue_by_country(loaded_orders)
    # UK: lines 1001, 1003, 1004 = 500 + 600 + 10; France: 1000, 1002, 1005 = 20 + 30 + 500.
    assert list(result.columns) == ["Country", "revenue", "orders", "share"]
    assert result["Country"].tolist() == ["UK", "France"]
    assert result["revenue"].tolist() == pytest.approx([1110.0, 550.0])
    assert result["orders"].tolist() == [3, 3]
    assert result["share"].tolist() == pytest.approx([1110.0 / 1660.0, 550.0 / 1660.0])


def test_revenue_by_category(loaded_orders):
    result = revenue_by_category(loaded_orders)
    # Electronics: 500 + 600 + 500; Books: 20 + 30 + 10.
    assert list(result.columns) == ["Category", "revenue", "orders", "share"]
    assert result["Category"].tolist() == ["Electronics", "Books"]
    assert result["revenue"].tolist() == pytest.approx([1600.0, 60.0])
    assert result["orders"].tolist() == [3, 3]
    assert result["share"].tolist() == pytest.approx([1600.0 / 1660.0, 60.0 / 1660.0])


def test_the_wrappers_are_revenue_by_with_the_right_column(loaded_orders):
    pd.testing.assert_frame_equal(
        revenue_by_country(loaded_orders), revenue_by(loaded_orders, "Country")
    )
    pd.testing.assert_frame_equal(
        revenue_by_category(loaded_orders), revenue_by(loaded_orders, "Category")
    )


@pytest.mark.parametrize("column", ["Product", "Category", "CustomerID", "Country"])
def test_every_text_column_can_be_used(loaded_orders, column):
    result = revenue_by(loaded_orders, column)
    assert list(result.columns) == [column, "revenue", "orders", "share"]
    assert result["revenue"].sum() == pytest.approx(1660.0)


# --- the totals add up ----------------------------------------------------------------------


@pytest.mark.parametrize("column", ["Country", "Category", "Product", "CustomerID"])
def test_shares_sum_to_one_and_revenue_to_the_total(loaded_orders, column):
    result = revenue_by(loaded_orders, column)
    assert result["share"].sum() == pytest.approx(1.0)
    assert result["revenue"].sum() == pytest.approx(total_revenue(loaded_orders))


def test_the_sample_dataset_adds_up():
    sample = load_orders(SAMPLE_DATA)
    for result in (revenue_by_country(sample), revenue_by_category(sample)):
        assert result["revenue"].sum() == pytest.approx(261333.44, abs=0.005)
        assert result["share"].sum() == pytest.approx(1.0)
        assert result["revenue"].is_monotonic_decreasing
    assert len(revenue_by_country(sample)) == 10
    assert len(revenue_by_category(sample)) == 5


# --- order and determinism -----------------------------------------------------------------


def test_a_tie_in_revenue_is_ordered_by_name():
    data = groups([(1, "Spain", 10.0), (2, "Italy", 10.0), (3, "France", 20.0), (4, "Chad", 5.0)])
    assert revenue_by(data, "Country")["Country"].tolist() == ["France", "Italy", "Spain", "Chad"]


def test_the_result_does_not_depend_on_the_row_order(loaded_orders):
    shuffled = loaded_orders.sample(frac=1, random_state=3)
    pd.testing.assert_frame_equal(revenue_by_country(shuffled), revenue_by_country(loaded_orders))


def test_the_result_has_a_clean_index(loaded_orders):
    assert revenue_by_country(loaded_orders).index.tolist() == [0, 1]


def test_the_input_is_not_modified(loaded_orders):
    before = loaded_orders.copy()
    revenue_by_country(loaded_orders)
    pd.testing.assert_frame_equal(loaded_orders, before)


# --- orders --------------------------------------------------------------------------------


def test_lines_of_one_order_count_as_one_order():
    data = groups([(1, "France", 10.0), (1, "France", 5.0), (2, "France", 1.0)])
    result = revenue_by(data, "Country")
    assert result["orders"].tolist() == [2]
    assert result["revenue"].tolist() == pytest.approx([16.0])


# --- empty and single group ----------------------------------------------------------------


def test_empty_table_gives_an_empty_result_with_the_right_columns(loaded_orders):
    result = revenue_by_country(loaded_orders.iloc[0:0])
    assert result.empty
    assert list(result.columns) == ["Country", "revenue", "orders", "share"]
    assert result["revenue"].dtype == np.float64
    assert result["orders"].dtype == np.int64
    assert result["share"].dtype == np.float64


def test_a_single_group_has_a_share_of_one(loaded_orders):
    france = loaded_orders[loaded_orders["Country"] == "France"]
    result = revenue_by_country(france)
    assert result["Country"].tolist() == ["France"]
    assert result["share"].tolist() == [1.0]


def test_shares_are_zero_when_the_total_revenue_is_zero():
    data = groups([(1, "France", 0.0), (2, "UK", 0.0)])
    result = revenue_by(data, "Country")
    assert result["share"].tolist() == [0.0, 0.0]


# --- missing values ------------------------------------------------------------------------


def test_lines_without_a_label_are_kept_so_the_totals_still_add_up():
    data = groups([(1, "France", 10.0), (2, None, 30.0), (3, "UK", 10.0)])
    result = revenue_by(data, "Country")
    assert result["revenue"].sum() == pytest.approx(50.0)
    assert result["share"].sum() == pytest.approx(1.0)
    assert result["Country"].isna().sum() == 1
    assert result.loc[result["Country"].isna(), "revenue"].tolist() == [30.0]


def test_unused_categories_of_a_category_column_are_not_groups(loaded_orders):
    # A label column stored as a category keeps the labels nobody used; they are not groups.
    countries = pd.CategoricalDtype(["France", "Italy", "UK"])
    stored = loaded_orders.astype({"Country": countries})
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = revenue_by_country(stored)
    assert result["Country"].astype(str).tolist() == ["UK", "France"]
    assert result["revenue"].tolist() == pytest.approx([1110.0, 550.0])
    assert result["share"].sum() == pytest.approx(1.0)


# --- invalid columns -----------------------------------------------------------------------


def test_a_column_that_does_not_exist_raises_value_error(loaded_orders):
    with pytest.raises(ValueError, match="Colour"):
        revenue_by(loaded_orders, "Colour")


@pytest.mark.parametrize("column", ["Revenue", "UnitPrice", "Quantity", "OrderID", "Date"])
def test_a_column_that_is_not_allowed_raises_value_error(loaded_orders, column):
    with pytest.raises(ValueError, match="Cannot break revenue down"):
        revenue_by(loaded_orders, column)


def test_an_allowed_column_missing_from_the_data_raises_value_error(loaded_orders):
    with pytest.raises(ValueError, match="no column 'Country'"):
        revenue_by(loaded_orders.drop(columns="Country"), "Country")
