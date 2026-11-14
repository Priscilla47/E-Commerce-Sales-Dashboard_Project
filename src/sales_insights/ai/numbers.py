"""Checking the numbers of a text against the numbers it is allowed to use.

A text written by a language model is accepted only when every number in it is a number that
code computed. The check reads the text the way a reader does: a number is the whole run of
digits and separators (``2,0,2,5`` is not four small numbers), a date is one token, invisible
characters and other digits than 0 to 9 are read as the digits they show, and what cannot be
checked (``1e5``, ``2 million``, ``½``) is refused.
"""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext

# A run of digits with the separators that can sit between them, so that "2,0,2,5" and "1/2"
# are one token each (and are then refused, because they are no well-formed number).
_TOKEN = re.compile(
    r"(?P<date>(?<![\d.,])\d{4}-\d{2}(?:-\d{2})?(?![\d]))"
    r"|(?P<number>\d(?:[\d,./⁄]*\d)?)"
    r"(?P<exponent>[eE][+-]?\d+)?"
    r"(?P<percent>\s?(?:%|percent\b|per\s?cent\b))?"
    r"(?P<abbreviation>\s?(?:(?:million|billion|trillion|thousand|hundred)s?|bn|k|m|b)\b)?",
    re.IGNORECASE,
)
_WELL_FORMED = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
_DATE_IN_TEXT = re.compile(r"\d{4}-\d{2}(?:-\d{2})?")
_PRECISION = Context(prec=400)  # enough for any float, so that rounding never overflows


@dataclass(frozen=True)
class Allowed:
    """What a text may say.

    ``numbers`` may be written as they are (rounded to 0, 1 or 2 decimals); ``percents`` may be
    written with a percent sign (a share of 0.3 is given here as 30); ``dates`` (``2025-04`` or
    ``2025-04-30``) may be written whole, or as the month of a day; ``names`` are names from the
    data (a product called "Model 3000"), which are skipped when they stand as words.
    """

    numbers: tuple[Decimal, ...] = ()
    percents: tuple[Decimal, ...] = ()
    dates: tuple[str, ...] = ()
    names: tuple[str, ...] = ()


def number(value: float | int) -> Decimal:
    """A number of a result as an exact decimal, without its sign."""
    return Decimal(repr(abs(value)))


def dates_in(text: str) -> list[str]:
    """The dates (``2025-04``, ``2025-04-30``) written in a text of the results."""
    return _DATE_IN_TEXT.findall(text)


def digits_in(text: str) -> list[Decimal]:
    """The numbers written in a text of the results (a note, a period), digit groups only."""
    return [Decimal(found) for found in re.findall(r"\d+(?:\.\d+)?", text)]


@dataclass(frozen=True)
class Leaves:
    """The values of a JSON-ready result, sorted for the check (see ``leaves``)."""

    numbers: tuple[Decimal, ...]
    percents: tuple[Decimal, ...]
    dates: tuple[str, ...]
    texts: tuple[str, ...]  # every other text: names from the data


def leaves(
    data: object,
    *,
    shares: frozenset[str] = frozenset(),
    points: frozenset[str] = frozenset(),
    dated: frozenset[str] = frozenset(),
) -> Leaves:
    """Walk ``data`` (dicts, lists, text, numbers) and sort what it holds.

    Every number may be quoted. A number under a key of ``shares`` (a fraction) may also be
    written as a percent (0.3 as 30%), and one under ``points`` with a percent sign as it is. A
    text under a key of ``dated`` (a period, a note) gives its dates and its digits; every other
    text is a name from the data. Booleans and ``None`` say nothing.
    """
    found: dict[str, list] = {"numbers": [], "percents": [], "dates": [], "texts": []}

    def walk(value: object, key: object) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, int | float):
            found["numbers"].append(number(value))
            if key in shares:
                found["percents"].append(number(value) * 100)
            elif key in points:
                found["percents"].append(number(value))
        elif isinstance(value, dict):
            for name, item in value.items():
                walk(item, name)
        elif isinstance(value, list | tuple):
            for item in value:
                walk(item, key)
        elif isinstance(value, str):
            if key in dated:
                found["numbers"].extend(digits_in(value))
                found["dates"].extend(dates_in(value))
            else:
                found["texts"].append(value)

    walk(data, None)
    return Leaves(*(tuple(found[k]) for k in ("numbers", "percents", "dates", "texts")))


def _normalise(text: str) -> tuple[str, list[str]]:
    """The text with invisible characters removed and every digit written 0 to 9, and the
    characters that are numbers but no digit (``½``, roman numerals), which cannot be checked."""
    text = unicodedata.normalize("NFKC", text)
    kept: list[str] = []
    odd: list[str] = []
    for char in text:
        if unicodedata.category(char) == "Cf":
            continue
        if char.isdigit() and not char.isascii():
            char = str(unicodedata.digit(char))
        elif char.isnumeric() and not char.isascii():
            odd.append(char)
            char = " "
        kept.append(char)
    return "".join(kept), odd


def _without_names(text: str, names: Iterable[str]) -> str:
    """Remove the names that stand as words: never inside another word or number, and never a
    name without a letter (a product called "1" must not remove every 1 of the text)."""
    for name in sorted({n for n in names if any(c.isalpha() for c in n)}, key=len, reverse=True):
        pattern = rf"(?<!\w)(?<!\d[.,]){re.escape(name)}(?!\w)(?![.,]\d)(?!\s?%)"
        text = re.sub(pattern, " ", text)
    return text


def _matches(token: Decimal, decimals: int, allowed: Iterable[Decimal]) -> bool:
    with localcontext(_PRECISION):
        for candidate in allowed:
            if decimals <= 2:
                step = Decimal(1).scaleb(-decimals)
                if candidate.quantize(step, rounding=ROUND_HALF_UP) == token:
                    return True
            elif candidate == token:
                return True
    return False


def _date_allowed(token: str, dates: Iterable[str]) -> bool:
    return any(date == token or date.startswith(token + "-") for date in dates)


def unknown_numbers(text: str, allowed: Allowed) -> list[str]:
    """The numbers of ``text`` that are not allowed, as written, in order, without repeats.

    A number is accepted when it equals an allowed number rounded half up to 0, 1 or 2 decimals
    (more decimals must match exactly), with or without thousands separators; the sign is not
    compared. With a percent sign (``%``, ``percent``) it must be one of ``allowed.percents``.
    A date is accepted when it is one of ``allowed.dates`` (or the month of one). Refused
    whatever their value: a run of digits that is no well-formed number (``2,0,2,5``, ``1/2``),
    scientific notation (``1e5``), an abbreviation (``261k``, ``2 millions``) and a number that
    is not written with digits (``½``). Words for numbers ("two") are not read.
    """
    text, odd = _normalise(text)
    text = _without_names(text, allowed.names)
    unknown: list[str] = []

    def refuse(written: str) -> None:
        if written not in unknown:
            unknown.append(written)

    for found in _TOKEN.finditer(text):
        written = found.group(0).strip()
        if found.group("date"):
            if not _date_allowed(found.group("date"), allowed.dates):
                refuse(written)
            continue
        digits = found.group("number")
        if (
            found.group("exponent")
            or found.group("abbreviation")
            or not _WELL_FORMED.fullmatch(digits)
        ):
            refuse(written)
            continue
        digits = digits.replace(",", "")
        decimals = len(digits.split(".")[1]) if "." in digits else 0
        pool = allowed.percents if found.group("percent") else allowed.numbers
        if not _matches(Decimal(digits), decimals, pool):
            refuse(written)
    for char in odd:
        refuse(char)
    return unknown
