import contextlib
import signal
from pathlib import Path

import pandas as pd
import pytest

from sales_insights.data.loader import load_orders
from sales_insights.data.schema import SchemaError
from sales_insights.data.validation import RULES, validate_orders

SAMPLE_DATA = Path(__file__).resolve().parents[2] / "data" / "sample_orders.csv"
TODAY = pd.Timestamp("2025-12-31")


def validate(orders):
    return validate_orders(orders, today=TODAY)


def codes(report):
    return [issue.code for issue in report.issues]


# --- clean data -------------------------------------------------------------------------


def test_clean_data_has_no_issues(typed_orders):
    report = validate(typed_orders)
    assert report.is_valid
    assert report.issues == []
    assert report.errors == []
    assert report.warnings == []
    assert report.summary() == "Validation: no issues found"


def test_empty_table_is_valid(typed_orders):
    report = validate(typed_orders.iloc[0:0])
    assert report.is_valid
    assert report.issues == []


def test_the_sample_dataset_is_clean():
    assert validate_orders(load_orders(SAMPLE_DATA)).issues == []


def test_a_missing_optional_value_is_not_reported(typed_orders):
    typed_orders.loc[1, "Category"] = None
    typed_orders.loc[1, "CustomerID"] = None
    assert validate(typed_orders).issues == []


# --- errors -----------------------------------------------------------------------------


@pytest.mark.parametrize("column", ["OrderID", "Date", "Product", "UnitPrice", "Quantity"])
def test_missing_required_value_is_an_error(typed_orders, column):
    typed_orders.loc[1, column] = None
    report = validate(typed_orders)
    assert not report.is_valid
    (issue,) = report.issues
    assert (issue.code, issue.severity, issue.column) == ("missing_value", "error", column)
    assert issue.rows == (3,)
    assert column in issue.message


def test_negative_price_is_an_error(typed_orders):
    typed_orders.loc[0, "UnitPrice"] = -1.0
    (issue,) = validate(typed_orders).issues
    assert (issue.code, issue.severity, issue.column) == ("negative_value", "error", "UnitPrice")
    assert issue.rows == (2,)


def test_negative_quantity_is_an_error(typed_orders):
    typed_orders.loc[[2, 4], "Quantity"] = -1
    (issue,) = validate(typed_orders).issues
    assert (issue.code, issue.severity, issue.column) == ("negative_value", "error", "Quantity")
    assert issue.rows == (4, 6)


def test_duplicate_order_id_is_one_error_naming_both_rows(typed_orders):
    typed_orders.loc[3, "OrderID"] = typed_orders.loc[1, "OrderID"]
    report = validate(typed_orders)
    (issue,) = report.errors
    assert issue.code == "duplicate_order_id"
    assert issue.rows == (3, 5)
    assert "1001" in issue.message
    assert report.warnings == []


def test_each_duplicated_order_id_gets_its_own_error(typed_orders):
    typed_orders.loc[1, "OrderID"] = 1000
    typed_orders.loc[5, "OrderID"] = 1004
    report = validate(typed_orders)
    assert codes(report) == ["duplicate_order_id", "duplicate_order_id"]
    assert [issue.rows for issue in report.issues] == [(2, 3), (6, 7)]


def test_missing_order_ids_are_not_reported_as_duplicates(typed_orders):
    typed_orders.loc[[0, 1], "OrderID"] = None
    assert codes(validate(typed_orders)) == ["missing_value"]


# --- warnings ---------------------------------------------------------------------------


def test_zero_quantity_is_a_warning_and_keeps_the_data_valid(typed_orders):
    typed_orders.loc[0, "Quantity"] = 0
    report = validate(typed_orders)
    assert report.is_valid
    (issue,) = report.warnings
    assert (issue.code, issue.severity, issue.rows) == ("zero_quantity", "warning", (2,))


def test_future_date_is_a_warning(typed_orders):
    typed_orders.loc[1, "Date"] = pd.Timestamp("2026-01-01")
    report = validate(typed_orders)
    assert report.is_valid
    (issue,) = report.warnings
    assert (issue.code, issue.rows) == ("future_date", (3,))
    assert "2025-12-31" in issue.message


def test_a_date_equal_to_today_is_not_in_the_future(typed_orders):
    typed_orders.loc[1, "Date"] = TODAY
    assert validate(typed_orders).issues == []


def test_future_date_uses_the_current_date_by_default(typed_orders):
    typed_orders.loc[1, "Date"] = pd.Timestamp("2200-01-01")
    assert codes(validate_orders(typed_orders)) == ["future_date"]


