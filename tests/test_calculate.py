"""Characterization tests for the analytics functions in calculate.py.

They record what the code does today. Known defects are written as strict xfail
tests asserting the correct behavior, so the fixes turn them into normal tests.
"""

import warnings
from pathlib import Path

import pandas as pd
import pytest

from sales_insights.analytics import legacy as cal

SAMPLE_DATA = Path(__file__).resolve().parent.parent / "data" / "sample_orders.csv"


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


@pytest.mark.parametrize(
    ("first", "second"),
    [([1, 2, 3], [1, 2]), ([1, 2], [1, 2, 3]), ([1], []), ([], [1])],
)
def test_sum_of_two_arr_mismatched_sizes_raise_value_error(first, second):
    with pytest.raises(ValueError, match="Wrong size of tables"):
        cal.sum_of_two_arr(first, second)


# --- count_orders ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("product", "expected"),
    [("Book", 3), ("Laptop", 2), ("Phone", 1), ("Unknown", 0)],
)
def test_count_orders_counts_the_order_lines_of_a_product(orders, product, expected):
    assert cal.count_orders(orders["Product"], product) == expected


def test_count_orders_counts_a_repeat_customer_every_time(orders):
    # Customer C1 bought Book twice: both orders are counted.
    assert cal.count_orders(orders["Product"], "Book") == 3


def test_count_orders_is_case_sensitive(orders):
    assert cal.count_orders(orders["Product"], "book") == 0


def test_count_orders_of_empty_data_is_zero():
    assert cal.count_orders(pd.Series([], dtype=object), "Book") == 0


def test_count_orders_returns_a_plain_integer(orders):
    assert type(cal.count_orders(orders["Product"], "Book")) is int


# --- n_number_clients -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("product", "expected"),
    [("Book", 2), ("Laptop", 2), ("Phone", 1), ("Unknown", 0)],
)
def test_n_number_clients_counts_unique_customers(orders, product, expected):
    assert cal.n_number_clients(orders["Product"], product, orders["CustomerID"]) == expected


def test_n_number_clients_counts_a_repeat_customer_once(orders):
    # Customer C1 bought Book twice, C2 once: 3 orders but 2 customers.
    assert cal.count_orders(orders["Product"], "Book") == 3
    assert cal.n_number_clients(orders["Product"], "Book", orders["CustomerID"]) == 2


def test_n_number_clients_two_different_customers_count_two():
    products = pd.Series(["Book", "Book"])
    customers = pd.Series(["C1", "C2"])
    assert cal.n_number_clients(products, "Book", customers) == 2


def test_n_number_clients_only_counts_the_customers_of_that_product(orders):
    # C3 bought Laptop and Phone, but is not a Book customer.
    assert cal.n_number_clients(orders["Product"], "Book", orders["CustomerID"]) == 2
    assert cal.n_number_clients(orders["Product"], "Phone", orders["CustomerID"]) == 1


def test_n_number_clients_is_case_sensitive(orders):
    assert cal.n_number_clients(orders["Product"], "book", orders["CustomerID"]) == 0


def test_n_number_clients_does_not_count_an_empty_customer_id():
    products = pd.Series(["Book", "Book", "Book"])
    customers = pd.Series(["C1", None, "C1"])
    assert cal.n_number_clients(products, "Book", customers) == 1


def test_n_number_clients_of_empty_data_is_zero():
    empty = pd.Series([], dtype=object)
    assert cal.n_number_clients(empty, "Book", empty) == 0


def test_n_number_clients_accepts_plain_lists():
    assert cal.n_number_clients(["Book", "Pen", "Book"], "Book", ["C1", "C2", "C1"]) == 1


def test_n_number_clients_returns_a_plain_integer(orders):
    result = cal.n_number_clients(orders["Product"], "Book", orders["CustomerID"])
    assert type(result) is int


def test_n_number_clients_mismatched_sizes_raise_value_error():
    with pytest.raises(ValueError, match="Wrong size of tables"):
        cal.n_number_clients(["Book", "Pen"], "Book", ["C1"])


def test_n_number_clients_ignores_the_row_labels_of_the_inputs():
    products = pd.Series(["Book", "Pen", "Book"], index=[10, 20, 30])
    customers = pd.Series(["C1", "C2", "C3"], index=[7, 8, 9])
    assert cal.n_number_clients(products, "Book", customers) == 2


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


def test_top_n_product_first_product_can_be_the_best_seller():
    products, quantities = products_and_quantities({"A": 9, "B": 3, "C": 1})
    assert cal.top_n_product(1, quantities, products) == ["A"]


