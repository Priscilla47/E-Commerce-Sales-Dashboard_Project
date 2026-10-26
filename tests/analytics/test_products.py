import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sales_insights.analytics.products import (
    customers_for,
    orders_for,
    top_products,
    unique_products,
    units_sold_for,
)
from sales_insights.data.loader import load_orders

SAMPLE_DATA = Path(__file__).resolve().parents[2] / "data" / "sample_orders.csv"


def lines(rows: list[tuple]) -> pd.DataFrame:
    """A minimal loaded table from (Product, Quantity, CustomerID) rows."""
    return pd.DataFrame(rows, columns=["Product", "Quantity", "CustomerID"])


def totals(per_product: dict[str, int]) -> pd.DataFrame:
    """One order line per product, so the units of a product are the given total."""
    return lines([(name, units, f"C{i}") for i, (name, units) in enumerate(per_product.items())])


def ranking(df: pd.DataFrame, n: int) -> list[str]:
    return top_products(df, n)["Product"].tolist()


# --- unique_products --------------------------------------------------------------------


def test_unique_products_are_sorted_and_listed_once(loaded_orders):
    assert unique_products(loaded_orders) == ["Book", "Laptop", "Phone"]


def test_unique_products_ignores_repeats_and_input_order():
    data = lines([("b", 1, "C1"), ("a", 1, "C1"), ("b", 1, "C1"), ("a", 1, "C1")])
    assert unique_products(data) == ["a", "b"]


def test_unique_products_single_product():
    assert unique_products(lines([("only", 1, "C1")])) == ["only"]


def test_unique_products_of_empty_data_is_an_empty_list():
    assert unique_products(lines([])) == []


def test_unique_products_leaves_out_a_missing_name():
    assert unique_products(lines([("a", 1, "C1"), (None, 1, "C1")])) == ["a"]


def test_unique_products_are_case_sensitive():
    assert unique_products(lines([("a", 1, "C1"), ("A", 1, "C1")])) == ["A", "a"]


def test_unique_products_are_plain_strings(loaded_orders):
    assert all(type(name) is str for name in unique_products(loaded_orders))


# --- units_sold_for ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("product", "expected"),
    [("Book", 6), ("Laptop", 2), ("Phone", 2), ("Unknown", 0)],
)
def test_units_sold_for_adds_up_the_quantities_of_a_product(loaded_orders, product, expected):
    assert units_sold_for(loaded_orders, product) == expected


def test_units_sold_for_is_case_sensitive(loaded_orders):
    assert units_sold_for(loaded_orders, "book") == 0


def test_units_sold_for_empty_data_is_zero():
    assert units_sold_for(lines([]), "Book") == 0


def test_units_sold_for_skips_a_missing_quantity():
    data = lines([("Book", 2, "C1"), ("Book", None, "C2")])
    assert units_sold_for(data, "Book") == 2


def test_units_sold_for_returns_a_plain_integer(loaded_orders):
    assert type(units_sold_for(loaded_orders, "Book")) is int


# --- orders_for -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("product", "expected"),
    [("Book", 3), ("Laptop", 2), ("Phone", 1), ("Unknown", 0)],
)
def test_orders_for_counts_the_order_lines_of_a_product(loaded_orders, product, expected):
    assert orders_for(loaded_orders, product) == expected


def test_orders_for_counts_a_repeat_customer_every_time(loaded_orders):
    # Customer C1 bought Book twice: both orders are counted.
    assert orders_for(loaded_orders, "Book") == 3


def test_orders_for_is_case_sensitive(loaded_orders):
    assert orders_for(loaded_orders, "book") == 0


def test_orders_for_empty_data_is_zero():
    assert orders_for(lines([]), "Book") == 0


def test_orders_for_returns_a_plain_integer(loaded_orders):
    assert type(orders_for(loaded_orders, "Book")) is int


# --- customers_for ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("product", "expected"),
    [("Book", 2), ("Laptop", 2), ("Phone", 1), ("Unknown", 0)],
)
def test_customers_for_counts_unique_customers(loaded_orders, product, expected):
    assert customers_for(loaded_orders, product) == expected


def test_customers_for_counts_a_repeat_customer_once(loaded_orders):
    # Customer C1 bought Book twice, C2 once: 3 orders but 2 customers.
    assert orders_for(loaded_orders, "Book") == 3
    assert customers_for(loaded_orders, "Book") == 2


def test_customers_for_two_different_customers_count_two():
    assert customers_for(lines([("Book", 1, "C1"), ("Book", 1, "C2")]), "Book") == 2


def test_customers_for_only_counts_the_customers_of_that_product(loaded_orders):
    # C3 bought Laptop and Phone, but is not a Book customer.
    assert customers_for(loaded_orders, "Book") == 2
    assert customers_for(loaded_orders, "Phone") == 1


def test_customers_for_is_case_sensitive(loaded_orders):
    assert customers_for(loaded_orders, "book") == 0


def test_customers_for_does_not_count_an_empty_customer_id():
    data = lines([("Book", 1, "C1"), ("Book", 1, None), ("Book", 1, "C1")])
    assert customers_for(data, "Book") == 1


def test_customers_for_empty_data_is_zero():
    assert customers_for(lines([]), "Book") == 0


def test_customers_for_returns_a_plain_integer(loaded_orders):
    assert type(customers_for(loaded_orders, "Book")) is int


def test_customers_for_ignores_the_row_labels():
    data = lines([("Book", 1, "C1"), ("Pen", 1, "C2"), ("Book", 1, "C3")])
    data.index = [10, 20, 30]
    assert customers_for(data, "Book") == 2


# --- top_products -----------------------------------------------------------------------


