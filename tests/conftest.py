"""Shared test fixtures."""

import pandas as pd
import pytest

from sales_insights.data.loader import load_orders

ORDER_COLUMNS = [
    "OrderID",
    "Date",
    "Product",
    "Category",
    "UnitPrice",
    "Quantity",
    "CustomerID",
    "Country",
]


@pytest.fixture
def orders() -> pd.DataFrame:
    """A small orders table whose results can be checked by hand.

    Totals:
      - Book:   6 units, revenue 60.0    (3 orders, customers C1 and C2)
      - Laptop: 2 units, revenue 1000.0  (2 orders, customers C2 and C3)
      - Phone:  2 units, revenue 600.0   (1 order, customer C3)
      - All products: 10 units, revenue 1660.0
    Laptop and Phone are tied at 2 units, which is useful to test ranking ties.
    """
    rows = [
        (1000, "2025-01-05", "Book", "Books", 10.0, 2, "C1", "France"),
        (1001, "2025-01-20", "Laptop", "Electronics", 500.0, 1, "C2", "UK"),
        (1002, "2025-02-03", "Book", "Books", 10.0, 3, "C1", "France"),
        (1003, "2025-02-14", "Phone", "Electronics", 300.0, 2, "C3", "UK"),
        (1004, "2025-02-20", "Book", "Books", 10.0, 1, "C2", "UK"),
        (1005, "2025-03-01", "Laptop", "Electronics", 500.0, 1, "C3", "France"),
    ]
    return pd.DataFrame(rows, columns=ORDER_COLUMNS)


@pytest.fixture
def typed_orders_with_problems(orders) -> pd.DataFrame:
    """The orders fixture with a duplicated OrderID (lines 3 and 5) and a zero quantity (line 4)."""
    typed = orders.copy()
    typed["Date"] = pd.to_datetime(typed["Date"])
    typed.loc[3, "OrderID"] = typed.loc[1, "OrderID"]
    typed.loc[2, "Quantity"] = 0
    return typed


@pytest.fixture
def loaded_orders(orders, tmp_path) -> pd.DataFrame:
    """The shared orders fixture loaded the way the application loads a file.

    It has typed columns and the computed ``Revenue`` column, one value per line:
    20, 500, 30, 600, 10 and 500 (total 1660.0, 6 orders, 10 units).
    """
    path = tmp_path / "orders.csv"
    orders.to_csv(path, index=False)
    return load_orders(path)
