"""The statistical facts as short lines for the page (no Streamlit inside).

These lines are written by code from the facts, so every number in them is a fact; they are shown
when the written insights are switched off, and under the written text for transparency.
"""

import re

from sales_insights.ai.facts import Facts
from sales_insights.dashboard.kpis import format_money


def _plain(text: str) -> str:
    """Escape the characters of ``text`` that Markdown would interpret (it comes from a file)."""
    return re.sub(r"([\\`*_\[\]()<>#|~$])", r"\\\1", text)


def _share(value: float) -> str:
    return f"{value * 100:.1f}%"


def facts_bullets(facts: Facts) -> list[str]:
    """One line for each fact, as Markdown with the text of the data escaped."""
    if facts.orders == 0:
        return ["There are no orders to describe."]
    lines = []
    if facts.period_start is not None:
        lines.append(f"{facts.orders:,} orders from {facts.period_start} to {facts.period_end}.")
    else:
        lines.append(f"{facts.orders:,} orders, none of them with a date.")
    if facts.trend is not None:
        slope = format_money(abs(facts.trend.slope_per_month))
        if facts.trend.direction == "flat":
            lines.append("The monthly revenue is flat: it has no trend of 1% or more a month.")
        else:
            word = "more" if facts.trend.direction == "up" else "less"
            lines.append(
                f"The monthly revenue is trending {facts.trend.direction}: about {slope} {word} "
                "each month."
            )
    if facts.best_month is not None:
        best, worst = facts.best_month, facts.worst_month
        lines.append(f"The best month was {best.period} with {format_money(best.revenue)}.")
        lines.append(f"The worst month was {worst.period} with {format_money(worst.revenue)}.")
    for anomaly in facts.anomalies:
        lines.append(
            f"{anomaly.period} was unusual: {format_money(anomaly.revenue)}, "
            f"{abs(anomaly.z_score):.2f} standard deviations "
            f"{'above' if anomaly.z_score > 0 else 'below'} the average month."
        )
    if facts.anomalies_note:
        lines.append(facts.anomalies_note)
    for change in facts.share_changes:
        lines.append(
            f"{change.column} {_plain(change.value)}: its share of the revenue went from "
            f"{_share(change.first_share)} to {_share(change.second_share)} "
            f"({change.change_points:+.1f} points) between the first and the second half."
        )
    if facts.top_product is not None:
        lines.append(
            f"The best-selling product is {_plain(facts.top_product.name)} with "
            f"{facts.top_product.units:,} units."
        )
    lines.extend(facts.notes)
    return lines