def test_top_n_product_handles_ties():
    products, quantities = products_and_quantities({"A": 1, "B": 2, "C": 2, "D": 5})
    assert cal.top_n_product(3, quantities, products) == ["D", "B", "C"]


def test_top_n_product_tie_at_the_cut_off_keeps_the_name_that_comes_first():
    products, quantities = products_and_quantities({"A": 1, "B": 2, "C": 2, "D": 5})
    assert cal.top_n_product(2, quantities, products) == ["D", "B"]


def test_top_n_product_tie_for_first_place_is_ordered_by_name():
    products, quantities = products_and_quantities({"B": 4, "A": 4, "C": 1})
    assert cal.top_n_product(2, quantities, products) == ["A", "B"]


def test_top_n_product_tie_in_the_middle_lists_each_product_once():
    products, quantities = products_and_quantities({"A": 5, "B": 3, "C": 3, "D": 1})
    assert cal.top_n_product(4, quantities, products) == ["A", "B", "C", "D"]


def test_top_n_product_one_returns_the_single_best_seller():
    products, quantities = products_and_quantities({"A": 1, "B": 5, "C": 3})
    assert cal.top_n_product(1, quantities, products) == ["B"]


def test_top_n_product_all_products_returns_the_full_ranking(capsys):
    products, quantities = products_and_quantities({"A": 1, "B": 5, "C": 3})
    assert cal.top_n_product(3, quantities, products) == ["B", "C", "A"]
    assert capsys.readouterr().out.splitlines() == [
        "1 - B  sold  5  times",
        "2 - C  sold  3  times",
        "3 - A  sold  1  times",
    ]


def test_top_n_product_adds_up_the_quantities_of_a_products_order_lines():
    products = pd.Series(["B", "A", "B", "A", "B"])
    quantities = pd.Series([1, 2, 1, 1, 1])
    # B: 3 units over three lines, A: 3 units over two lines -> tie, A first.
    assert cal.top_n_product(2, quantities, products) == ["A", "B"]


def test_top_n_product_returns_each_name_once_as_a_list():
    products = pd.Series(["B", "A", "B", "C", "A", "B"])
    quantities = pd.Series([1, 1, 1, 1, 1, 1])
    result = cal.top_n_product(3, quantities, products)
    assert isinstance(result, list)
    assert result == ["B", "A", "C"]


def test_top_n_product_single_product():
    products, quantities = products_and_quantities({"Only": 4})
    assert cal.top_n_product(1, quantities, products) == ["Only"]


def test_top_n_product_negative_number_exits_with_code_84(capsys):
    products, quantities = products_and_quantities({"A": 1, "B": 5})
    with pytest.raises(SystemExit) as error:
        cal.top_n_product(-1, quantities, products)
    assert error.value.code == 84
    assert "Wrong number of products" in capsys.readouterr().out


def test_top_n_product_empty_data_returns_an_empty_list_for_zero(capsys):
    empty = pd.Series([], dtype=object)
    assert cal.top_n_product(0, empty, empty) == []
    assert capsys.readouterr().out == ""


def test_top_n_product_empty_data_exits_with_code_84_for_one():
    empty = pd.Series([], dtype=object)
    with pytest.raises(SystemExit) as error:
        cal.top_n_product(1, empty, empty)
    assert error.value.code == 84


def test_top_n_product_on_the_sample_dataset(capsys):
    sales = pd.read_csv(SAMPLE_DATA)
    assert cal.top_n_product(3, sales["Quantity"], sales["Product"]) == [
        "Smartphone",
        "Book",
        "Desk Lamp",
    ]
    assert capsys.readouterr().out.splitlines() == [
        "1 - Smartphone  sold  186  times",
        "2 - Book  sold  176  times",
        "3 - Desk Lamp  sold  175  times",
    ]


# --- sales_over_time ------------------------------------------------------------------


def test_sales_over_time_is_a_stub_returning_its_input():
    assert cal.sales_over_time(2025) == 2025
    assert cal.sales_over_time("2025") == "2025"


def test_top_n_product_ignores_categories_that_nobody_bought():
    # A product column stored as a category keeps the unused labels; they are not products sold.
    products = pd.Series(["A", "B", "A"], dtype=pd.CategoricalDtype(["A", "B", "Unused"]))
    quantities = pd.Series([1, 5, 2])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert cal.top_n_product(2, quantities, products) == ["B", "A"]
    with pytest.raises(SystemExit):
        cal.top_n_product(3, quantities, products)
