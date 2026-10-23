"""The data format page must describe exactly what the code does."""

import re
import sys
from pathlib import Path

from sales_insights.cli import main as cli
from sales_insights.data.loader import load_orders
from sales_insights.data.schema import COLUMN_TYPES, COLUMNS, REVENUE_COLUMN
from sales_insights.data.validation import (
    REQUIRED_VALUE_COLUMNS,
    RULES,
    validate_orders,
)
from tests.conftest import ORDER_COLUMNS

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


# --- the "Errors you may see" table, checked against the real command line ----------------


def write_orders(tmp_path, *lines):
    path = tmp_path / "orders.csv"
    path.write_text("\n".join(lines) + "\n")
    return path


def cli_output(monkeypatch, capsys, path):
    monkeypatch.setattr(sys, "argv", ["sales-insights", "-T", str(path)])
    try:
        cli.main()
    except SystemExit as error:
        assert error.code == 84
    else:
        raise AssertionError("the command line should have stopped with exit code 84")
    return capsys.readouterr().out


HEADER = ",".join(ORDER_COLUMNS)

ERROR_SCENARIOS = {
    "Wrong Filepath": lambda tmp_path: tmp_path / "missing.csv",
    "The orders file is empty: it has no header row": lambda tmp_path: write_orders(tmp_path, ""),
    "The orders file is not valid CSV: Expected 8 fields in line 3, saw 9": lambda tmp_path: write_orders(
        tmp_path,
        HEADER,
        "1,2025-01-01,Book,Books,10.0,1,C1,France",
        "2,2025-01-02,Book,Books,10.0,1,C1,France,extra",
    ),
    "The orders file is not valid CSV: its rows have more values than the header": lambda tmp_path: write_orders(
        tmp_path, HEADER, "1,2025-01-01,Book,Books,10.0,1,C1,France,x"
    ),
    "Duplicate column(s) in the header: Quantity": lambda tmp_path: write_orders(
        tmp_path, HEADER + ",Quantity", "1,2025-01-01,Book,Books,10.0,1,C1,France,5"
    ),
    "Missing required column(s): Quantity": lambda tmp_path: write_orders(
        tmp_path, ",".join(c for c in ORDER_COLUMNS if c != "Quantity")
    ),
    "Column 'Date' must hold a date (YYYY-MM-DD); line 3 has 'abc'": lambda tmp_path: write_orders(
        tmp_path,
        HEADER,
        "1,2025-01-01,Book,Books,10.0,1,C1,France",
        "2,abc,Book,Books,10.0,1,C1,France",
    ),
}


def test_every_documented_error_has_a_scenario():
    assert {row[0] for row in table_rows("Errors you may see")} == set(ERROR_SCENARIOS)


def test_every_documented_error_is_what_the_command_line_prints(monkeypatch, capsys, tmp_path):
    for message, make_file in ERROR_SCENARIOS.items():
        assert message in cli_output(monkeypatch, capsys, make_file(tmp_path)), message


def test_a_folder_gives_the_same_message_as_a_missing_file(monkeypatch, capsys, tmp_path):
    assert "Wrong Filepath" in cli_output(monkeypatch, capsys, tmp_path)
