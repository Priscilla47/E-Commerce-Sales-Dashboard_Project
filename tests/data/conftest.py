import pandas as pd
import pytest


@pytest.fixture
def typed_orders(orders) -> pd.DataFrame:
    """The shared orders fixture with its dates parsed, as the loader would return them."""
    typed = orders.copy()
    typed["Date"] = pd.to_datetime(typed["Date"])
    return typed
