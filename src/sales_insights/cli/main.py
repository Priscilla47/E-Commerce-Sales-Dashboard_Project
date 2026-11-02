"""The ``sales-insights`` command line.

``sales-insights [options] FILE`` loads an orders CSV file and prints one answer per option,
in the order the options are given. Exit codes: 0 on success, 84 for a usage error or a data
error (the code the first version of the tool already used). Errors go to stderr.
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from typing import NoReturn

import pandas as pd

from sales_insights.ai.forecast import METHOD_LABELS, forecast_with_error
from sales_insights.analytics import breakdowns, products, revenue, timeseries
from sales_insights.data.loader import load_orders
from sales_insights.data.schema import SchemaError
from sales_insights.data.validation import ValidationReport, validate_orders

PROG = "sales-insights"
EXIT_OK = 0
EXIT_ERROR = 84

BY_COLUMNS = {"country": "Country", "category": "Category"}
BY_CHOICES = (*BY_COLUMNS, "month")

EPILOG = """\
Options are answered in the order they are given, one after the other.
Exit codes: 0 on success, 84 for a usage error or a data error (messages go to stderr).

example: sales-insights -T -t 3 data/sample_orders.csv
"""


class _Parser(argparse.ArgumentParser):
    """An argument parser whose usage errors exit with 84 instead of 2."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"{self.prog}: error: {message}\n")


class _Request(argparse.Action):
    """Remember each option with its value, in the order given on the command line."""

    def __call__(self, parser, namespace, values, option_string=None):
        # Options that take no value (nargs=0) are given an empty list.
        value = None if values == [] else values
        namespace.requests = [*(namespace.requests or []), (self.dest, value)]


