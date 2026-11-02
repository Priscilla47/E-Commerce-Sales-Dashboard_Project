import re
from pathlib import Path

import pytest

from sales_insights.ai.forecast import forecast_with_error
from sales_insights.cli.main import main
from sales_insights.data.loader import load_orders

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = str(ROOT / "data" / "sample_orders.csv")
HEADER = "OrderID,Date,Product,Category,UnitPrice,Quantity,CustomerID,Country\n"


def monthly_csv(tmp_path, values, start_year=2023):
    """One order on the last day of each month, with the given revenue (price x 1)."""
    import calendar

    lines = [HEADER.strip()]
    for index, value in enumerate(values):
        year, month = start_year + index // 12, index % 12 + 1
        day = calendar.monthrange(year, month)[1]
        lines.append(
            f"{index + 1},{year}-{month:02d}-{day:02d},Book,Books,{value},1,C{index},France"
        )
    path = tmp_path / "monthly.csv"
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --- the answer -------------------------------------------------------------------------------


def test_forecast_three_months_of_the_sample_prints_three_rows_and_the_error_line(capsys):
    code, out, err = run(capsys, "--forecast", "3", SAMPLE)
    lines = out.splitlines()
    assert code == 0
    assert lines[0] == "Revenue forecast (naive method)"
    assert lines[1].split() == ["Month", "Forecast", "Lower", "Upper"]
    assert [line.split()[0] for line in lines[2:5]] == ["2025-05", "2025-06", "2025-07"]
    assert lines[5].startswith("Error on the last 1 month, naive method: MAE ")
    assert len(lines) == 6


def test_the_numbers_are_the_numbers_of_the_report(capsys):
    report = forecast_with_error(load_orders(SAMPLE), 3)
    _, out, _ = run(capsys, "--forecast", "3", SAMPLE)
    rows = [line.split() for line in out.splitlines()[2:5]]
    table = report.forecast.table
    for row, (_, expected) in zip(rows, table.iterrows(), strict=True):
        assert row[0] == f"{expected['period']:%Y-%m}"
        assert [float(cell) for cell in row[1:]] == [
            float(f"{expected[c]:.2f}") for c in ("forecast", "lower", "upper")
        ]
    mae = report.evaluation.model.mae
    assert f"MAE {mae:.2f}" in out.splitlines()[5]
    assert f"MAPE {report.evaluation.model.mape:.1f}%" in out


def test_the_error_line_also_gives_the_baseline(capsys):
    _, out, _ = run(capsys, "--forecast", "2", SAMPLE)
    assert re.search(r"; baseline: MAE [\d.]+, MAPE [\d.]+%$", out.splitlines()[-1])


def test_a_long_history_uses_holt_winters_and_says_so(capsys, tmp_path):
    path = monthly_csv(tmp_path, [100 + 10 * month for month in range(1, 31)])
    code, out, err = run(capsys, "--forecast", "2", path)
    assert code == 0
    assert out.splitlines()[0] == "Revenue forecast (Holt-Winters method)"
    assert "on the last 3 months, Holt-Winters method" in out.splitlines()[-1]
    assert err == ""


def test_the_forecast_values_have_two_decimals(capsys):
    _, out, _ = run(capsys, "--forecast", "1", SAMPLE)
    for cell in out.splitlines()[2].split()[1:]:
        assert re.fullmatch(r"\d+\.\d{2}", cell)


# --- the reasons the user needs to know -------------------------------------------------------


def test_the_warnings_of_the_forecast_go_to_stderr_not_stdout(capsys):
    code, out, err = run(capsys, "--forecast", "3", SAMPLE)
    assert code == 0
    assert "warning" not in out
    lines = err.splitlines()
    assert all(line.startswith("sales-insights: warning: ") for line in lines)
    assert any("2025-05" in line and "left out" in line for line in lines)
    assert any("naive method was used instead of holt_winters" in line for line in lines)
    assert len(lines) == len(set(lines)), "no warning is printed twice"


def test_with_three_months_there_is_a_forecast_a_warning_and_no_error_line(capsys, tmp_path):
    path = monthly_csv(tmp_path, [100, 110, 120])
    code, out, err = run(capsys, "--forecast", "2", path)
    assert code == 0
    assert len(out.splitlines()) == 4  # title, header, two rows
    assert "Error on" not in out
    assert "cannot be measured with 3 months" in err


# --- the errors -------------------------------------------------------------------------------


@pytest.mark.parametrize("months", ["0", "13", "-2", "100"])
def test_a_number_of_months_outside_1_to_12_exits_84_and_names_the_range(capsys, months):
    code, out, err = run(capsys, "--forecast", months, SAMPLE)
    assert code == 84
    assert out == ""
    assert "sales-insights: error: months must be from 1 to 12" in err


@pytest.mark.parametrize("months", ["abc", "2.5", ""])
def test_a_number_of_months_that_is_not_a_whole_number_exits_84(capsys, months):
    code, out, err = run(capsys, "--forecast", months, SAMPLE)
    assert code == 84
    assert out == ""
    assert "--forecast: invalid int value" in err


def test_a_missing_number_exits_84(capsys):
    code, _, err = run(capsys, "--forecast")
    assert code == 84
    assert "expected one argument" in err or "required" in err


def test_two_months_of_history_exit_84_with_the_reason_on_stderr(capsys, tmp_path):
    path = monthly_csv(tmp_path, [100, 110])
    code, out, err = run(capsys, "--forecast", "3", path)
    assert code == 84
    assert out == ""
    assert "sales-insights: error: The forecast needs at least 3 months of history, found 2" in err


# --- with other options -----------------------------------------------------------------------


def test_the_answers_keep_the_order_of_the_options(capsys):
    code, out, _ = run(capsys, "-T", "--forecast", "1", "-t", "1", SAMPLE)
    lines = out.splitlines()
    assert code == 0
    assert lines[0].startswith("Total Revenue:")
    assert lines[1].startswith("Revenue forecast")
    assert lines[-2].startswith("1 - ")
    assert lines[-1].startswith("Top ")


def test_an_error_after_a_forecast_still_keeps_what_was_printed_before(capsys):
    code, out, err = run(capsys, "--forecast", "1", "-t", "999", SAMPLE)
    assert code == 84
    assert out.startswith("Revenue forecast")
    assert "Wrong number of products" in err


def test_the_option_given_twice_is_answered_twice(capsys):
    _, out, _ = run(capsys, "--forecast", "1", "--forecast", "2", SAMPLE)
    assert out.count("Revenue forecast") == 2


def test_the_forecast_does_not_change_the_other_answers(capsys):
    _, alone, _ = run(capsys, "-T", SAMPLE)
    _, together, _ = run(capsys, "-T", "--forecast", "1", SAMPLE)
    assert together.startswith(alone)


def test_a_revenue_too_large_to_forecast_exits_84_with_a_message_and_no_numpy_warning(
    capsys, tmp_path
):
    path = monthly_csv(tmp_path, [10] * 28 + ["1e308", 10])
    code, _, err = run(capsys, "--forecast", "2", path)
    assert code == 84
    assert "too large to forecast" in err
    assert "RuntimeWarning" not in err and "overflow" not in err
