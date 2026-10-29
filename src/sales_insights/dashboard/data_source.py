"""Where the dashboard gets its orders from: the sample file or an uploaded CSV.

This module holds the loading logic that does not need Streamlit, so that it can be tested
without a browser. Every function returns the loaded orders together with the validation
report, and raises the ``SchemaError`` of the loader (with its message that says what to
change) when a file cannot be loaded at all.
"""

from pathlib import Path
from typing import NamedTuple, Protocol

import pandas as pd

from sales_insights.data.loader import load_orders, load_orders_from_bytes
from sales_insights.data.validation import ERROR, ValidationReport, validate_orders

# The sample file shipped with the repository (not part of an installed package).
SAMPLE_PATH = Path(__file__).resolve().parents[3] / "data" / "sample_orders.csv"


class LoadedData(NamedTuple):
    """Orders loaded from a file and what the validation found in them."""

    orders: pd.DataFrame
    report: ValidationReport


class Upload(Protocol):
    """What an uploaded file offers: its bytes through ``read`` (and maybe ``getvalue``)."""

    def read(self) -> bytes: ...


def sample_is_available() -> bool:
    """True when the sample file is there (it is missing outside a clone of the repository)."""
    return SAMPLE_PATH.is_file()


def load_from_path(path: str | Path) -> LoadedData:
    """Load the orders of the CSV file at ``path`` and validate them."""
    return _validated(load_orders(path))


def load_from_bytes(content: bytes) -> LoadedData:
    """Load the orders of a CSV file given as bytes, and validate them."""
    return _validated(load_orders_from_bytes(content))


def load_from_upload(upload: Upload) -> LoadedData:
    """Load the orders of an uploaded file (a file-like object), whatever its read position."""
    getvalue = getattr(upload, "getvalue", None)
    if getvalue is not None:
        content = getvalue()
    else:
        seek = getattr(upload, "seek", None)
        if seek is not None:
            seek(0)
        content = upload.read()
    return load_from_bytes(content)


def count_problems(report: ValidationReport, severity: str = ERROR) -> int:
    """The number of affected lines among the findings of the given ``severity``."""
    return sum(len(issue.rows) for issue in report.issues if issue.severity == severity)


def describe_problems(
    report: ValidationReport, severity: str = ERROR, limit: int = 20
) -> list[str]:
    """One short message per affected line, such as ``line 12: Missing value in column 'Date'``.

    Lists the findings of the given ``severity`` (the errors by default), by line number. When
    there are more than ``limit`` of them, the first ``limit`` are listed and a last entry says
    how many more there are (``and 30 more``).
    """
    problems = sorted(
        (row, issue.message)
        for issue in report.issues
        if issue.severity == severity
        for row in issue.rows
    )
    lines = [f"line {row}: {message}" for row, message in problems[:limit]]
    if len(problems) > limit:
        lines.append(f"and {len(problems) - limit} more")
    return lines


def _validated(orders: pd.DataFrame) -> LoadedData:
    return LoadedData(orders, validate_orders(orders))