def build_parser() -> argparse.ArgumentParser:
    """The argument parser of the command."""
    parser = _Parser(
        prog=PROG,
        description="Explore a CSV file of e-commerce orders.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    parser.set_defaults(requests=None)
    parser.add_argument(
        "file", help="CSV file of orders (the columns are listed in docs/data-schema.md)"
    )
    parser.add_argument("-T", dest="total", action=_Request, nargs=0, help="total revenue")
    parser.add_argument(
        "-c",
        dest="customers",
        action=_Request,
        metavar="PRODUCT",
        help="number of unique customers who bought PRODUCT",
    )
    parser.add_argument(
        "-u", dest="unique", action=_Request, nargs=0, help="list the products sold"
    )
    parser.add_argument(
        "-p",
        dest="units",
        action=_Request,
        metavar="PRODUCT",
        help="number of units sold of PRODUCT",
    )
    parser.add_argument(
        "-t",
        dest="top",
        action=_Request,
        type=int,
        metavar="N",
        help="the N best-selling products",
    )
    parser.add_argument(
        "--by",
        dest="by",
        action=_Request,
        choices=BY_CHOICES,
        help="revenue broken down by country, by category or by month",
    )
    parser.add_argument(
        "--forecast",
        dest="forecast",
        action=_Request,
        type=int,
        metavar="N",
        help="forecast the revenue of the next N months (1 to 12), with its error",
    )
    parser.add_argument(
        "--validate",
        dest="validate",
        action=_Request,
        nargs=0,
        help="check the data and print the findings (exit code 84 if it has errors)",
    )
    return parser


# --- the answers, one function per option ---------------------------------------------------


def _total(orders: pd.DataFrame, _value: None) -> None:
    print("Total Revenue: ", revenue.total_revenue(orders))


def _customers(orders: pd.DataFrame, product: str) -> None:
    print("Number of clients that bought: ", product, "=", products.customers_for(orders, product))


def _unique(orders: pd.DataFrame, _value: None) -> None:
    print("Items sold:", products.unique_products(orders))


def _units(orders: pd.DataFrame, product: str) -> None:
    print("Number of", product, "sold: ", products.units_sold_for(orders, product))


def _top(orders: pd.DataFrame, n: int) -> None:
    ranking = products.top_products(orders, n)
    pairs = zip(ranking["Product"], ranking["units"], strict=True)
    for rank, (product, units) in enumerate(pairs, start=1):
        print(rank, "-", product, " sold ", int(units), " times")
    print("Top ", n, ": ", ranking["Product"].tolist())


def _by(orders: pd.DataFrame, what: str) -> None:
    if what == "month":
        table = timeseries.revenue_over_time(orders, "M")
        labels = table["period"].dt.strftime("%Y-%m")
        rows = [
            (label, f"{amount:.2f}", str(count))
            for label, amount, count in zip(labels, table["revenue"], table["orders"], strict=True)
        ]
        _print_table("Revenue by month", ("Month", "Revenue", "Orders"), rows)
        return

    column = BY_COLUMNS[what]
    table = breakdowns.revenue_by(orders, column)
    rows = [
        ("(missing)" if pd.isna(label) else str(label), f"{amount:.2f}", str(count), f"{share:.1%}")
        for label, amount, count, share in zip(
            table[column], table["revenue"], table["orders"], table["share"], strict=True
        )
    ]
    _print_table(f"Revenue by {what}", (column, "Revenue", "Orders", "Share"), rows)


def _print_table(title: str, headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    """Print a table: the first column on the left, the others aligned on the right."""
    print(title)
    if not rows:
        print("(no orders)")
        return
    widths = [max(len(header), *(len(row[i]) for row in rows)) for i, header in enumerate(headers)]
    for cells in (headers, *rows):
        aligned = [
            cell.ljust(widths[i]) if i == 0 else cell.rjust(widths[i])
            for i, cell in enumerate(cells)
        ]
        print("  ".join(aligned).rstrip())


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}%"


def _forecast(orders: pd.DataFrame, months: int) -> None:
    report = forecast_with_error(orders, months)
    forecast = report.forecast
    method = METHOD_LABELS[forecast.method_used]
    rows = [
        (f"{period:%Y-%m}", f"{value:.2f}", f"{low:.2f}", f"{high:.2f}")
        for period, value, low, high in zip(
            forecast.table["period"],
            forecast.table["forecast"],
            forecast.table["lower"],
            forecast.table["upper"],
            strict=True,
        )
    ]
    _print_table(
        f"Revenue forecast ({method} method)", ("Month", "Forecast", "Lower", "Upper"), rows
    )
    warnings = list(forecast.warnings)
    if report.evaluation is None:
        warnings.append(report.note)
    else:
        evaluation = report.evaluation
        last = f"{evaluation.holdout} month{'' if evaluation.holdout == 1 else 's'}"
        model, baseline = evaluation.model, evaluation.baseline
        print(
            f"Error on the last {last}, {method} method: "
            f"MAE {model.mae:.2f}, MAPE {_percent(model.mape)}; "
            f"baseline: MAE {baseline.mae:.2f}, MAPE {_percent(baseline.mape)}"
        )
    for warning in dict.fromkeys(warnings):
        print(f"{PROG}: warning: {warning}", file=sys.stderr)


def _validate(_orders: pd.DataFrame, _value: None, report: ValidationReport) -> None:
    print(report.summary())


_ANSWERS: dict[str, Callable[[pd.DataFrame, object], None]] = {
    "total": _total,
    "customers": _customers,
    "unique": _unique,
    "units": _units,
    "top": _top,
    "by": _by,
    "forecast": _forecast,
}


# --- the command ------------------------------------------------------------------------


def _fail(message: str) -> int:
    print(f"{PROG}: error: {message}", file=sys.stderr)
    return EXIT_ERROR


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command with ``argv`` (default: the process arguments); return the exit code."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if not args.requests:
            parser.error("choose at least one option, for example -T (see -h)")
    except SystemExit as stop:  # -h, or a usage error (already printed)
        return int(stop.code or EXIT_OK)

    try:
        orders = load_orders(args.file)
    except (FileNotFoundError, SchemaError) as error:
        return _fail(str(error))
    except OSError as error:
        return _fail(f"Cannot read {args.file}: {error.strerror or error}")

    report = validate_orders(orders)
    validating = any(name == "validate" for name, _ in args.requests)
    if not report.is_valid and not validating:
        count = len(report.errors)
        print(
            f"{PROG}: warning: {count} error{'' if count == 1 else 's'} found in the data, "
            "so some figures may be unreliable; run with --validate for details",
            file=sys.stderr,
        )

    for name, value in args.requests:
        try:
            if name == "validate":
                _validate(orders, value, report)
            else:
                _ANSWERS[name](orders, value)
        except ValueError as error:
            return _fail(str(error))

    return EXIT_ERROR if validating and not report.is_valid else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
