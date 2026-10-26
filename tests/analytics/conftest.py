import pandas as pd
import pytest

from sales_insights.data.loader import load_orders


@pytest.fixture
def loaded_orders(orders, tmp_path) -> pd.DataFrame:
    """The shared orders fixture loaded the way the application loads a file.

    It has typed columns and the computed ``Revenue`` column, one value per line:
    20, 500, 30, 600, 10 and 500 (total 1660.0, 6 orders, 10 units).
    """
    path = tmp_path / "orders.csv"
    orders.to_csv(path, index=False)
    return load_orders(path)
