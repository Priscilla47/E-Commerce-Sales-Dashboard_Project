from pathlib import Path

import pandas as pd
import pytest

from sales_insights.analytics.revenue import (
    average_order_value,
    order_count,
    total_revenue,
    units_sold,
)
from sales_insights.data.loader import load_orders

SAMPLE_DATA = Path(__file__).resolve().parents[2] / "data" / "sample_orders.csv"


def order_lines(rows: list[tuple[int, float, int]]) -> pd.DataFrame:
    """A minimal loaded table from (OrderID, UnitPrice, Quantity) rows."""
    frame = pd.DataFrame(rows, columns=["OrderID", "UnitPrice", "Quantity"])
    frame["Revenue"] = frame["UnitPrice"] * frame["Quantity"]
    return frame


# --- normal case ------------------------------------------------------------------------


def test_total_revenue_adds_up_every_line(loaded_orders):
    assert total_revenue(loaded_orders) == pytest.approx(1660.0)


def test_order_count_counts_the_orders(loaded_orders):
    assert order_count(loaded_orders) == 6


def test_units_sold_adds_up_the_quantities(loaded_orders):
    assert units_sold(loaded_orders) == 10


def test_average_order_value_is_revenue_divided_by_orders(loaded_orders):
    assert average_order_value(loaded_orders) == pytest.approx(1660.0 / 6)


# --- empty data -------------------------------------------------------------------------


def test_empty_table_gives_zeros_without_dividing_by_zero(loaded_orders):
    empty = loaded_orders.iloc[0:0]
    assert total_revenue(empty) == 0.0
    assert order_count(empty) == 0
    assert units_sold(empty) == 0
    assert average_order_value(empty) == 0.0


def test_header_only_file_gives_zeros(tmp_path):
    path = tmp_path / "header_only.csv"
    path.write_text("OrderID,Date,Product,Category,UnitPrice,Quantity,CustomerID,Country\n")
    empty = load_orders(path)
    assert (total_revenue(empty), order_count(empty), units_sold(empty)) == (0.0, 0, 0)
    assert average_order_value(empty) == 0.0


# --- single order -----------------------------------------------------------------------


def test_single_order(loaded_orders):
    single = loaded_orders.iloc[:1]  # 2 books at 10.0
    assert total_revenue(single) == pytest.approx(20.0)
    assert order_count(single) == 1
    assert units_sold(single) == 2
    assert average_order_value(single) == pytest.approx(20.0)


# --- several lines in one order ---------------------------------------------------------


def test_lines_with_the_same_order_id_are_one_order():
    lines = order_lines([(1, 10.0, 2), (1, 5.0, 4), (2, 100.0, 1)])
    assert order_count(lines) == 2
    assert total_revenue(lines) == pytest.approx(140.0)
    assert average_order_value(lines) == pytest.approx(70.0)
    assert units_sold(lines) == 7


# --- precision and types ----------------------------------------------------------------


def test_float_sums_are_not_rounded_inside_the_functions():
    lines = order_lines([(i, 0.1, 3) for i in range(1, 11)])  # ten lines of 0.1 * 3
    assert total_revenue(lines) == pytest.approx(3.0)
    assert average_order_value(lines) == pytest.approx(0.3)


def test_prices_with_many_decimals_keep_their_precision():
    lines = order_lines([(1, 19.99, 3), (2, 0.333, 7)])
    assert total_revenue(lines) == pytest.approx(19.99 * 3 + 0.333 * 7, abs=1e-12)


def test_functions_return_plain_python_numbers(loaded_orders):
    assert type(total_revenue(loaded_orders)) is float
    assert type(order_count(loaded_orders)) is int
    assert type(average_order_value(loaded_orders)) is float
    assert type(units_sold(loaded_orders)) is int
    empty = loaded_orders.iloc[0:0]
    assert type(total_revenue(empty)) is float
    assert type(average_order_value(empty)) is float


# --- missing values ---------------------------------------------------------------------


def test_a_line_with_a_missing_quantity_is_skipped_not_propagated(tmp_path):
    path = tmp_path / "gap.csv"
    path.write_text(
        "OrderID,Date,Product,Category,UnitPrice,Quantity,CustomerID,Country\n"
        "1,2025-01-01,Book,Books,10.0,2,C1,France\n"
        "2,2025-01-02,Book,Books,10.0,,C2,France\n"
    )
    gap = load_orders(path)
    assert total_revenue(gap) == pytest.approx(20.0)
    assert units_sold(gap) == 2
    assert type(units_sold(gap)) is int


# --- the sample dataset -----------------------------------------------------------------


def test_sample_dataset_numbers():
    sample = load_orders(SAMPLE_DATA)
    assert total_revenue(sample) == pytest.approx(261333.44, abs=0.005)
    assert order_count(sample) == 500
    assert units_sold(sample) == 1515
    assert average_order_value(sample) == pytest.approx(522.66688, abs=1e-5)


def test_total_revenue_prints_as_the_first_version_of_the_tool_printed_it():
    # `-T` has always printed 261333.44 for the sample dataset: no float noise at the end.
    assert str(total_revenue(load_orders(SAMPLE_DATA))) == "261333.44"
