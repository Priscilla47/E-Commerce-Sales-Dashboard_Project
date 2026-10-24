"""Characterization tests for the analytics functions in calculate.py.

They record what the code does today. Known defects are written as strict xfail
tests asserting the correct behavior, so the fixes turn them into normal tests.
"""

import pandas as pd
import pytest

from sales_insights.analytics import legacy as cal


def products_and_quantities(totals: dict[str, int]) -> tuple[pd.Series, pd.Series]:
    """One order line per product, so the per-product quantity is the given total."""
    return pd.Series(list(totals)), pd.Series(list(totals.values()))


# --- sum_of_two_arr -------------------------------------------------------------------


def test_sum_of_two_arr_computes_total_revenue(orders):
    assert cal.sum_of_two_arr(orders["Quantity"], orders["UnitPrice"]) == pytest.approx(1660.0)


def test_sum_of_two_arr_accepts_plain_lists():
    assert cal.sum_of_two_arr([1, 2], [3, 4]) == 11


def test_sum_of_two_arr_empty_arrays_return_zero():
    assert cal.sum_of_two_arr([], []) == 0


def test_sum_of_two_arr_single_element():
    assert cal.sum_of_two_arr([3], [2.5]) == pytest.approx(7.5)


@pytest.mark.xfail(
    strict=True,
    raises=NameError,
    reason="known bug: 'Value_error' does not exist, so a ValueError is never raised",
)
def test_sum_of_two_arr_mismatched_sizes_raise_value_error():
    with pytest.raises(ValueError, match="Wrong size of tables"):
        cal.sum_of_two_arr([1, 2, 3], [1, 2])


# --- n_number_clients -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("product", "expected"),
    [("Book", 3), ("Laptop", 2), ("Phone", 1), ("Unknown", 0)],
)
def test_n_number_clients_counts_matching_rows(orders, product, expected):
    assert cal.n_number_clients(orders["Product"], product) == expected


def test_n_number_clients_counts_orders_not_unique_customers(orders):
    # Customer C1 bought Book twice, yet both orders are counted (see the fix issue).
    book_customers = orders.loc[orders["Product"] == "Book", "CustomerID"]
    assert book_customers.nunique() == 2
    assert cal.n_number_clients(orders["Product"], "Book") == 3


def test_n_number_clients_is_case_sensitive(orders):
    assert cal.n_number_clients(orders["Product"], "book") == 0


# --- compare_it -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("element", "items", "expected"),
    [("b", ["a", "b", "c"], 1), ("z", ["a", "b", "c"], 0), ("a", [], 0), (2, [1, 2], 1)],
)
def test_compare_it(element, items, expected):
    assert cal.compare_it(element, items) == expected


# --- n_items --------------------------------------------------------------------------


def test_n_items_returns_sorted_unique_products(orders):
    assert cal.n_items(orders["Product"]) == ["Book", "Laptop", "Phone"]


def test_n_items_lists_each_product_once():
    products = pd.Series(["b", "a", "b", "a", "b"])
    assert cal.n_items(products) == ["a", "b"]


def test_n_items_single_product():
    assert cal.n_items(pd.Series(["only"])) == ["only"]


def test_n_items_fails_on_empty_input():
    with pytest.raises((IndexError, KeyError)):
        cal.n_items(pd.Series([], dtype=object))


# --- num_products ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("product", "expected"),
    [("Book", 6), ("Laptop", 2), ("Phone", 2), ("Unknown", 0)],
)
def test_num_products_sums_quantities_per_product(orders, product, expected):
    assert cal.num_products(product, orders["Quantity"], orders["Product"]) == expected


# --- compare_n_pdt --------------------------------------------------------------------


def test_compare_n_pdt_returns_index_of_element():
    assert cal.compare_n_pdt(7, [3, 5, 7]) == 2


def test_compare_n_pdt_returns_zero_when_not_found():
    assert cal.compare_n_pdt(9, [3, 5, 7]) == 0


def test_compare_n_pdt_returns_zero_for_first_element_too():
    # Same answer for "not found" and "found first": the ambiguity behind the top-N bug.
    assert cal.compare_n_pdt(3, [3, 5, 7]) == 0


def test_compare_n_pdt_empty_list_returns_zero():
    assert cal.compare_n_pdt(1, []) == 0


# --- top_n_product --------------------------------------------------------------------


def test_top_n_product_returns_best_sellers_in_order():
    products, quantities = products_and_quantities({"A": 1, "B": 5, "C": 3})
    assert cal.top_n_product(2, quantities, products) == ["B", "C"]


def test_top_n_product_prints_the_ranking(capsys):
    products, quantities = products_and_quantities({"A": 1, "B": 5, "C": 3})
    cal.top_n_product(2, quantities, products)
    assert capsys.readouterr().out.splitlines() == [
        "1 - B  sold  5  times",
        "2 - C  sold  3  times",
    ]


def test_top_n_product_zero_returns_empty_list_and_prints_nothing(capsys):
    products, quantities = products_and_quantities({"A": 1, "B": 5})
    assert cal.top_n_product(0, quantities, products) == []
    assert capsys.readouterr().out == ""


def test_top_n_product_too_many_exits_with_code_84(capsys):
    products, quantities = products_and_quantities({"A": 1, "B": 5})
    with pytest.raises(SystemExit) as error:
        cal.top_n_product(3, quantities, products)
    assert error.value.code == 84
    assert "Wrong number of products" in capsys.readouterr().out


@pytest.mark.xfail(
    strict=True,
    reason="known bug: the first product (alphabetical) is never returned",
)
def test_top_n_product_first_product_can_be_the_best_seller():
    products, quantities = products_and_quantities({"A": 9, "B": 3, "C": 1})
    assert cal.top_n_product(1, quantities, products) == ["A"]


@pytest.mark.xfail(
    strict=True,
    reason="known bug: tied products are listed twice and another product is dropped",
)
def test_top_n_product_handles_ties():
    products, quantities = products_and_quantities({"A": 1, "B": 2, "C": 2, "D": 5})
    assert cal.top_n_product(3, quantities, products) == ["D", "B", "C"]
