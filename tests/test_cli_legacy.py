"""Characterization tests for the existing command-line interface (main.py, usage.py).

They record today's behavior, exit codes and messages. Defects are written as strict
xfail tests asserting the correct behavior, so the rebuilt CLI turns them into normal tests.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

from sales_insights.cli import main as cli
from sales_insights.cli import usage
from tests.conftest import ORDER_COLUMNS

SAMPLE_DATA = Path(__file__).resolve().parent.parent / "data" / "sample_orders.csv"
FLAGS = ["-T", "-c", "-u", "-p", "-t"]


def run_cli(monkeypatch, capsys, *args):
    """Run main() with the given arguments and return (exit_code, stdout).

    The exit code is 0 when main() returns normally.
    """
    monkeypatch.setattr(sys, "argv", ["main.py", *args])
    code = 0
    try:
        cli.main()
    except SystemExit as error:
        code = error.code
    return code, capsys.readouterr().out


@pytest.fixture
def orders_csv(tmp_path, orders):
    """The shared fixture written to disk: revenue 1660.0, Book 6 units in 3 orders."""
    path = tmp_path / "orders.csv"
    orders.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def ranking_csv(tmp_path):
    """Apple 1 unit, Banana 5 units, Cherry 3 units (the best seller is not the first product)."""
    rows = [
        (1, "2025-01-01", "Apple", "Fruit", 1.0, 1, "C1", "France"),
        (2, "2025-01-02", "Banana", "Fruit", 1.0, 5, "C2", "France"),
        (3, "2025-01-03", "Cherry", "Fruit", 1.0, 3, "C3", "France"),
    ]
    path = tmp_path / "ranking.csv"
    pd.DataFrame(rows, columns=ORDER_COLUMNS).to_csv(path, index=False)
    return str(path)


# --- argument and file errors -----------------------------------------------------------


def test_no_arguments_exits_84(monkeypatch, capsys):
    code, out = run_cli(monkeypatch, capsys)
    assert code == 84
    assert "Wrong number of input" in out


def test_help_alone_prints_usage_and_exits_0(monkeypatch, capsys):
    code, out = run_cli(monkeypatch, capsys, "-h")
    assert code == 0
    assert "USAGE" in out


def test_single_argument_other_than_help_exits_84(monkeypatch, capsys, orders_csv):
    code, out = run_cli(monkeypatch, capsys, orders_csv)
    assert code == 84
    assert "Wrong number of argument" in out
    assert "USAGE" in out


def test_flag_without_file_exits_84(monkeypatch, capsys):
    code, out = run_cli(monkeypatch, capsys, "-T")
    assert code == 84
    assert "Wrong number of argument" in out


def test_missing_file_exits_84_with_usage(monkeypatch, capsys, tmp_path):
    code, out = run_cli(monkeypatch, capsys, "-T", str(tmp_path / "missing.csv"))
    assert code == 84
    assert "Wrong Filepath" in out
    assert "USAGE" in out


def test_directory_instead_of_file_exits_84_with_usage(monkeypatch, capsys, tmp_path):
    code, out = run_cli(monkeypatch, capsys, "-T", str(tmp_path))
    assert code == 84
    assert "Wrong Filepath" in out
    assert "USAGE" in out


def test_unknown_flag_exits_84_with_usage(monkeypatch, capsys, orders_csv):
    code, out = run_cli(monkeypatch, capsys, "-x", orders_csv)
    assert code == 84
    assert "Wrong argument" in out
    assert "USAGE" in out


def test_help_flag_followed_by_a_file_is_treated_as_unknown_argument(
    monkeypatch, capsys, orders_csv
):
    code, out = run_cli(monkeypatch, capsys, "-h", orders_csv)
    assert code == 84
    assert "Wrong argument" in out


# --- each flag --------------------------------------------------------------------------


def test_total_revenue(monkeypatch, capsys, orders_csv):
    code, out = run_cli(monkeypatch, capsys, "-T", orders_csv)
    assert code == 0
    assert out == "Total Revenue:  1660.0\n"


def test_unique_products(monkeypatch, capsys, orders_csv):
    code, out = run_cli(monkeypatch, capsys, "-u", orders_csv)
    assert code == 0
    assert out == "Items sold: ['Book', 'Laptop', 'Phone']\n"


def test_units_sold_for_a_product(monkeypatch, capsys, orders_csv):
    code, out = run_cli(monkeypatch, capsys, "-p", "Book", orders_csv)
    assert code == 0
    assert out == "Number of Book sold:  6\n"


def test_units_sold_for_an_unknown_product_is_zero(monkeypatch, capsys, orders_csv):
    code, out = run_cli(monkeypatch, capsys, "-p", "Unknown", orders_csv)
    assert code == 0
    assert out == "Number of Unknown sold:  0\n"


def test_clients_for_a_product_counts_unique_customers(monkeypatch, capsys, orders_csv):
    # Book has 3 orders from 2 distinct customers: the option counts the customers.
    code, out = run_cli(monkeypatch, capsys, "-c", "Book", orders_csv)
    assert code == 0
    assert out == "Number of clients that bought:  Book = 2\n"


def test_clients_for_a_product_nobody_bought_is_zero(monkeypatch, capsys, orders_csv):
    code, out = run_cli(monkeypatch, capsys, "-c", "Unknown", orders_csv)
    assert code == 0
    assert out == "Number of clients that bought:  Unknown = 0\n"


def test_top_n_products(monkeypatch, capsys, ranking_csv):
    code, out = run_cli(monkeypatch, capsys, "-t", "2", ranking_csv)
    assert code == 0
    assert out.splitlines() == [
        "1 - Banana  sold  5  times",
        "2 - Cherry  sold  3  times",
        "Top  2 :  ['Banana', 'Cherry']",
    ]


def test_top_n_larger_than_product_count_exits_84(monkeypatch, capsys, ranking_csv):
    code, out = run_cli(monkeypatch, capsys, "-t", "9", ranking_csv)
    assert code == 84
    assert "Wrong number of products" in out


def test_several_flags_in_one_command(monkeypatch, capsys, orders_csv):
    code, out = run_cli(monkeypatch, capsys, "-T", "-u", "-p", "Phone", orders_csv)
    assert code == 0
    assert out.splitlines() == [
        "Total Revenue:  1660.0",
        "Items sold: ['Book', 'Laptop', 'Phone']",
        "Number of Phone sold:  2",
    ]


# --- regression on the real sample dataset ------------------------------------------------


def test_sample_dataset_total_revenue(monkeypatch, capsys):
    code, out = run_cli(monkeypatch, capsys, "-T", str(SAMPLE_DATA))
    assert code == 0
    assert out == "Total Revenue:  261333.44\n"


def test_sample_dataset_laptop_customers(monkeypatch, capsys):
    # 46 Laptop orders, but one customer bought it twice: 45 customers.
    code, out = run_cli(monkeypatch, capsys, "-c", "Laptop", str(SAMPLE_DATA))
    assert code == 0
    assert out == "Number of clients that bought:  Laptop = 45\n"


def test_sample_dataset_top_three(monkeypatch, capsys):
    code, out = run_cli(monkeypatch, capsys, "-t", "3", str(SAMPLE_DATA))
    assert code == 0
    assert out.splitlines()[:3] == [
        "1 - Smartphone  sold  186  times",
        "2 - Book  sold  176  times",
        "3 - Desk Lamp  sold  175  times",
    ]


# --- usage ------------------------------------------------------------------------------


@pytest.mark.parametrize("flag", FLAGS)
def test_usage_lists_every_flag(capsys, flag):
    usage.usage()
    assert flag in capsys.readouterr().out


def test_usage_says_the_c_option_counts_unique_customers(capsys):
    usage.usage()
    assert "unique customers" in capsys.readouterr().out


# --- known defects ----------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="known bug: a flag that needs a value silently takes the file path as its value",
)
@pytest.mark.parametrize("flag", ["-c", "-p"])
def test_flag_missing_its_value_is_rejected(monkeypatch, capsys, orders_csv, flag):
    code, _ = run_cli(monkeypatch, capsys, flag, orders_csv)
    assert code == 84


@pytest.mark.xfail(
    strict=True,
    reason="known bug: a non-numeric N crashes with a traceback instead of a clean exit",
)
def test_top_n_with_non_numeric_value_is_rejected(monkeypatch, capsys, ranking_csv):
    code, _ = run_cli(monkeypatch, capsys, "-t", "abc", ranking_csv)
    assert code == 84


# --- data errors ------------------------------------------------------------------------


def test_file_with_a_missing_column_exits_84_with_a_clear_message(monkeypatch, capsys, tmp_path):
    path = tmp_path / "incomplete.csv"
    path.write_text("OrderID,Date,Product\n1,2025-01-01,Book\n")
    code, out = run_cli(monkeypatch, capsys, "-T", str(path))
    assert code == 84
    assert "Missing required column(s)" in out
    assert "Quantity" in out


def test_file_with_an_invalid_value_exits_84_with_a_clear_message(monkeypatch, capsys, tmp_path):
    path = tmp_path / "invalid.csv"
    path.write_text(
        ",".join(ORDER_COLUMNS) + "\n1,not-a-date,Book,Books,10.0,1,C1,France\n"
    )
    code, out = run_cli(monkeypatch, capsys, "-T", str(path))
    assert code == 84
    assert "'Date'" in out
    assert "not-a-date" in out


def test_file_that_is_not_valid_csv_exits_84_with_a_clear_message(monkeypatch, capsys, tmp_path):
    path = tmp_path / "ragged.csv"
    path.write_text(
        ",".join(ORDER_COLUMNS)
        + "\n1,2025-01-01,Book,Books,10.0,1,C1,France\n2,2025-01-02,Book,Books,10.0,1,C1,France,x\n"
    )
    code, out = run_cli(monkeypatch, capsys, "-T", str(path))
    assert code == 84
    assert "not valid CSV" in out
    assert "line 3" in out
