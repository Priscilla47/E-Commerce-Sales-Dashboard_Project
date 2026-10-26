"""Content checks on a loaded orders table.

Problems are collected in a report; bad data never raises. Row numbers in the report are
line numbers of the CSV file: the header is line 1, so the first order is line 2.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from sales_insights.data.schema import require_columns

ERROR = "error"
WARNING = "warning"

# Every rule: its code and how serious a finding is.
RULES = {
    "missing_value": ERROR,
    "negative_value": ERROR,
    "duplicate_order_id": ERROR,
    "zero_quantity": WARNING,
    "future_date": WARNING,
    "untrimmed_text": WARNING,
    "inconsistent_casing": WARNING,
}

REQUIRED_VALUE_COLUMNS = ("OrderID", "Date", "Product", "UnitPrice", "Quantity")
NON_NEGATIVE_COLUMNS = ("UnitPrice", "Quantity")
TEXT_COLUMNS = ("Product", "Country")

MAX_LINES_SHOWN = 5


@dataclass(frozen=True)
class Issue:
    """One finding: what is wrong, how serious it is, and where."""

    code: str
    severity: str
    message: str
    rows: tuple[int, ...]
    column: str | None = None


@dataclass
class ValidationReport:
    """The findings of a validation run."""

    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == WARNING]

    @property
    def is_valid(self) -> bool:
        """True when there are no errors (warnings do not make the data invalid)."""
        return not self.errors

    def summary(self) -> str:
        """A readable text: the counts, then one line per finding."""
        if not self.issues:
            return "Validation: no issues found"
        header = (
            f"Validation: {_count(len(self.errors), 'error')}, "
            f"{_count(len(self.warnings), 'warning')}"
        )
        lines = [
            f"  [{issue.severity}] {issue.message} ({_describe_lines(issue.rows)})"
            for issue in self.issues
        ]
        return "\n".join([header, *lines])


def validate_orders(orders: pd.DataFrame, today: pd.Timestamp | None = None) -> ValidationReport:
    """Check the content of a loaded orders table and return a report.

    ``today`` is the reference date for the future-date warning (default: the current date).
    Raises SchemaError only if the table lacks expected columns, which is a loading problem
    rather than bad data.
    """
    require_columns(orders.columns)
    today = pd.Timestamp.today().normalize() if today is None else today
    today = _match_time_zone(today, orders["Date"])
    issues: list[Issue] = []

    for column in REQUIRED_VALUE_COLUMNS:
        _add(issues, "missing_value", f"Missing value in column '{column}'",
             orders[column].isna(), column)

    for column in NON_NEGATIVE_COLUMNS:
        _add(issues, "negative_value", f"Negative value in column '{column}'",
             orders[column].lt(0), column)

    issues.extend(_duplicate_order_ids(orders["OrderID"]))

    _add(issues, "zero_quantity", "Quantity is zero", orders["Quantity"].eq(0), "Quantity")
    _add(issues, "future_date", f"Date is after {today.date()}", orders["Date"].gt(today), "Date")

    for column in TEXT_COLUMNS:
        issues.extend(_text_issues(orders[column], column))

    return ValidationReport(issues)


def _match_time_zone(today: pd.Timestamp, dates: pd.Series) -> pd.Timestamp:
    """Give ``today`` the time zone of the dates (or none), so the two can be compared."""
    zone = dates.dt.tz if pd.api.types.is_datetime64_any_dtype(dates) else None
    if zone is not None and today.tzinfo is None:
        return today.tz_localize(zone)
    if zone is None and today.tzinfo is not None:
        return today.tz_localize(None)
    return today


def _add(issues: list[Issue], code: str, message: str, mask: pd.Series, column: str) -> None:
    rows = _lines(mask)
    if rows:
        issues.append(Issue(code, RULES[code], message, rows, column))


def _lines(mask: pd.Series) -> tuple[int, ...]:
    flags = mask.fillna(False).to_numpy(dtype=bool)
    return tuple(int(position) + 2 for position in np.flatnonzero(flags))


def _duplicate_order_ids(order_ids: pd.Series) -> list[Issue]:
    duplicated = order_ids.notna() & order_ids.duplicated(keep=False)
    issues = []
    positions = np.flatnonzero(duplicated.to_numpy(dtype=bool))
    repeated = order_ids[duplicated]
    # One pass over the repeated ids, not one scan of the whole column per id.
    for value, members in sorted(repeated.groupby(repeated).indices.items()):
        rows = tuple(int(positions[member]) + 2 for member in members)
        issues.append(
            Issue("duplicate_order_id", RULES["duplicate_order_id"],
                  f"Duplicate OrderID {value}", rows, "OrderID")
        )
    return issues


def _text_issues(values: pd.Series, column: str) -> list[Issue]:
    text = values.astype("string")
    stripped = text.str.strip()
    issues = []
    _add(issues, "untrimmed_text", f"Leading or trailing spaces in column '{column}'",
         text.ne(stripped), column)

    key = stripped.str.lower()
    # Only the spellings with several variants need a closer look.
    spellings = stripped.groupby(key).nunique()
    for spelling_key in sorted(spellings[spellings > 1].index):
        in_group = key.eq(spelling_key)
        variants = sorted(stripped[in_group].unique())
        if len(variants) > 1:
            shown = ", ".join(repr(variant) for variant in variants)
            issues.append(
                Issue("inconsistent_casing", RULES["inconsistent_casing"],
                      f"Inconsistent casing in column '{column}': {shown}",
                      _lines(in_group), column)
            )
    return issues


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" + ("" if number == 1 else "s")


def _describe_lines(rows: tuple[int, ...]) -> str:
    if len(rows) == 1:
        return f"line {rows[0]}"
    if len(rows) <= MAX_LINES_SHOWN:
        return f"lines {', '.join(map(str, rows[:-1]))} and {rows[-1]}"
    shown = ", ".join(map(str, rows[:MAX_LINES_SHOWN]))
    return f"lines {shown} and {len(rows) - MAX_LINES_SHOWN} more"
