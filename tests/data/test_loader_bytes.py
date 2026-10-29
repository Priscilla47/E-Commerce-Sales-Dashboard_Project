import pandas as pd
import pytest

from sales_insights.data.loader import load_orders, load_orders_from_bytes
from sales_insights.data.schema import SchemaError


def test_bytes_load_the_same_table_as_the_file(orders, tmp_path):
    path = tmp_path / "orders.csv"
    orders.to_csv(path, index=False)
    from_file = load_orders(path)
    from_bytes = load_orders_from_bytes(path.read_bytes())
    pd.testing.assert_frame_equal(from_bytes, from_file)
    assert from_bytes["Revenue"].sum() == 1660.0


def test_a_bytearray_and_a_memoryview_are_accepted(orders, tmp_path):
    content = orders.to_csv(index=False).encode()
    expected = load_orders_from_bytes(content)
    pd.testing.assert_frame_equal(load_orders_from_bytes(bytearray(content)), expected)
    pd.testing.assert_frame_equal(load_orders_from_bytes(memoryview(content)), expected)


def test_empty_bytes_say_the_file_is_empty():
    with pytest.raises(SchemaError, match="empty"):
        load_orders_from_bytes(b"")


def test_missing_columns_are_named(orders):
    content = orders.drop(columns=["UnitPrice"]).to_csv(index=False).encode()
    with pytest.raises(SchemaError, match="UnitPrice"):
        load_orders_from_bytes(content)


def test_bytes_that_are_not_utf8_text_are_a_schema_error():
    with pytest.raises(SchemaError, match="UTF-8"):
        load_orders_from_bytes("OrderID,Date\n1,café\n".encode("latin-1"))


def test_a_text_instead_of_bytes_is_refused():
    with pytest.raises(TypeError, match="bytes"):
        load_orders_from_bytes("OrderID,Date\n")
