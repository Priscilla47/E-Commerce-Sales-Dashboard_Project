import pandas as pd
import pytest

from tests.conftest import ORDER_COLUMNS


@pytest.fixture
def orders_csv(tmp_path, orders) -> str:
    """The shared fixture written to disk: revenue 1660.0, Book 6 units in 3 orders."""
    path = tmp_path / "orders.csv"
    orders.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def faulty_csv(tmp_path, typed_orders_with_problems) -> str:
    """A duplicated OrderID (lines 3 and 5, an error) and a zero quantity (line 4, a warning)."""
    path = tmp_path / "faulty.csv"
    typed_orders_with_problems.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def ranking_csv(tmp_path) -> str:
    """Apple 1 unit, Banana 5 units, Cherry 3 units (the best seller is not the first product)."""
    rows = [
        (1, "2025-01-01", "Apple", "Fruit", 1.0, 1, "C1", "France"),
        (2, "2025-01-02", "Banana", "Fruit", 1.0, 5, "C2", "France"),
        (3, "2025-01-03", "Cherry", "Fruit", 1.0, 3, "C3", "France"),
    ]
    path = tmp_path / "ranking.csv"
    pd.DataFrame(rows, columns=ORDER_COLUMNS).to_csv(path, index=False)
    return str(path)
