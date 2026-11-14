"""Written insights: a language model words the facts, and code checks every number it wrote.

The model only receives the statistical facts (never the orders). Its text is accepted only when
every number in it is a number of the facts, so an invented figure never reaches the reader. See
``docs/ai.md``.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from importlib.resources import files

from sales_insights.ai.config import API_KEY
from sales_insights.ai.factory import AIDisabled
from sales_insights.ai.facts import Facts
from sales_insights.ai.llm import LLMClient, LLMError, Message
from sales_insights.ai.numbers import Allowed, leaves, unknown_numbers

_MARKER = "=== FACTS ==="
# Text of the facts that is not typed by the data, so its digits (a year, a month) may be quoted.
_SAFE_TEXT = frozenset({"start", "end", "period", "notes", "anomalies_note"})
_SHARES = frozenset({"first_share", "second_share"})  # fractions, written as percents (0.3 is 30%)
_POINTS = frozenset({"change_points"})  # percentage points, which may carry a percent sign


@dataclass(frozen=True)
class Insights:
    """The written insights, or why there are none.

    ``text`` is None and ``grounded`` False when no text could be written or when the text had a
    number that is not in the facts; ``reason`` says why. ``error`` is True when the cause is a
    failed call, which may work next time, and False when the model answered and was refused.
    """

    text: str | None
    grounded: bool
    reason: str | None = None
    error: bool = False  # the model could not be reached: worth trying again later


def _names(facts: Facts) -> tuple[str, ...]:
    """Names from the data: they are quoted as names, digits and all."""
    names = [change.value for change in facts.share_changes]
    if facts.top_product is not None:
        names.append(facts.top_product.name)
    return tuple(name for name in names if name)


def allowed_numbers(facts: Facts) -> Allowed:
    """What a text about ``facts`` may say: their numbers, their shares as percents, their
    dates, every year of their period, and the names of the data."""
    found = leaves(facts.as_dict(), shares=_SHARES, points=_POINTS, dated=_SAFE_TEXT)
    years: tuple[Decimal, ...] = ()
    if facts.period_start is not None:
        first, last = int(facts.period_start[:4]), int(facts.period_end[:4])
        years = tuple(Decimal(year) for year in range(first, last + 1))
    return Allowed(found.numbers + years, found.percents, found.dates, _names(facts))


def check_numbers(text: str, facts: Facts) -> list[str]:
    """The numbers of ``text`` that are not in ``facts``, as written, in order (none: all fine).

    A number is accepted when it equals a number of the facts rounded to 0, 1 or 2 decimals
    (more decimals must match exactly), with or without thousands separators; the sign is not
    compared. A percent must be a share of the facts (0.3 is 30%) or a change in points. A date
    must be one of the facts, a year must be in the period, and the digits of a note may be
    quoted. Everything that cannot be checked (2 million, 1e5, 2,0,2,5) is refused, and names
    from the data are skipped as words, so a product called "Model 3000" can be quoted. The
    rules are those of ``numbers.unknown_numbers``.
    """
    return unknown_numbers(text, allowed_numbers(facts))


def _messages(facts: Facts) -> list[Message]:
    template = files("sales_insights.ai").joinpath("prompts/insights.txt").read_text()
    rules, _, rest = template.partition(_MARKER)
    payload = json.dumps(facts.as_dict(), ensure_ascii=False, indent=1)
    return [
        Message("system", rules.strip()),
        Message("user", rest.strip().replace("{facts}", payload)),
    ]


def _reminder(unknown: list[str]) -> str:
    return (
        f"Your text contains numbers that are not in the facts: {', '.join(unknown)}. "
        "Rewrite it using only numbers from the facts, or none."
    )


def write_insights(facts: Facts, client: LLMClient | None) -> Insights:
    """Ask the model to word ``facts``, check its numbers, and retry once when one is not in them.

    Raises:
        AIDisabled: ``client`` is None (the AI features are switched off).
    """
    if client is None:
        raise AIDisabled(f"The AI features are switched off. Set {API_KEY} to switch them on.")
    if facts.orders == 0:
        return Insights(None, False, "There are no orders, so there is nothing to write about.")
    messages = _messages(facts)
    problem = ""
    for attempt in range(2):
        try:
            text = client.complete(messages).text
        except LLMError as error:
            return Insights(None, False, f"The language model could not answer: {error}", True)
        if not text.strip():
            unknown, problem = [], "The model returned an empty text."
        else:
            unknown = check_numbers(text, facts)
            if not unknown:
                return Insights(text, True)
            problem = f"The text contained numbers that are not in the facts: {', '.join(unknown)}"
        if attempt == 0:
            reminder = (
                _reminder(unknown) if unknown else "Your answer was empty. Write the insights."
            )
            messages = [*messages, Message("assistant", text), Message("user", reminder)]
    return Insights(None, False, problem)
