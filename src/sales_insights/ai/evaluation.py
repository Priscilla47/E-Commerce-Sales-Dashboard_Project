"""An evaluation set of questions, and a runner that scores a model on it.

Whether a model answers well depends on the model, so the project ships questions with their
expected functions and values (``data/eval_questions.json``, checked against pandas by the tests)
and this runner, which asks them through the configured provider::

    python -m sales_insights.ai.evaluation [--questions FILE] [--file FILE]

Each question gets its own client, so the limit of calls of a session applies to a question and
not to the whole run.
"""

import argparse
import json
import os
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from sales_insights.ai.config import ConfigError, load_config
from sales_insights.ai.factory import AIDisabled, build_client
from sales_insights.ai.llm import LLMClient, LLMError, ToolCall
from sales_insights.ai.nlq import CANNOT_REASON, MAX_QUESTION_LENGTH, Answer, ask
from sales_insights.ai.tools import ToolError, validate_call
from sales_insights.data.loader import load_orders
from sales_insights.data.schema import SchemaError

PROG = "evaluation"
EXIT_ERROR = 84
DEFAULT_QUESTIONS = "data/eval_questions.json"
DEFAULT_FILE = "data/sample_orders.csv"


_FIELDS = ("question", "expected_calls", "expected_values", "must_refuse")


class CaseError(ValueError):
    """The file of questions cannot be used."""


class _Parser(argparse.ArgumentParser):
    """Usage errors exit with 84, as for the command line, instead of 2."""

    def error(self, message: str):
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"{self.prog}: error: {message}\n")


@dataclass(frozen=True)
class Case:
    """A question, the functions a good answer uses, the values it states, and whether the
    functions cannot answer it (``must_refuse``). Each expected value is a tuple of alternatives,
    any of which is enough."""

    question: str
    expected_calls: tuple[ToolCall, ...]
    expected_values: tuple[tuple[str, ...], ...]
    must_refuse: bool


@dataclass(frozen=True)
class CaseResult:
    case: Case
    passed: bool
    reason: str | None
    answer: Answer | None


@dataclass(frozen=True)
class Report:
    results: tuple[CaseResult, ...]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(result.passed for result in self.results)


def _title(name: str, arguments) -> str:
    return f"{name}({', '.join(f'{k}={v!r}' for k, v in arguments.items())})"


def _case(index: int, item: object) -> Case:
    where = f"Case {index}"
    if not isinstance(item, dict):
        raise CaseError(f"{where} must be an object, not {item!r}")
    for field in _FIELDS:
        if field not in item:
            raise CaseError(f"{where}: missing field '{field}'")
    extra = sorted(set(item) - set(_FIELDS))
    if extra:
        raise CaseError(f"{where}: unknown field '{extra[0]}'")
    question = item["question"]
    if isinstance(question, str):
        question = question.strip()  # as ask() reads it, so " Q? " is a duplicate of "Q?"
    if not isinstance(question, str) or not 1 <= len(question) <= MAX_QUESTION_LENGTH:
        raise CaseError(
            f"{where}: 'question' must be text of 1 to {MAX_QUESTION_LENGTH} characters"
        )
    where = f"{question!r}"
    if not isinstance(item["must_refuse"], bool):
        raise CaseError(f"{where}: 'must_refuse' must be true or false")
    calls = item["expected_calls"]
    if not isinstance(calls, list):
        raise CaseError(f"{where}: 'expected_calls' must be a list")
    expected_calls = []
    for call in calls:
        if not isinstance(call, dict) or set(call) != {"name", "arguments"}:
            raise CaseError(f"{where}: a call has a 'name' and 'arguments'")
        tool_call = ToolCall(call["name"], call["arguments"])
        try:
            validate_call(tool_call)
        except ToolError as error:
            raise CaseError(f"{where}: {error}") from None
        expected_calls.append(tool_call)
    values = item["expected_values"]
    if not isinstance(values, list):
        raise CaseError(f"{where}: 'expected_values' must be a list")
    expected_values = []
    for value in values:
        alternatives = (
            (value,) if isinstance(value, str) else tuple(value) if isinstance(value, list) else ()
        )
        if not alternatives or not all(isinstance(a, str) and a.strip() for a in alternatives):
            raise CaseError(f"{where}: a value is text, or a list of texts of which any will do")
        expected_values.append(alternatives)
    if item["must_refuse"] and (expected_calls or expected_values):
        raise CaseError(
            f"{where}: a case with must_refuse has no expected_calls or expected_values"
        )
    if not item["must_refuse"] and not expected_calls:
        raise CaseError(f"{where}: a case that must be answered needs expected_calls")
    if not item["must_refuse"] and not expected_values:
        raise CaseError(f"{where}: a case that must be answered needs expected_values")
    return Case(question, tuple(expected_calls), tuple(expected_values), item["must_refuse"])


