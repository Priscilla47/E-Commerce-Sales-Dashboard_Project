from pathlib import Path

import pandas as pd
import pytest
from pandas.api import types as pdt

from sales_insights.data.loader import load_orders
from sales_insights.data.schema import COLUMNS, SchemaError

SAMPLE_DATA = Path(__file__).resolve().parents[2] / "data" / "sample_orders.csv"
HEADER = "OrderID,Date,Product,Category,UnitPrice,Quantity,CustomerID,Country"


def write_csv(tmp_path, *lines, header=HEADER):
    path = tmp_path / "orders.csv"
    path.write_text("\n".join([header, *lines]) + "\n")
    return path


@pytest.fixture
def valid_csv(tmp_path):
    return write_csv(
        tmp_path,
        "1000,2025-01-05,Book,Books,10.0,2,C1,France",
        "1001,2025-01-20,Laptop,Electronics,500.0,1,C2,UK",
        "1002,2025-02-03,Book,Books,10.5,3,C1,France",
    )


# --- valid files ------------------------------------------------------------------------


def test_valid_file_loads_with_the_right_dtypes(valid_csv):
    orders = load_orders(valid_csv)
    assert pdt.is_integer_dtype(orders["OrderID"])
    assert pdt.is_integer_dtype(orders["Quantity"])
    assert pdt.is_float_dtype(orders["UnitPrice"])
    assert pdt.is_datetime64_any_dtype(orders["Date"])
    assert orders["Product"].tolist() == ["Book", "Laptop", "Book"]
    assert orders["Date"].iloc[1] == pd.Timestamp("2025-01-20")


def test_revenue_is_unit_price_times_quantity(valid_csv):
    orders = load_orders(valid_csv)
    assert orders["Revenue"].tolist() == [20.0, 500.0, 31.5]


def test_columns_come_in_schema_order_then_revenue(valid_csv):
    assert list(load_orders(valid_csv).columns) == [*COLUMNS, "Revenue"]


def test_columns_in_a_different_order_are_reordered(tmp_path):
    path = tmp_path / "shuffled.csv"
    path.write_text(
        "Country,Quantity,UnitPrice,Category,Product,Date,CustomerID,OrderID\n"
        "France,2,10.0,Books,Book,2025-01-05,C1,1000\n"
    )
    orders = load_orders(path)
    assert list(orders.columns) == [*COLUMNS, "Revenue"]
    assert orders["Revenue"].tolist() == [20.0]


def test_accepts_a_string_path_and_a_path_object(valid_csv):
    assert load_orders(str(valid_csv)).equals(load_orders(Path(valid_csv)))


def test_extra_columns_are_kept_after_the_schema_columns(tmp_path):
    path = write_csv(
        tmp_path,
        "1000,2025-01-05,Book,Books,10.0,2,C1,France,gift",
        header=HEADER + ",Notes",
    )
    orders = load_orders(path)
    assert list(orders.columns) == [*COLUMNS, "Notes", "Revenue"]
    assert orders["Notes"].tolist() == ["gift"]


def test_an_existing_revenue_column_is_recomputed(tmp_path):
    path = write_csv(
        tmp_path,
        "1000,2025-01-05,Book,Books,10.0,2,C1,France,999",
        header=HEADER + ",Revenue",
    )
    assert load_orders(path)["Revenue"].tolist() == [20.0]


def test_the_sample_dataset_loads():
    orders = load_orders(SAMPLE_DATA)
    assert len(orders) == 500
    assert list(orders.columns) == [*COLUMNS, "Revenue"]
    assert orders["Revenue"].sum() == pytest.approx(261333.44)


# --- missing values ---------------------------------------------------------------------


def test_empty_cells_are_kept_as_missing_values(tmp_path):
    path = write_csv(tmp_path, "1000,2025-01-05,Book,Books,10.0,,C1,France")
    orders = load_orders(path)
    assert pd.isna(orders["Quantity"].iloc[0])
    assert pd.isna(orders["Revenue"].iloc[0])
    assert pdt.is_integer_dtype(orders["Quantity"])


def test_na_text_is_a_value_not_a_missing_cell(tmp_path):
    path = write_csv(tmp_path, "1000,2025-01-05,Book,Books,10.0,2,C1,NA")
    assert load_orders(path)["Country"].tolist() == ["NA"]


# --- file problems ----------------------------------------------------------------------


def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="missing.csv"):
        load_orders(tmp_path / "missing.csv")


def test_a_directory_is_not_an_orders_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_orders(tmp_path)


def test_zero_byte_file_raises_a_clear_error(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("")
    with pytest.raises(SchemaError, match="empty"):
        load_orders(path)


def test_header_only_file_gives_an_empty_table_with_all_columns(tmp_path):
    orders = load_orders(write_csv(tmp_path))
    assert len(orders) == 0
    assert list(orders.columns) == [*COLUMNS, "Revenue"]


# --- schema problems --------------------------------------------------------------------


def test_missing_column_raises_schema_error_naming_it(tmp_path):
    path = write_csv(
        tmp_path,
        "1000,2025-01-05,Book,Books,10.0,C1,France",
        header="OrderID,Date,Product,Category,UnitPrice,CustomerID,Country",
    )
    with pytest.raises(SchemaError, match="Quantity"):
        load_orders(path)


def test_several_missing_columns_are_all_listed(tmp_path):
    path = write_csv(tmp_path, "1000,2025-01-05,Book", header="OrderID,Date,Product")
    with pytest.raises(SchemaError) as error:
        load_orders(path)
    for column in ("Category", "UnitPrice", "Quantity", "CustomerID", "Country"):
        assert column in str(error.value)
    assert "Product" not in str(error.value)


# --- value problems ---------------------------------------------------------------------


def test_invalid_date_raises_with_line_and_value(tmp_path):
    path = write_csv(
        tmp_path,
        "1000,2025-01-05,Book,Books,10.0,2,C1,France",
        "1001,not-a-date,Laptop,Electronics,500.0,1,C2,UK",
    )
    with pytest.raises(SchemaError, match=r"'Date'.*line 3.*'not-a-date'"):
        load_orders(path)


def test_non_numeric_price_raises(tmp_path):
    path = write_csv(tmp_path, "1000,2025-01-05,Book,Books,ten,2,C1,France")
    with pytest.raises(SchemaError, match=r"'UnitPrice'.*line 2.*'ten'"):
        load_orders(path)


def test_fractional_quantity_raises(tmp_path):
    path = write_csv(tmp_path, "1000,2025-01-05,Book,Books,10.0,2.5,C1,France")
    with pytest.raises(SchemaError, match=r"'Quantity'.*whole number.*'2.5'"):
        load_orders(path)


def test_several_invalid_values_report_the_first_and_the_count(tmp_path):
    path = write_csv(
        tmp_path,
        "1000,bad,Book,Books,10.0,2,C1,France",
        "1001,worse,Book,Books,10.0,2,C1,France",
    )
    with pytest.raises(SchemaError, match=r"line 2.*'bad'.*\(and 1 more\)"):
        load_orders(path)
