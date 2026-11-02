"""The forecast as the page writes it: a report in, the labels out (no Streamlit inside).

The labels are written the way the command line prints them, so that both show the same text.
"""

from dataclasses import dataclass

from sales_insights.ai.forecast import METHOD_LABELS, ForecastReport


@dataclass(frozen=True)
class ForecastLabels:
    """The text of a forecast. The error fields are None when the error could not be measured."""

    method: str
    rows: list[tuple[str, str, str, str]]
    warnings: list[str]
    holdout: str | None
    mae: str | None
    mape: str | None
    baseline_mae: str | None
    baseline_mape: str | None
    note: str | None


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}%"


def format_forecast(report: ForecastReport) -> ForecastLabels:
    """The labels of a report: money with two decimals, percentages with one."""
    table = report.forecast.table
    rows = [
        (f"{period:%Y-%m}", f"{value:.2f}", f"{low:.2f}", f"{high:.2f}")
        for period, value, low, high in zip(
            table["period"], table["forecast"], table["lower"], table["upper"], strict=True
        )
    ]
    common = {
        "method": METHOD_LABELS[report.forecast.method_used],
        "rows": rows,
        "warnings": list(report.forecast.warnings),
    }
    evaluation = report.evaluation
    if evaluation is None:
        return ForecastLabels(
            **common,
            holdout=None,
            mae=None,
            mape=None,
            baseline_mae=None,
            baseline_mape=None,
            note=report.note,
        )
    months = evaluation.holdout
    return ForecastLabels(
        **common,
        holdout=f"the last {months} month{'' if months == 1 else 's'}",
        mae=f"{evaluation.model.mae:.2f}",
        mape=_percent(evaluation.model.mape),
        baseline_mae=f"{evaluation.baseline.mae:.2f}",
        baseline_mape=_percent(evaluation.baseline.mape),
        note=None,
    )
