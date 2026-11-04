"""The four key figures of the dashboard: revenue, orders, average order value and customers.

``compute_kpis`` calls the analytics functions and keeps their exact values; ``format_kpis``
turns them into the texts shown on the page. Rounding happens only there, for display.
"""

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Context, Decimal

import pandas as pd

from sales_insights.analytics.revenue import (
    average_order_value,
    order_count,
    total_revenue,
    unique_customers,
)


@dataclass(frozen=True)
class Kpis:
    """The key figures of a set of orders, as computed (not rounded)."""

    revenue: float
    orders: int
    average_order_value: float
    customers: int


# The default precision of 28 digits refuses amounts above 1e26; 400 holds any float (309 digits).
_WIDE = Context(prec=400)


@dataclass(frozen=True)
class KpiLabels:
    """The key figures as the texts to display."""

    revenue: str
    orders: str
    average_order_value: str
    customers: str


def compute_kpis(df: pd.DataFrame) -> Kpis:
    """The key figures of ``df``; zeros for an empty table."""
    return Kpis(
        revenue=total_revenue(df),
        orders=order_count(df),
        average_order_value=average_order_value(df),
        customers=unique_customers(df),
    )


def format_kpis(kpis: Kpis) -> KpiLabels:
    """The texts to display: thousands separators, and two decimals for money (half up)."""
    return KpiLabels(
        revenue=format_money(kpis.revenue),
        orders=f"{kpis.orders:,}",
        average_order_value=format_money(kpis.average_order_value),
        customers=f"{kpis.customers:,}",
    )


def format_money(value: float) -> str:
    """Money as shown on the cards: two decimals (half up), thousands separators, never -0.00."""
    if not math.isfinite(value):
        return "n/a"
    # Round the decimal text of the number, so that 2.675 gives 2.68 as written on paper.
    amount = Decimal(repr(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP, context=_WIDE)
    if amount == 0:
        amount = abs(amount)  # never "-0.00"
    return f"{amount:,.2f}"