def load_cases(path: str | Path) -> list[Case]:
    """The cases of a JSON file, validated.

    Raises:
        CaseError: the file cannot be read, is not JSON, is empty, or a case is wrong (a missing
            field, a function that is not in the registry, bad arguments, a duplicate question).
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as error:
        raise CaseError(f"Cannot read {path}: {error.strerror or error}") from None
    except (ValueError, RecursionError):  # RecursionError: nested too deep to be a set of cases
        raise CaseError(f"{path} is not valid JSON") from None
    if not isinstance(data, list) or not data:
        raise CaseError(f"{path} must hold a non-empty list of cases")
    cases = [_case(index, item) for index, item in enumerate(data, start=1)]
    seen: set[str] = set()
    for case in cases:
        if case.question in seen:
            raise CaseError(f"The question {case.question!r} appears twice")
        seen.add(case.question)
    return cases


def _judge(case: Case, answer: Answer) -> str | None:
    """Why the answer fails the case, or None when it passes."""
    if answer.error:
        return answer.reason
    if case.must_refuse:
        if answer.answered:
            return f"This question should have been refused, but the model answered: {answer.text}"
        if answer.reason != CANNOT_REASON:  # a blocked answer is not a refusal
            return f"This question should have been refused, but the model tried: {answer.reason}"
        return None
    if not answer.answered:
        return answer.reason
    done = [(call.name, dict(call.arguments)) for call in answer.calls]
    for expected in case.expected_calls:
        if (expected.name, dict(expected.arguments)) not in done:
            called = ", ".join(_title(n, a) for n, a in done) or "nothing"
            wanted = _title(expected.name, expected.arguments)
            return f"Expected {wanted} to be called, but {called} was."
    text = answer.text or ""
    for alternatives in case.expected_values:
        if not any(_states(text, alternative) for alternative in alternatives):
            return f"The text does not state {alternatives[0]!r}."
    return None


def _states(text: str, value: str) -> bool:
    """``value`` is in ``text`` as a whole word or number, read as the number check reads it.

    186 is not in 1,860, 1186 or 186.5, but 500.00 states 500; thousands separators are ignored
    (1,660.0 states 1660.0); ``85.2 %``, ``85.2 percent`` and ``85.2 per cent`` state 85.2%; and a
    name may be written in the plural (Smartphones states Smartphone).
    """
    plain = re.sub(r"(?<=\d),(?=\d{3})", "", text)
    plain = re.sub(r"(?<=\d)\s?(?:%|percent\b|per\s?cent\b)", "%", plain, flags=re.I)
    if any(c.isdigit() for c in value):
        pattern = rf"(?<![\w.]){re.escape(value)}(?:\.0+)?(?!\w|\.\d)"
    else:
        pattern = rf"(?<![\w.]){re.escape(value)}(?:s|es)?(?!\w)"
    return re.search(pattern, plain) is not None


def run_evaluation(
    cases: Sequence[Case], orders: pd.DataFrame, make_client: Callable[[], LLMClient]
) -> Report:
    """Ask every case, with a new client each (so the limit of calls is per question)."""
    results = []
    for case in cases:
        try:
            answer = ask(case.question, orders, make_client())
        except (ValueError, LLMError) as error:
            results.append(CaseResult(case, False, str(error), None))
            continue
        reason = _judge(case, answer)
        results.append(CaseResult(case, reason is None, reason, answer))
    return Report(tuple(results))


def format_report(report: Report) -> str:
    """One line for each case (PASS, or FAIL with the reason) and the total."""
    lines = [
        f"PASS  {r.case.question}" if r.passed else f"FAIL  {r.case.question}: {r.reason}"
        for r in report.results
    ]
    lines.append(f"Passed {report.passed} of {report.total}")
    return "\n".join(lines)


def _fail(message: str) -> int:
    print(f"{PROG}: error: {message}", file=sys.stderr)
    return EXIT_ERROR


def main(argv: Sequence[str] | None = None) -> int:
    """Run the evaluation with the model of the environment; 0 when every case passes, else 84."""
    parser = _Parser(prog=PROG, description="Score a model on the questions.")
    parser.add_argument("--questions", default=DEFAULT_QUESTIONS, help="the file of questions")
    parser.add_argument(
        "--file", default=DEFAULT_FILE, help="the orders file the questions are about"
    )
    args = parser.parse_args(argv)
    try:
        cases = load_cases(args.questions)
        orders = load_orders(args.file)
        config = load_config(os.environ)
        build_client(config)  # fails early, naming the variable to set, when the AI is off
    except (CaseError, ConfigError, AIDisabled, LLMError, SchemaError, FileNotFoundError) as error:
        return _fail(str(error))
    except OSError as error:
        return _fail(f"Cannot read {args.file}: {error.strerror or error}")
    report = run_evaluation(cases, orders, lambda: build_client(config))
    print(format_report(report))
    return 0 if report.passed == report.total else EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
