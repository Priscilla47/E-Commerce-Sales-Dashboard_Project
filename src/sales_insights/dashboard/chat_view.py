"""The history of the questions of a session, as the page shows it (no Streamlit inside)."""

import json
from dataclasses import dataclass

from sales_insights.ai.nlq import Answer
from sales_insights.ai.tools import ToolResult


@dataclass(frozen=True)
class Turn:
    """A question, its answer, and how many orders (after the filters) it was made from."""

    question: str
    answer: Answer
    orders: int


def call_title(call: ToolResult) -> str:
    """A function that was run with its arguments, on one line: ``top_products(n=1)``."""
    arguments = ", ".join(f"{name}={value!r}" for name, value in call.arguments.items())
    return f"{call.name}({arguments})".replace("\n", " ")


def call_data(call: ToolResult) -> str:
    """What a function returned, as indented JSON, for the reader to check."""
    return json.dumps(call.data, indent=1, ensure_ascii=False, allow_nan=False)


def status_of(turn: Turn) -> str:
    """``answered``, ``refused`` (answered, then refused) or ``failed`` (the call failed)."""
    if turn.answer.answered:
        return "answered"
    return "failed" if turn.answer.error else "refused"
