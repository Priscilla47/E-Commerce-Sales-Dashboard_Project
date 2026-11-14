"""The statistical facts as short lines for the page (no Streamlit inside).

These lines are written by code from the facts, so every number in them is a fact; they are shown
when the written insights are switched off, and under the written text for transparency.
"""

import re

from sales_insights.ai.facts import Facts
from sales_insights.dashboard.kpis import format_money

# ":" only before a character, as in an icon code (:material/home:), not in "line 2: ..."
_ANYWHERE = re.compile(r"([\\`*_\[\]()<>#|~$!]|:(?=\S))")
_LINE_START = re.compile(r"^(\s*)([-+=]|\d+[.)])", re.MULTILINE)
_ADDRESS = re.compile(r"(?i)\bwww\.|//")  # the start of a web address, which is made a link


def plain(text: str) -> str:
    """``text`` (from a file or a model) escaped so that Markdown shows it as written.

    Emphasis, links, images, HTML, tables, maths and icon codes (``:material/x:``) are escaped
    everywhere; lists, rules and headings where a line starts; and a bare address is broken so
    that it is not turned into a link.
    """
    text = _ANYWHERE.sub(r"\\\1", text)
    text = _LINE_START.sub(lambda m: m.group(1) + _escape_marks(m.group(2)), text)
    return _ADDRESS.sub(lambda m: m.group(0)[:-1] + "\\" + m.group(0)[-1], text)


def _escape_marks(start: str) -> str:
    """``1.`` becomes ``1\\.``: a backslash before a digit would be shown, so only marks."""
    return "".join(c if c.isdigit() else "\\" + c for c in start)


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
            f"{change.column} {plain(change.value)}: its share of the revenue went from "
            f"{_share(change.first_share)} to {_share(change.second_share)} "
            f"({change.change_points:+.1f} points) between the first and the second half."
        )
    if facts.top_product is not None:
        lines.append(
            f"The best-selling product is {plain(facts.top_product.name)} with "
            f"{facts.top_product.units:,} units."
        )
    lines.extend(facts.notes)
    return lines
