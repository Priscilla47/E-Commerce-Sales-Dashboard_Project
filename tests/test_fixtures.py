from tests.conftest import ORDER_COLUMNS


def test_orders_fixture_shape(orders):
    assert list(orders.columns) == ORDER_COLUMNS
    assert len(orders.columns) == 8
    assert len(orders) == 6


def test_orders_fixture_totals_match_documented_values(orders):
    revenue = (orders["UnitPrice"] * orders["Quantity"]).sum()
    assert revenue == 1660.0
    assert orders["Quantity"].sum() == 10
