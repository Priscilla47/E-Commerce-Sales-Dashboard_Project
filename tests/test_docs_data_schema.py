"""The data format page must describe exactly what the code does."""

import re
from pathlib import Path

from sales_insights.data.loader import load_orders
from sales_insights.data.schema import COLUMN_TYPES, COLUMNS, REVENUE_COLUMN
from sales_insights.data.validation import REQUIRED_VALUE_COLUMNS, RULES, validate_orders

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "docs" / "data-schema.md").read_text()

TYPE_WORDS = {"whole number": "integer", "date": "date", "text": "text", "number": "float"}


def section(heading: str) -> str:
    start = DOC.index(f"## {heading}\n")
    end = DOC.find("\n## ", start + 1)
    return DOC[start : end if end != -1 else len(DOC)]


def table_rows(heading: str) -> list[list[str]]:
    """The rows of the first table of a section, cells stripped of spaces and backticks."""
    rows = []
    for line in section(heading).splitlines():
        if line.startswith("| `"):
            rows.append([cell.strip().strip("`") for cell in line.strip("|").split("|")])
    return rows


def test_every_column_is_documented_in_schema_order():
    assert [row[0] for row in table_rows("Columns")] == list(COLUMNS)


def test_documented_column_types_match_the_schema():
    for name, type_word, *_ in table_rows("Columns"):
        assert TYPE_WORDS[type_word] == COLUMN_TYPES[name], name


def test_documented_required_values_match_the_validation_rules():
    documented = {row[0] for row in table_rows("Columns") if row[2] == "yes"}
    assert documented == set(REQUIRED_VALUE_COLUMNS)


def test_the_computed_revenue_column_is_documented():
    assert f"`{REVENUE_COLUMN}`" in section("What loading produces")
    assert "UnitPrice * Quantity" in section("What loading produces")


def test_every_validation_rule_is_documented_with_its_severity():
    documented = {row[0]: row[1] for row in table_rows("Validation rules")}
    assert documented == RULES


def test_the_minimal_example_loads_and_passes_validation(tmp_path):
    example = re.search(r"```csv\n(.*?)```", DOC, re.DOTALL).group(1)
    path = tmp_path / "example.csv"
    path.write_text(example)

    orders = load_orders(path)
    report = validate_orders(orders)

    assert len(orders) == 3
    assert report.is_valid
    assert report.issues == []


def test_the_documented_report_example_matches_the_real_format(typed_orders_with_problems):
    expected = re.search(r"Example of a report:\n\n```\n(.*?)\n```", DOC, re.DOTALL).group(1)
    assert validate_orders(typed_orders_with_problems).summary() == expected


def test_the_readme_links_to_the_page():
    assert "docs/data-schema.md" in (ROOT / "README.md").read_text()
