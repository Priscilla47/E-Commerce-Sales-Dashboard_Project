import io
from pathlib import Path

import pytest

from sales_insights.analytics.revenue import order_count, total_revenue
from sales_insights.dashboard.data_source import (
    SAMPLE_PATH,
    LoadedData,
    load_from_bytes,
    load_from_path,
    load_from_upload,
    sample_is_available,
)
from sales_insights.data.schema import SchemaError

REPOSITORY = Path(__file__).resolve().parents[2]


@pytest.fixture
def csv_bytes(orders) -> bytes:
    return orders.to_csv(index=False).encode()


@pytest.fixture
def csv_path(csv_bytes, tmp_path) -> Path:
    path = tmp_path / "orders.csv"
    path.write_bytes(csv_bytes)
    return path


# --- the sample file -----------------------------------------------------------------------


def test_the_sample_path_is_the_sample_file_of_the_repository():
    assert SAMPLE_PATH == REPOSITORY / "data" / "sample_orders.csv"
    assert sample_is_available()


def test_the_sample_loads_with_its_known_figures():
    orders, report = load_from_path(SAMPLE_PATH)
    assert order_count(orders) == 500
    assert total_revenue(orders) == pytest.approx(261333.44)
    assert report.is_valid


# --- load_from_path ------------------------------------------------------------------------


def test_load_from_path_returns_the_orders_and_the_report(csv_path):
    loaded = load_from_path(csv_path)
    assert isinstance(loaded, LoadedData)
    orders, report = loaded  # it unpacks like a pair
    assert total_revenue(orders) == 1660.0
    assert report.is_valid


def test_load_from_path_accepts_text_paths(csv_path):
    assert order_count(load_from_path(str(csv_path)).orders) == 6


def test_load_from_path_reports_data_problems_without_raising(orders, tmp_path):
    bad = orders.copy()
    bad.loc[0, "Quantity"] = -4
    path = tmp_path / "bad.csv"
    bad.to_csv(path, index=False)
    loaded = load_from_path(path)
    assert not loaded.report.is_valid
    assert len(loaded.orders) == 6


def test_load_from_path_with_missing_columns_raises_the_loader_message(orders, tmp_path):
    path = tmp_path / "short.csv"
    orders.drop(columns=["UnitPrice"]).to_csv(path, index=False)
    with pytest.raises(SchemaError, match="UnitPrice"):
        load_from_path(path)


def test_load_from_path_of_a_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_from_path(tmp_path / "nope.csv")


# --- load_from_bytes and load_from_upload --------------------------------------------------


def test_load_from_bytes_equals_load_from_path(csv_path, csv_bytes):
    by_path = load_from_path(csv_path)
    by_bytes = load_from_bytes(csv_bytes)
    assert by_bytes.orders.equals(by_path.orders)
    assert by_bytes.report.summary() == by_path.report.summary()


def test_an_upload_is_a_file_like_object_with_bytes(csv_bytes):
    loaded = load_from_upload(io.BytesIO(csv_bytes))
    assert total_revenue(loaded.orders) == 1660.0
    assert loaded.report.is_valid


def test_an_upload_already_read_is_still_loaded_whole(csv_bytes):
    upload = io.BytesIO(csv_bytes)
    upload.read()  # the position is now at the end
    assert order_count(load_from_upload(upload).orders) == 6


def test_an_upload_with_only_a_read_method_is_accepted(csv_bytes):
    class OnlyRead:
        def read(self) -> bytes:
            return csv_bytes

    assert order_count(load_from_upload(OnlyRead()).orders) == 6


def test_an_upload_with_missing_columns_raises_the_loader_message(orders):
    content = orders.drop(columns=["Country"]).to_csv(index=False).encode()
    with pytest.raises(SchemaError, match="Country"):
        load_from_upload(io.BytesIO(content))


def test_a_non_utf8_upload_raises_a_schema_error():
    content = "OrderID,Date\n1,café\n".encode("latin-1")
    with pytest.raises(SchemaError, match="UTF-8"):
        load_from_upload(io.BytesIO(content))


def test_an_empty_upload_raises_a_schema_error():
    with pytest.raises(SchemaError, match="empty"):
        load_from_upload(io.BytesIO(b""))


@pytest.mark.parametrize("content", [b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", b"%PDF-1.7\n\xff\xfe"])
def test_a_file_that_is_not_a_csv_raises_only_a_schema_error(content):
    with pytest.raises(SchemaError):
        load_from_upload(io.BytesIO(content))


# --- independence from the interface --------------------------------------------------------


def test_the_data_source_module_does_not_need_streamlit():
    source = (REPOSITORY / "src/sales_insights/dashboard/data_source.py").read_text()
    assert "streamlit" not in source
