import pytest

from sales_insights.data.schema import (
    COLUMN_TYPES,
    COLUMNS,
    SchemaError,
    missing_columns,
    require_columns,
)
from tests.conftest import ORDER_COLUMNS


def test_columns_match_the_documented_order():
    assert list(COLUMNS) == ORDER_COLUMNS


def test_every_column_has_a_known_kind():
    assert set(COLUMN_TYPES.values()) == {"integer", "date", "text", "float"}
    assert COLUMN_TYPES["Quantity"] == "integer"
    assert COLUMN_TYPES["UnitPrice"] == "float"


def test_missing_columns_is_empty_when_all_present():
    assert missing_columns(ORDER_COLUMNS) == []


def test_missing_columns_lists_absent_ones_in_schema_order():
    present = [column for column in ORDER_COLUMNS if column not in ("Country", "Date")]
    assert missing_columns(present) == ["Date", "Country"]


def test_missing_columns_with_nothing_present_lists_everything():
    assert missing_columns([]) == ORDER_COLUMNS


def test_require_columns_accepts_extra_columns():
    require_columns([*ORDER_COLUMNS, "Notes"])


def test_require_columns_raises_and_names_every_missing_column():
    with pytest.raises(SchemaError, match="Date, Country"):
        require_columns([c for c in ORDER_COLUMNS if c not in ("Date", "Country")])


def test_schema_error_is_a_value_error():
    assert issubclass(SchemaError, ValueError)
