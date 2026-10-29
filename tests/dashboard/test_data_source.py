import io
from pathlib import Path

import pytest

from sales_insights.analytics.revenue import order_count, total_revenue
from sales_insights.dashboard.data_source import (
    SAMPLE_PATH,
    LoadedData,
    count_problems,
    describe_problems,
    load_from_bytes,
    load_from_path,
    load_from_upload,
    sample_is_available,
)
from sales_insights.data.schema import SchemaError
from sales_insights.data.validation import ERROR, WARNING, Issue, ValidationReport

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


# --- describe_problems -----------------------------------------------------------------------


def report_with(
    rows: list[int], severity: str = ERROR, message: str = "Bad value"
) -> ValidationReport:
    return ValidationReport([Issue("negative_value", severity, message, tuple(rows), "Quantity")])


def test_no_problem_gives_no_line():
    assert describe_problems(ValidationReport()) == []


def test_one_problem_is_one_line_with_its_line_number():
    report = report_with([12], message="Negative value in column 'Quantity'")
    assert describe_problems(report) == ["line 12: Negative value in column 'Quantity'"]


def test_an_issue_on_several_lines_gives_one_message_per_line():
    report = report_with([2, 3], message="Duplicate OrderID 1")
    assert describe_problems(report) == [
        "line 2: Duplicate OrderID 1",
        "line 3: Duplicate OrderID 1",
    ]


def test_exactly_twenty_problems_are_all_listed_without_a_trailer():
    lines = describe_problems(report_with(list(range(2, 22))))
    assert len(lines) == 20
    assert not lines[-1].startswith("and ")


def test_twenty_one_problems_list_twenty_and_one_more():
    lines = describe_problems(report_with(list(range(2, 23))))
    assert len(lines) == 21
    assert lines[:20] == [f"line {n}: Bad value" for n in range(2, 22)]
    assert lines[20] == "and 1 more"


def test_fifty_problems_list_twenty_and_thirty_more():
    lines = describe_problems(report_with(list(range(2, 52))))
    assert len(lines) == 21
    assert lines[-1] == "and 30 more"


def test_the_limit_can_be_changed():
    lines = describe_problems(report_with([2, 3, 4, 5]), limit=2)
    assert lines == ["line 2: Bad value", "line 3: Bad value", "and 2 more"]


def test_problems_are_ordered_by_line_number():
    report = ValidationReport(
        [
            Issue("missing_value", ERROR, "Missing value in column 'UnitPrice'", (9,), "UnitPrice"),
            Issue("negative_value", ERROR, "Negative value in column 'Quantity'", (4,), "Quantity"),
        ]
    )
    assert describe_problems(report) == [
        "line 4: Negative value in column 'Quantity'",
        "line 9: Missing value in column 'UnitPrice'",
    ]


def test_the_errors_are_listed_by_default_and_the_warnings_on_request():
    report = ValidationReport(
        [
            Issue("negative_value", ERROR, "An error", (2,), None),
            Issue("zero_quantity", WARNING, "A warning", (3,), None),
        ]
    )
    assert describe_problems(report) == ["line 2: An error"]
    assert describe_problems(report, severity=WARNING) == ["line 3: A warning"]


def test_a_real_report_is_described_line_by_line(orders, tmp_path):
    bad = orders.copy()
    bad.loc[0, "Quantity"] = -4
    bad.loc[3, "UnitPrice"] = None
    path = tmp_path / "bad.csv"
    bad.to_csv(path, index=False)
    assert describe_problems(load_from_path(path).report) == [
        "line 2: Negative value in column 'Quantity'",
        "line 5: Missing value in column 'UnitPrice'",
    ]


# --- no file can make the loading fail with anything but a SchemaError -------------------------


def damaged_versions(content: bytes, count: int = 400) -> list[bytes]:
    import random

    rng = random.Random(44)
    versions = [b"", b"\n", b",", b'"', b"\xef\xbb\xbf", b"\x00" * 50, content[:7], content * 2]
    for _ in range(count):
        data = bytearray(content)
        for _ in range(rng.randint(1, 8)):
            kind = rng.choice(["flip", "cut", "insert", "delete", "quote", "newline"])
            at = rng.randrange(len(data)) if data else 0
            if kind == "flip" and data:
                data[at] = rng.randrange(256)
            elif kind == "cut":
                del data[at:]
            elif kind == "insert":
                data[at:at] = bytes(rng.randrange(256) for _ in range(rng.randint(1, 5)))
            elif kind == "delete" and data:
                del data[at : at + rng.randint(1, 6)]
            elif kind == "quote":
                data[at:at] = b'"'
            else:
                data[at:at] = b"\r\n"
        versions.append(bytes(data))
    return versions


def test_damaged_files_load_or_raise_only_a_schema_error(csv_bytes):
    for content in damaged_versions(csv_bytes):
        try:
            loaded = load_from_bytes(content)
        except SchemaError:
            continue
        assert isinstance(loaded.report, ValidationReport)


def test_damaged_sample_files_load_or_raise_only_a_schema_error():
    content = SAMPLE_PATH.read_bytes()[:3000]
    for damaged in damaged_versions(content, count=150):
        try:
            load_from_bytes(damaged)
        except SchemaError:
            pass


def test_count_problems_counts_lines_not_findings():
    report = ValidationReport(
        [
            Issue("negative_value", ERROR, "Negative", (2, 3, 4), "Quantity"),
            Issue("missing_value", ERROR, "Missing", (9,), "UnitPrice"),
            Issue("zero_quantity", WARNING, "Zero", (5, 6), "Quantity"),
        ]
    )
    assert count_problems(report) == 4
    assert count_problems(report, severity=WARNING) == 2
    assert count_problems(ValidationReport()) == 0


def test_count_problems_is_the_number_of_lines_describe_problems_would_list_without_a_limit():
    report = report_with(list(range(2, 52)))
    assert count_problems(report) == len(describe_problems(report, limit=1000)) == 50