@pytest.mark.parametrize("column", ["Product", "Country"])
def test_leading_or_trailing_spaces_are_a_warning(typed_orders, column):
    typed_orders.loc[0, column] = typed_orders.loc[0, column] + " "
    (issue,) = validate(typed_orders).issues
    assert (issue.code, issue.severity, issue.column) == ("untrimmed_text", "warning", column)
    assert issue.rows == (2,)


def test_inconsistent_casing_is_a_warning_listing_the_variants(typed_orders):
    typed_orders.loc[1, "Country"] = "france"
    (issue,) = validate(typed_orders).issues
    assert (issue.code, issue.severity, issue.column) == (
        "inconsistent_casing",
        "warning",
        "Country",
    )
    assert issue.rows == (2, 3, 4, 7)
    assert "'France', 'france'" in issue.message


def test_different_words_are_not_inconsistent_casing(typed_orders):
    assert validate(typed_orders).issues == []


# --- reports ----------------------------------------------------------------------------


def test_several_problems_are_all_reported(typed_orders):
    typed_orders.loc[0, "UnitPrice"] = -5.0
    typed_orders.loc[2, "OrderID"] = typed_orders.loc[1, "OrderID"]
    typed_orders.loc[3, "Product"] = "Phone "
    report = validate(typed_orders)
    assert sorted(codes(report)) == ["duplicate_order_id", "negative_value", "untrimmed_text"]
    assert len(report.errors) == 2
    assert len(report.warnings) == 1
    assert not report.is_valid


def test_summary_counts_errors_and_warnings(typed_orders):
    typed_orders.loc[0, "UnitPrice"] = -5.0
    typed_orders.loc[3, "Product"] = "Phone "
    typed_orders.loc[4, "Quantity"] = 0
    summary = validate(typed_orders).summary()
    assert summary.splitlines()[0] == "Validation: 1 error, 2 warnings"


def test_summary_lists_each_finding_with_its_lines(typed_orders):
    typed_orders.loc[3, "OrderID"] = typed_orders.loc[1, "OrderID"]
    lines = validate(typed_orders).summary().splitlines()
    assert lines[1] == "  [error] Duplicate OrderID 1001 (lines 3 and 5)"


def test_summary_shortens_long_line_lists(typed_orders):
    many = pd.concat([typed_orders] * 3, ignore_index=True)
    many["OrderID"] = range(len(many))
    many["Quantity"] = 0
    line = validate(many).summary().splitlines()[1]
    assert line == "  [warning] Quantity is zero (lines 2, 3, 4, 5, 6 and 13 more)"


def test_every_rule_code_is_used_with_a_known_severity():
    assert set(RULES.values()) == {"error", "warning"}


def test_bad_data_never_raises():
    broken = pd.DataFrame(
        {
            "OrderID": [None, None],
            "Date": [pd.NaT, pd.NaT],
            "Product": [None, None],
            "Category": [None, None],
            "UnitPrice": [None, None],
            "Quantity": [None, None],
            "CustomerID": [None, None],
            "Country": [None, None],
        }
    ).astype({"OrderID": "float64", "UnitPrice": "float64", "Quantity": "float64"})
    report = validate(broken)
    assert not report.is_valid
    assert len(report.errors) == 5


def test_missing_columns_are_a_loading_problem_and_raise(typed_orders):
    with pytest.raises(SchemaError, match="Quantity"):
        validate(typed_orders.drop(columns="Quantity"))


# --- large files ------------------------------------------------------------------------


def large_orders(rows: int, products: int) -> pd.DataFrame:
    """A clean frame of `rows` orders over `products` distinct products."""
    return pd.DataFrame(
        {
            "OrderID": range(1, rows + 1),
            "Date": pd.Timestamp("2025-01-01"),
            "Product": [f"Product {i % products}" for i in range(rows)],
            "Category": "Misc",
            "UnitPrice": 1.0,
            "Quantity": 1,
            "CustomerID": "C1",
            "Country": "France",
        }
    )


@pytest.fixture
def column_scans(monkeypatch):
    """Count the whole-column comparisons a validation run makes: ``eq`` and ``==``."""
    calls = []

    def counting(original):
        def wrapper(self, *args, **kwargs):
            calls.append(len(self))
            return original(self, *args, **kwargs)

        return wrapper

    monkeypatch.setattr(pd.Series, "eq", counting(pd.Series.eq))
    monkeypatch.setattr(pd.Series, "__eq__", counting(pd.Series.__eq__))
    return calls


