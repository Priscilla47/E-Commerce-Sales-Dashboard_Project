"""Checking the numbers of a text against the numbers it is allowed to use.

Shared by the written insights and the answers to questions: a text is accepted only when every
number in it is a number that code computed.
"""

import re
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

_NUMBER = re.compile(
    r"(?P<number>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<percent>%)?"
    r"(?P<abbreviation>\s?(?:million|billion|thousand|bn|k|m|b)\b)?",
    re.IGNORECASE,
)


def _matches(token: Decimal, decimals: int, percent: bool, allowed: list[Decimal]) -> bool:
    for number in allowed:
        for candidate in (number, number * 100) if percent else (number,):
            if decimals <= 2:
                step = Decimal(1).scaleb(-decimals)
                if candidate.quantize(step, rounding=ROUND_HALF_UP) == token:
                    return True
            elif candidate == token:
                return True
    return False


def unknown_numbers(text: str, allowed: list[Decimal], names: Iterable[str] = ()) -> list[str]:
    """The numbers of ``text`` that are not in ``allowed``, as written, in order, without repeats.

    A number is accepted when it equals an allowed number rounded half up to 0, 1 or 2 decimals
    (more decimals must match exactly), with or without thousands separators; the sign is not
    compared. With a percent sign it may also be a share (0.3 is 30%). An abbreviation (261k,
    2 million) is never accepted, because it cannot be checked. ``names`` (from the data) are
    removed first, longest first, so that a product called "Model 3000" can be quoted.
    """
    allowed = [abs(number) for number in allowed]
    for name in sorted(set(names), key=len, reverse=True):
        if name:
            text = text.replace(name, " ")
    unknown: list[str] = []
    for found in _NUMBER.finditer(text):
        written = found.group(0).strip()
        digits = found.group("number").replace(",", "")
        decimals = len(digits.split(".")[1]) if "." in digits else 0
        accepted = not found.group("abbreviation") and _matches(
            Decimal(digits), decimals, bool(found.group("percent")), allowed
        )
        if not accepted and written not in unknown:
            unknown.append(written)
    return unknown
