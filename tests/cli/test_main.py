"""The command line, called through main([...]) so no sys.argv patching is needed.

Every test of the first version of the tool was ported here: the output of each option is
unchanged. Errors now go to stderr (with exit code 84) and the old known defects are fixed.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from sales_insights.cli.main import build_parser, main
from tests.conftest import ORDER_COLUMNS

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DATA = ROOT / "data" / "sample_orders.csv"
OPTIONS = ["-T", "-c", "-u", "-p", "-t", "--by", "--validate"]
HEADER = ",".join(ORDER_COLUMNS)


def run(capsys, *args):
    """Call main() and return (exit code, stdout, stderr)."""
    code = main(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def write_csv(tmp_path, *lines, header=HEADER):
    path = tmp_path / "data.csv"
    path.write_text("\n".join([header, *lines]) + "\n")
    return str(path)


# --- help and usage errors --------------------------------------------------------------


def test_help_exits_0_and_lists_every_option(capsys):
    code, out, err = run(capsys, "-h")
    assert code == 0
    assert err == ""
    assert out.startswith("usage: sales-insights")
    for option in OPTIONS:
        assert option in out


def test_help_says_the_c_option_counts_unique_customers(capsys):
    _, out, _ = run(capsys, "-h")
    assert "unique customers" in " ".join(out.split())


def test_help_followed_by_a_file_still_shows_the_help(capsys, orders_csv):
    code, out, _ = run(capsys, "-h", orders_csv)
    assert code == 0
    assert out.startswith("usage:")


def test_no_arguments_exits_84_with_usage_on_stderr(capsys):
    code, out, err = run(capsys)
    assert code == 84
    assert out == ""
    assert err.startswith("usage: sales-insights")
    assert "required: file" in err


def test_a_file_without_any_option_exits_84(capsys, orders_csv):
    code, out, err = run(capsys, orders_csv)
    assert code == 84
    assert out == ""
    assert "choose at least one option" in err


def test_an_option_without_a_file_exits_84(capsys):
    code, out, err = run(capsys, "-T")
    assert code == 84
    assert out == ""
    assert "required: file" in err


def test_unknown_option_exits_84_with_usage(capsys, orders_csv):
    code, out, err = run(capsys, "-x", orders_csv)
    assert code == 84
    assert out == ""
    assert "unrecognized arguments: -x" in err
    assert "usage:" in err


def test_option_names_cannot_be_abbreviated(capsys, orders_csv):
    code, out, err = run(capsys, "--val", orders_csv)
    assert code == 84
    assert out == ""
    assert "unrecognized arguments" in err


@pytest.mark.parametrize(
    ("option", "complaint"),
    [
        ("-c", "required: file"),
        ("-p", "required: file"),
        ("-t", "invalid int value"),
        ("--by", "invalid choice"),
    ],
)
def test_an_option_missing_its_value_is_rejected(capsys, orders_csv, option, complaint):
    # The file path is taken as the value of the option, so the file is missing or the value
    # is invalid: either way nothing is run and the exit code is 84.
    code, out, err = run(capsys, option, orders_csv)
    assert code == 84
    assert out == ""
    assert complaint in err


# --- file errors ------------------------------------------------------------------------


def test_missing_file_exits_84_with_a_message_on_stderr(capsys, tmp_path):
    missing = str(tmp_path / "missing.csv")
    code, out, err = run(capsys, "-T", missing)
    assert code == 84
    assert out == ""
    assert f"Orders file not found: {missing}" in err


def test_directory_instead_of_file_exits_84(capsys, tmp_path):
    code, out, err = run(capsys, "-T", str(tmp_path))
    assert code == 84
    assert out == ""
    assert "Orders file not found" in err


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read any file")
def test_unreadable_file_exits_84(capsys, orders_csv):
    os.chmod(orders_csv, 0)
    try:
        code, out, err = run(capsys, "-T", orders_csv)
    finally:
        os.chmod(orders_csv, 0o644)
    assert code == 84
    assert out == ""
    assert "Cannot read" in err
    assert "Permission denied" in err


# --- data errors ------------------------------------------------------------------------


def test_file_with_a_missing_column_exits_84_with_a_clear_message(capsys, tmp_path):
    path = tmp_path / "incomplete.csv"
    path.write_text("OrderID,Date,Product\n1,2025-01-01,Book\n")
    code, out, err = run(capsys, "-T", str(path))
    assert code == 84
    assert out == ""
    assert "Missing required column(s)" in err
    assert "Quantity" in err


def test_file_with_an_invalid_value_exits_84_with_a_clear_message(capsys, tmp_path):
    path = write_csv(tmp_path, "1,not-a-date,Book,Books,10.0,1,C1,France")
    code, out, err = run(capsys, "-T", path)
    assert code == 84
    assert out == ""
    assert "'Date'" in err
    assert "not-a-date" in err


def test_file_that_is_not_valid_csv_exits_84_with_a_clear_message(capsys, tmp_path):
    path = write_csv(
        tmp_path,
        "1,2025-01-01,Book,Books,10.0,1,C1,France",
        "2,2025-01-02,Book,Books,10.0,1,C1,France,x",
    )
    code, out, err = run(capsys, "-T", path)
    assert code == 84
    assert out == ""
    assert "not valid CSV" in err
    assert "line 3" in err


def test_empty_file_exits_84_with_a_clear_message(capsys, tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("")
    code, out, err = run(capsys, "-T", str(path))
    assert code == 84
    assert out == ""
    assert "The orders file is empty" in err


@pytest.mark.parametrize("encoding", ["latin-1", "utf-16"])
def test_file_saved_in_another_encoding_exits_84_and_says_what_to_do(capsys, tmp_path, encoding):
    path = tmp_path / "excel.csv"
    path.write_bytes((HEADER + "\n1,2025-01-01,Café,Books,10.0,2,C1,France\n").encode(encoding))
    code, out, err = run(capsys, "-T", str(path))
    assert code == 84
    assert out == ""
    assert "not UTF-8 text" in err
    assert "CSV UTF-8" in err
    assert "Traceback" not in err


def test_dates_that_mix_time_zones_exit_84(capsys, tmp_path):
    path = write_csv(
        tmp_path,
        "1,2025-01-01T10:00:00+01:00,Book,Books,10.0,2,C1,France",
        "2,2025-01-02T10:00:00+02:00,Book,Books,10.0,2,C1,France",
    )
    code, out, err = run(capsys, "-T", path)
    assert code == 84
    assert out == ""
    assert "'Date' mixes time zones" in err


def test_dates_with_one_time_zone_work_with_every_report(capsys, tmp_path):
    path = write_csv(
        tmp_path,
        "1,2025-01-31T23:30:00+01:00,Book,Books,10.0,2,C1,France",
        "2,2025-02-01T00:30:00+01:00,Book,Books,10.0,1,C2,France",
    )
    code, out, err = run(capsys, "-T", "--by", "month", "--validate", path)
    assert (code, err) == (0, "")
    assert out.splitlines() == [
        "Total Revenue:  30.0",
        "Revenue by month",
        "Month    Revenue  Orders",
        "2025-01    20.00       1",
        "2025-02    10.00       1",
        "Validation: no issues found",
    ]


def test_error_messages_name_the_command(capsys, tmp_path):
    _, _, err = run(capsys, "-T", str(tmp_path / "missing.csv"))
    assert err.startswith("sales-insights: error: ")


# --- each option ------------------------------------------------------------------------


def test_total_revenue(capsys, orders_csv):
    code, out, err = run(capsys, "-T", orders_csv)
    assert (code, out, err) == (0, "Total Revenue:  1660.0\n", "")


def test_unique_products(capsys, orders_csv):
    code, out, err = run(capsys, "-u", orders_csv)
    assert (code, out, err) == (0, "Items sold: ['Book', 'Laptop', 'Phone']\n", "")


def test_units_sold_for_a_product(capsys, orders_csv):
    code, out, err = run(capsys, "-p", "Book", orders_csv)
    assert (code, out, err) == (0, "Number of Book sold:  6\n", "")


def test_units_sold_for_an_unknown_product_is_zero(capsys, orders_csv):
    code, out, _ = run(capsys, "-p", "Unknown", orders_csv)
    assert (code, out) == (0, "Number of Unknown sold:  0\n")


def test_clients_for_a_product_counts_unique_customers(capsys, orders_csv):
    # Book has 3 orders from 2 distinct customers: the option counts the customers.
    code, out, err = run(capsys, "-c", "Book", orders_csv)
    assert (code, out, err) == (0, "Number of clients that bought:  Book = 2\n", "")


def test_clients_for_a_product_nobody_bought_is_zero(capsys, orders_csv):
    code, out, _ = run(capsys, "-c", "Unknown", orders_csv)
    assert (code, out) == (0, "Number of clients that bought:  Unknown = 0\n")


def test_a_product_name_with_a_space(capsys, tmp_path):
    path = write_csv(tmp_path, "1,2025-01-01,Desk Lamp,Home,20.0,3,C1,France")
    code, out, _ = run(capsys, "-p", "Desk Lamp", path)
    assert (code, out) == (0, "Number of Desk Lamp sold:  3\n")


def test_top_n_products(capsys, ranking_csv):
    code, out, err = run(capsys, "-t", "2", ranking_csv)
    assert code == 0
    assert err == ""
    assert out.splitlines() == [
        "1 - Banana  sold  5  times",
        "2 - Cherry  sold  3  times",
        "Top  2 :  ['Banana', 'Cherry']",
    ]


def test_top_n_with_every_product(capsys, ranking_csv):
    code, out, _ = run(capsys, "-t", "3", ranking_csv)
    assert code == 0
    assert out.splitlines()[-1] == "Top  3 :  ['Banana', 'Cherry', 'Apple']"


def test_top_zero_prints_an_empty_ranking(capsys, ranking_csv):
    code, out, _ = run(capsys, "-t", "0", ranking_csv)
    assert (code, out) == (0, "Top  0 :  []\n")


def test_top_n_larger_than_product_count_exits_84(capsys, ranking_csv):
    code, out, err = run(capsys, "-t", "9", ranking_csv)
    assert code == 84
    assert out == ""
    assert "Wrong number of products" in err


def test_top_n_negative_exits_84(capsys, ranking_csv):
    code, out, err = run(capsys, "-t", "-1", ranking_csv)
    assert code == 84
    assert out == ""
    assert "Wrong number of products" in err


@pytest.mark.parametrize("value", ["abc", "1.5", ""])
def test_top_n_with_a_value_that_is_not_a_whole_number_exits_84(capsys, ranking_csv, value):
    code, out, err = run(capsys, "-t", value, ranking_csv)
    assert code == 84
    assert out == ""
    assert "invalid int value" in err


# --- --by -------------------------------------------------------------------------------


def test_by_country(capsys, orders_csv):
    code, out, err = run(capsys, "--by", "country", orders_csv)
    assert code == 0
    assert err == ""
    assert out.splitlines() == [
        "Revenue by country",
        "Country  Revenue  Orders  Share",
        "UK       1110.00       3  66.9%",
        "France    550.00       3  33.1%",
    ]


def test_by_category(capsys, orders_csv):
    code, out, _ = run(capsys, "--by", "category", orders_csv)
    assert code == 0
    assert out.splitlines() == [
        "Revenue by category",
        "Category     Revenue  Orders  Share",
        "Electronics  1600.00       3  96.4%",
        "Books          60.00       3   3.6%",
    ]


def test_by_month(capsys, orders_csv):
    code, out, _ = run(capsys, "--by", "month", orders_csv)
    assert code == 0
    assert out.splitlines() == [
        "Revenue by month",
        "Month    Revenue  Orders",
        "2025-01   520.00       2",
        "2025-02   640.00       3",
        "2025-03   500.00       1",
    ]


def test_by_month_shows_the_months_without_orders(capsys, tmp_path):
    path = write_csv(
        tmp_path,
        "1,2025-01-10,Book,Books,10.0,1,C1,France",
        "2,2025-03-10,Book,Books,10.0,2,C1,France",
    )
    _, out, _ = run(capsys, "--by", "month", path)
    assert out.splitlines()[2:] == [
        "2025-01    10.00       1",
        "2025-02     0.00       0",
        "2025-03    20.00       1",
    ]


def test_by_country_names_the_lines_without_a_country(capsys, tmp_path):
    path = write_csv(
        tmp_path,
        "1,2025-01-10,Book,Books,10.0,3,C1,",
        "2,2025-01-11,Book,Books,10.0,1,C1,France",
    )
    _, out, _ = run(capsys, "--by", "country", path)
    assert out.splitlines()[2].startswith("(missing)")


def test_by_with_no_orders_says_so(capsys, tmp_path):
    path = write_csv(tmp_path)
    code, out, _ = run(capsys, "--by", "country", path)
    assert code == 0
    assert out.splitlines() == ["Revenue by country", "(no orders)"]


def test_by_with_an_unknown_value_exits_84(capsys, orders_csv):
    code, out, err = run(capsys, "--by", "colour", orders_csv)
    assert code == 84
    assert out == ""
    assert "invalid choice: 'colour'" in err


def test_by_shares_add_up_on_the_sample_dataset(capsys):
    code, out, _ = run(capsys, "--by", "country", str(SAMPLE_DATA))
    assert code == 0
    rows = out.splitlines()[2:]
    assert len(rows) == 10
    revenues = [float(row.split()[-3]) for row in rows]
    assert revenues == sorted(revenues, reverse=True)
    assert sum(revenues) == pytest.approx(261333.44, abs=0.05)


# --- --validate -------------------------------------------------------------------------


def test_validate_a_clean_file(capsys, orders_csv):
    code, out, err = run(capsys, "--validate", orders_csv)
    assert (code, out, err) == (0, "Validation: no issues found\n", "")


def test_validate_a_file_with_errors_prints_the_report_and_exits_84(capsys, faulty_csv):
    code, out, err = run(capsys, "--validate", faulty_csv)
    assert code == 84
    assert err == ""
    assert out.splitlines() == [
        "Validation: 1 error, 1 warning",
        "  [error] Duplicate OrderID 1001 (lines 3 and 5)",
        "  [warning] Quantity is zero (line 4)",
    ]


def test_validate_a_file_with_only_warnings_exits_0(capsys, tmp_path):
    path = write_csv(tmp_path, "1,2025-01-01,Book,Books,10.0,0,C1,France")
    code, out, _ = run(capsys, "--validate", path)
    assert code == 0
    assert out.splitlines() == [
        "Validation: 0 errors, 1 warning",
        "  [warning] Quantity is zero (line 2)",
    ]


def test_validate_the_sample_dataset_is_clean(capsys):
    code, out, _ = run(capsys, "--validate", str(SAMPLE_DATA))
    assert (code, out) == (0, "Validation: no issues found\n")


def test_other_options_still_print_when_the_data_has_errors(capsys, faulty_csv):
    code, out, err = run(capsys, "-T", faulty_csv)
    assert code == 0
    assert out == "Total Revenue:  1630.0\n"  # the zero-quantity line adds nothing
    assert "warning" in err
    assert "1 error" in err
    assert "--validate" in err


def test_the_warning_is_not_repeated_when_validating(capsys, faulty_csv):
    code, out, err = run(capsys, "-T", "--validate", faulty_csv)
    assert code == 84
    assert out.splitlines()[0] == "Total Revenue:  1630.0"
    assert "[error] Duplicate OrderID" in out
    assert err == ""


def test_a_clean_file_gives_no_warning(capsys, orders_csv):
    _, _, err = run(capsys, "-T", orders_csv)
    assert err == ""


def test_a_missing_quantity_is_skipped_by_the_total_and_reported(capsys, tmp_path):
    path = write_csv(
        tmp_path,
        "1,2025-01-01,Book,Books,10.0,2,C1,France",
        "2,2025-01-02,Book,Books,10.0,,C2,France",
    )
    code, out, err = run(capsys, "-T", path)
    assert (code, out) == (0, "Total Revenue:  20.0\n")
    assert "1 error" in err
    code, out, _ = run(capsys, "--validate", path)
    assert code == 84
    assert "Missing value in column 'Quantity' (line 3)" in out


# --- several options --------------------------------------------------------------------


def test_several_options_in_one_command(capsys, orders_csv):
    code, out, err = run(capsys, "-T", "-u", "-p", "Phone", orders_csv)
    assert code == 0
    assert err == ""
    assert out.splitlines() == [
        "Total Revenue:  1660.0",
        "Items sold: ['Book', 'Laptop', 'Phone']",
        "Number of Phone sold:  2",
    ]


def test_results_follow_the_order_of_the_options(capsys, orders_csv):
    _, first, _ = run(capsys, "-p", "Phone", "-T", orders_csv)
    _, second, _ = run(capsys, "-T", "-p", "Phone", orders_csv)
    assert first.splitlines() == ["Number of Phone sold:  2", "Total Revenue:  1660.0"]
    assert second.splitlines() == ["Total Revenue:  1660.0", "Number of Phone sold:  2"]


def test_an_option_given_twice_is_answered_twice(capsys, orders_csv):
    _, out, _ = run(capsys, "-p", "Book", "-p", "Phone", "-T", "-T", orders_csv)
    assert out.splitlines() == [
        "Number of Book sold:  6",
        "Number of Phone sold:  2",
        "Total Revenue:  1660.0",
        "Total Revenue:  1660.0",
    ]


def test_the_old_combined_command_gives_the_same_output(capsys, orders_csv):
    code, out, _ = run(capsys, "-T", "-t", "2", "-p", "Book", "-c", "Book", orders_csv)
    assert code == 0
    assert out.splitlines() == [
        "Total Revenue:  1660.0",
        "1 - Book  sold  6  times",
        "2 - Laptop  sold  2  times",
        "Top  2 :  ['Book', 'Laptop']",
        "Number of Book sold:  6",
        "Number of clients that bought:  Book = 2",
    ]


def test_an_error_after_some_output_keeps_that_output_and_exits_84(capsys, ranking_csv):
    code, out, err = run(capsys, "-T", "-t", "9", ranking_csv)
    assert code == 84
    assert out == "Total Revenue:  9.0\n"
    assert "Wrong number of products" in err


def test_options_combine_with_the_new_reports(capsys, orders_csv):
    code, out, _ = run(capsys, "-T", "--by", "month", "--validate", orders_csv)
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == "Total Revenue:  1660.0"
    assert lines[1] == "Revenue by month"
    assert lines[-1] == "Validation: no issues found"


# --- regression on the real sample dataset ------------------------------------------------


def test_sample_dataset_total_revenue(capsys):
    code, out, _ = run(capsys, "-T", str(SAMPLE_DATA))
    assert (code, out) == (0, "Total Revenue:  261333.44\n")


def test_sample_dataset_laptop_figures(capsys):
    # 46 Laptop orders, but one customer bought it twice: 45 customers.
    code, out, _ = run(capsys, "-c", "Laptop", "-p", "Laptop", str(SAMPLE_DATA))
    assert code == 0
    assert out.splitlines() == [
        "Number of clients that bought:  Laptop = 45",
        "Number of Laptop sold:  147",
    ]


def test_sample_dataset_top_three(capsys):
    code, out, _ = run(capsys, "-t", "3", str(SAMPLE_DATA))
    assert code == 0
    assert out.splitlines() == [
        "1 - Smartphone  sold  186  times",
        "2 - Book  sold  176  times",
        "3 - Desk Lamp  sold  175  times",
        "Top  3 :  ['Smartphone', 'Book', 'Desk Lamp']",
    ]


def test_sample_dataset_every_product_is_ranked(capsys):
    code, out, _ = run(capsys, "-t", "10", str(SAMPLE_DATA))
    assert code == 0
    assert "8 - Blender  sold  140  times" in out.splitlines()


def test_sample_dataset_unique_products(capsys):
    _, out, _ = run(capsys, "-u", str(SAMPLE_DATA))
    assert out.startswith("Items sold: ['Blender', 'Book', 'Coffee Maker',")
    assert out.count(",") == 9


# --- calling conventions ----------------------------------------------------------------


def test_main_returns_an_int(capsys, orders_csv):
    assert type(main(["-T", orders_csv])) is int
    capsys.readouterr()


def test_main_reads_sys_argv_when_called_without_arguments(monkeypatch, capsys, orders_csv):
    monkeypatch.setattr(sys, "argv", ["sales-insights", "-T", orders_csv])
    assert main() == 0
    assert capsys.readouterr().out == "Total Revenue:  1660.0\n"


def test_the_parser_has_exactly_the_documented_options():
    names = {name for action in build_parser()._actions for name in action.option_strings}
    assert names == {"-h", "--help", *OPTIONS}


def run_as_a_program(*args):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "sales_insights.cli.main", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
        check=False,
    )


def test_run_as_a_program_the_exit_code_and_streams_are_real():
    done = run_as_a_program("-T", "data/sample_orders.csv")
    assert (done.returncode, done.stdout, done.stderr) == (0, "Total Revenue:  261333.44\n", "")


def test_run_as_a_program_an_error_exits_with_84_and_writes_to_stderr():
    done = run_as_a_program("-T", "data/missing.csv")
    assert done.returncode == 84
    assert done.stdout == ""
    assert "Orders file not found" in done.stderr


def test_run_as_a_program_help_exits_with_0():
    done = run_as_a_program("-h")
    assert (done.returncode, done.stderr) == (0, "")
    assert "usage: sales-insights" in done.stdout