def test_top_products_returns_the_best_sellers_in_order(loaded_orders):
    result = top_products(loaded_orders, 2)
    assert list(result.columns) == ["Product", "units"]
    assert result["Product"].tolist() == ["Book", "Laptop"]
    assert result["units"].tolist() == [6, 2]


def test_top_products_units_are_integers_and_the_index_is_clean(loaded_orders):
    result = top_products(loaded_orders, 3)
    assert result["units"].dtype == np.int64
    assert result.index.tolist() == [0, 1, 2]


def test_top_products_the_first_product_alphabetically_can_be_the_best_seller():
    assert ranking(totals({"A": 9, "B": 3, "C": 1}), 1) == ["A"]


def test_top_products_ties_are_ordered_by_name_across_the_whole_ranking():
    data = totals({"A": 1, "B": 2, "C": 2, "D": 5})
    assert ranking(data, 3) == ["D", "B", "C"]


def test_top_products_tie_at_the_cut_off_keeps_the_name_that_comes_first():
    assert ranking(totals({"A": 1, "B": 2, "C": 2, "D": 5}), 2) == ["D", "B"]


def test_top_products_tie_for_first_place_is_ordered_by_name():
    assert ranking(totals({"B": 4, "A": 4, "C": 1}), 2) == ["A", "B"]


def test_top_products_tie_in_the_middle_lists_each_product_once():
    assert ranking(totals({"A": 5, "B": 3, "C": 3, "D": 1}), 4) == ["A", "B", "C", "D"]


def test_top_products_many_ties_stay_ordered_by_name():
    # Many products over a few distinct totals: an unstable sort would shuffle the ties.
    sold = {f"P{i:03d}": (i * 7) % 5 + 1 for i in range(300)}
    expected = [name for name, _ in sorted(sold.items(), key=lambda item: (-item[1], item[0]))]
    data = totals(dict(reversed(list(sold.items()))))
    assert ranking(data, 300) == expected
    assert ranking(data, 40) == expected[:40]


def test_top_products_one_returns_the_single_best_seller():
    assert ranking(totals({"A": 1, "B": 5, "C": 3}), 1) == ["B"]


def test_top_products_all_products_returns_the_full_ranking():
    assert ranking(totals({"A": 1, "B": 5, "C": 3}), 3) == ["B", "C", "A"]


def test_top_products_adds_up_the_quantities_of_a_products_order_lines():
    data = lines([("B", 1, "C1"), ("A", 2, "C1"), ("B", 1, "C1"), ("A", 1, "C1"), ("B", 1, "C1")])
    # B: 3 units over three lines, A: 3 units over two lines -> tie, A first.
    assert top_products(data, 2).to_dict("list") == {"Product": ["A", "B"], "units": [3, 3]}


def test_top_products_single_product():
    assert ranking(totals({"Only": 4}), 1) == ["Only"]


def test_top_products_zero_returns_an_empty_table_with_the_columns():
    result = top_products(totals({"A": 1, "B": 5}), 0)
    assert result.empty
    assert list(result.columns) == ["Product", "units"]


@pytest.mark.parametrize("n", [-1, 3, 100])
def test_top_products_an_n_out_of_range_raises_value_error(n):
    with pytest.raises(ValueError, match="Wrong number of products"):
        top_products(totals({"A": 1, "B": 5}), n)


@pytest.mark.parametrize("n", [np.int64(2), np.int32(2), np.uint8(2), np.intp(2)])
def test_top_products_accepts_numpy_integers_like_python_ones(n):
    # Counts computed with numpy or pandas (a max, a slider, a length) are numpy integers.
    data = totals({"A": 1, "B": 5, "C": 3})
    pd.testing.assert_frame_equal(top_products(data, n), top_products(data, 2))


@pytest.mark.parametrize("n", [1.0, np.float64(2.0), "2", None, True, np.True_])
def test_top_products_an_n_that_is_not_a_whole_number_raises_type_error(n):
    with pytest.raises(TypeError, match="whole number"):
        top_products(totals({"A": 1, "B": 5}), n)


def test_top_products_of_empty_data_is_empty_for_zero_and_an_error_otherwise():
    assert top_products(lines([]), 0).empty
    with pytest.raises(ValueError, match="Wrong number of products"):
        top_products(lines([]), 1)


def test_top_products_counts_a_missing_quantity_as_no_units():
    data = lines([("A", None, "C1"), ("B", 3, "C2")])
    assert top_products(data, 2).to_dict("list") == {"Product": ["B", "A"], "units": [3, 0]}


def test_top_products_ignores_unused_categories_of_a_category_column():
    # A product column stored as a category keeps the unused labels; they are not products sold.
    products = pd.Series(["A", "B", "A"], dtype=pd.CategoricalDtype(["A", "B", "Unused"]))
    data = pd.DataFrame({"Product": products, "Quantity": [1, 5, 2]})
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert ranking(data, 2) == ["B", "A"]
    with pytest.raises(ValueError, match="Wrong number of products"):
        top_products(data, 3)


def test_top_products_does_not_modify_the_input(loaded_orders):
    before = loaded_orders.copy()
    top_products(loaded_orders, 2)
    pd.testing.assert_frame_equal(loaded_orders, before)


# --- the sample dataset -----------------------------------------------------------------


def test_sample_dataset_figures():
    sample = load_orders(SAMPLE_DATA)
    assert len(unique_products(sample)) == 10
    assert top_products(sample, 3).to_dict("list") == {
        "Product": ["Smartphone", "Book", "Desk Lamp"],
        "units": [186, 176, 175],
    }
    # 46 Laptop orders, but one customer bought it twice: 45 customers.
    assert units_sold_for(sample, "Laptop") == 147
    assert orders_for(sample, "Laptop") == 46
    assert customers_for(sample, "Laptop") == 45