@contextlib.contextmanager
def cpu_time_limit(seconds: float):
    """Fail the test as soon as the code under it has used ``seconds`` of processor time.

    Processor time, unlike the clock on the wall, does not grow when the machine is busy with
    other work, so a generous limit does not fail at random on a shared CI runner. The check
    interrupts the code, so a slow version fails after the limit instead of after minutes.
    """

    def too_slow(signum, frame):
        raise AssertionError(f"used more than {seconds} s of processor time")

    previous = signal.signal(signal.SIGPROF, too_slow)
    signal.setitimer(signal.ITIMER_PROF, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_PROF, 0)
        signal.signal(signal.SIGPROF, previous)


needs_posix_timers = pytest.mark.skipif(
    not hasattr(signal, "setitimer"), reason="needs POSIX interval timers (Linux and macOS)"
)


def test_validation_does_not_scan_the_column_once_per_distinct_product(column_scans):
    # The first version compared the whole column with each distinct spelling, so the work
    # grew with (distinct values x rows): 8,000 products took half a minute. This counts the
    # scans, which does not depend on the speed of the machine.
    orders = large_orders(rows=4_000, products=1_000)
    validate(orders)
    assert len(column_scans) < 10, f"{len(column_scans)} scans of the column"


def test_validation_does_not_scan_the_column_once_per_duplicated_order_id(column_scans):
    orders = large_orders(rows=4_000, products=10)
    orders["OrderID"] = orders.index // 2  # 2,000 ids, each twice
    validate(orders)
    assert len(column_scans) < 10, f"{len(column_scans)} scans of the column"


def test_the_number_of_scans_does_not_grow_with_the_number_of_values(column_scans):
    small = large_orders(rows=400, products=100)
    validate(small)
    for_small = len(column_scans)
    column_scans.clear()
    large = large_orders(rows=4_000, products=1_000)
    validate(large)
    assert len(column_scans) == for_small


# The limits are about 50 times what the code uses on an idle machine for the products and
# 5 times for the order ids; the first version needed 34 s and 10 s.


@needs_posix_timers
def test_many_products_are_validated_within_a_generous_processor_time_limit():
    orders = large_orders(rows=40_000, products=8_000)
    with cpu_time_limit(6):
        validate(orders)


@needs_posix_timers
def test_many_duplicated_order_ids_are_validated_within_a_generous_processor_time_limit():
    orders = large_orders(rows=100_000, products=10)
    orders["OrderID"] = orders.index // 2  # every id appears twice: 50,000 duplicates
    with cpu_time_limit(5):
        validate(orders)


def test_the_processor_time_limit_interrupts_slow_code():
    with pytest.raises(AssertionError, match="processor time"), cpu_time_limit(0.2):
        while True:
            sum(range(10_000))


def test_the_processor_time_limit_is_removed_afterwards():
    with cpu_time_limit(60):
        pass
    assert signal.getitimer(signal.ITIMER_PROF) == (0.0, 0.0)


def test_many_products_with_one_inconsistent_spelling_are_reported_exactly():
    orders = large_orders(rows=40_000, products=8_000)
    orders.loc[5, "Product"] = "product 5"  # the one odd spelling
    (issue,) = validate(orders).issues
    assert issue.code == "inconsistent_casing"
    assert "'Product 5', 'product 5'" in issue.message
    assert 7 in issue.rows  # row index 5 is CSV line 7


def test_many_duplicated_order_ids_are_reported_exactly():
    orders = large_orders(rows=100_000, products=10)
    orders["OrderID"] = orders.index // 2  # every id appears twice: 50,000 duplicates
    report = validate(orders)
    assert codes(report).count("duplicate_order_id") == 50_000
    first = report.issues[0]
    assert (first.message, first.rows) == ("Duplicate OrderID 0", (2, 3))


# --- dates with a time zone ---------------------------------------------------------------


@pytest.fixture
def zoned_orders(typed_orders):
    zoned = typed_orders.copy()
    zoned["Date"] = zoned["Date"].dt.tz_localize("Europe/Paris")
    return zoned


def test_dates_with_a_time_zone_can_be_validated(zoned_orders):
    assert validate(zoned_orders).issues == []


def test_a_future_date_with_a_time_zone_is_flagged(zoned_orders):
    zoned_orders.loc[2, "Date"] = pd.Timestamp("2026-06-01", tz="Europe/Paris")
    (issue,) = validate(zoned_orders).issues
    assert (issue.code, issue.rows) == ("future_date", (4,))


def test_dates_with_a_time_zone_are_validated_without_a_reference_date(zoned_orders):
    assert validate_orders(zoned_orders).issues == []


def test_a_reference_date_with_a_time_zone_works_with_plain_dates(typed_orders):
    today = pd.Timestamp("2025-02-10", tz="Europe/Paris")
    report = validate_orders(typed_orders, today=today)
    assert [(i.code, i.rows) for i in report.issues] == [("future_date", (5, 6, 7))]
