import csv
import json
from pathlib import Path

import pytest

from sales_insights.ai import factory
from sales_insights.ai.evaluation import (
    Case,
    CaseError,
    Report,
    format_report,
    load_cases,
    main,
    run_evaluation,
)
from sales_insights.ai.llm import Completion, LLMError, Message, ToolCall
from sales_insights.ai.tools import registry
from sales_insights.data.loader import load_orders

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "data" / "eval_questions.json"
SAMPLE = ROOT / "data" / "sample_orders.csv"
KEY = "sk-test-secret-123456"


class Oracle:
    """A model that does what a good one would: it asks for the expected functions and states
    the expected values. ``wrong`` and ``talk`` change what it does for one question."""

    def __init__(self, cases, wrong=None, talk=None, fail=None, forget=None):
        self.by_question = {case.question: case for case in cases}
        self.wrong, self.talk, self.fail, self.forget = wrong, talk, fail, forget
        self.asked: dict[str, int] = {}

    def complete(self, messages, tools=None):
        question = messages[1].content
        case = self.by_question[question]
        step = self.asked.get(question, 0)
        self.asked[question] = step + 1
        if question == self.fail:
            raise LLMError("The call timed out")
        if case.must_refuse and question != self.talk:
            return Completion("CANNOT_ANSWER")
        if question == self.talk:
            return Completion("It will be sunny.")
        if step == 0 and case.expected_calls:
            if question == self.wrong:
                return Completion("", (ToolCall("order_count", {}),))
            return Completion("", tuple(case.expected_calls))
        if question == self.wrong:
            return Completion("There are 500 orders.")
        values = [alternatives[0] for alternatives in case.expected_values]
        if question == self.forget:
            values = values[:-1]
        return Completion("Answer: " + ", ".join(values) + ".")


@pytest.fixture(scope="module")
def cases():
    return load_cases(CASES)


@pytest.fixture(scope="module")
def orders():
    return load_orders(SAMPLE)


def fresh(oracle):
    return lambda: oracle


# --- the shipped set --------------------------------------------------------------------------


def test_the_set_has_between_18_and_25_questions_and_at_least_3_that_must_be_refused(cases):
    assert 18 <= len(cases) <= 25
    assert sum(case.must_refuse for case in cases) >= 3


def test_every_function_of_the_registry_is_used_at_least_once(cases):
    used = {call.name for case in cases for call in case.expected_calls}
    assert used == {tool.name for tool in registry()}


def test_the_questions_are_all_different_and_short_enough(cases):
    questions = [case.question for case in cases]
    assert len(set(questions)) == len(questions)
    assert all(1 <= len(question) <= 500 for question in questions)


def test_a_refused_question_has_no_expected_call_and_no_expected_value(cases):
    for case in cases:
        if case.must_refuse:
            assert case.expected_calls == () and case.expected_values == ()
        else:
            assert case.expected_calls and case.expected_values


def test_running_the_expected_calls_returns_every_expected_value_not_a_hardcoded_guess(
    cases, orders
):
    from sales_insights.ai.nlq import _allowed  # what an answer made of these results may say
    from sales_insights.ai.numbers import unknown_numbers
    from sales_insights.ai.tools import run_tool

    for case in cases:
        results = [run_tool(call, orders) for call in case.expected_calls]
        allowed = _allowed(results, orders)
        text = json.dumps([dict(r.data) for r in results], ensure_ascii=False)
        for alternatives in case.expected_values:
            # A value with digits must pass the number check of an answer; a name must be in
            # the data the functions returned.
            assert any(
                unknown_numbers(alt, allowed) == []
                if any(c.isdigit() for c in alt)
                else alt in text
                for alt in alternatives
            ), (case.question, alternatives)


def test_the_key_figures_of_the_set_are_recomputed_with_plain_pandas_from_the_raw_file(cases):
    with open(SAMPLE, newline="") as handle:
        rows = list(csv.DictReader(handle))
    revenue = [float(r["UnitPrice"]) * int(r["Quantity"]) for r in rows]
    by = {case.question: case for case in cases}

    def values(question):
        return [alts[0] for alts in by[question].expected_values]

    assert values("What is the total revenue?") == [f"{sum(revenue):.2f}"]
    assert values("How many orders are there?") == [str(len({r["OrderID"] for r in rows}))]
    assert values("How many different customers ordered?") == [
        str(len({r["CustomerID"] for r in rows}))
    ]
    assert values("How many units were sold in total?") == [
        str(sum(int(r["Quantity"]) for r in rows))
    ]
    assert values("What is the average order value?") == [f"{sum(revenue) / len(rows):.2f}"]
    laptop = [r for r in rows if r["Product"] == "Laptop"]
    assert values("How many Laptops were sold?") == [str(sum(int(r["Quantity"]) for r in laptop))]
    assert values("How many orders include a Laptop?") == [str(len(laptop))]
    assert values("How many different customers bought a Laptop?") == [
        str(len({r["CustomerID"] for r in laptop}))
    ]
    units: dict[str, int] = {}
    for r in rows:
        units[r["Product"]] = units.get(r["Product"], 0) + int(r["Quantity"])
    ranking = sorted(units.items(), key=lambda item: (-item[1], item[0]))[:3]
    assert values("What are the three best-selling products?") == [
        part for name, count in ranking for part in (name, str(count))
    ]
    country: dict[str, float] = {}
    category: dict[str, float] = {}
    for r, amount in zip(rows, revenue, strict=True):
        country[r["Country"]] = country.get(r["Country"], 0) + amount
        category[r["Category"]] = category.get(r["Category"], 0) + amount
    first, second = sorted(country.items(), key=lambda item: -item[1])[:2]
    assert values("Which country sold the most?") == [first[0], f"{first[1]:.2f}"]
    assert values("Which country is second by revenue?") == [second[0], f"{second[1]:.2f}"]
    best = max(category.items(), key=lambda item: item[1])
    assert values("Which category brings the most revenue?") == [best[0], f"{best[1]:.2f}"]
    month: dict[str, float] = {}
    orders_in: dict[str, set] = {}
    for r, amount in zip(rows, revenue, strict=True):
        key = r["Date"][:7]
        month[key] = month.get(key, 0) + amount
        orders_in.setdefault(key, set()).add(r["OrderID"])
    peak = max(month.items(), key=lambda item: item[1])
    assert values("Which month had the highest revenue?")[1] == f"{peak[1]:.2f}"
    assert values("What was the revenue in February 2025?") == [f"{month['2025-02']:.2f}"]
    assert values("How many orders were placed in March 2025?") == [str(len(orders_in["2025-03"]))]


# --- load_cases -------------------------------------------------------------------------------


def write(tmp_path, data):
    path = tmp_path / "cases.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    return path


GOOD = {
    "question": "How many orders?",
    "expected_calls": [{"name": "order_count", "arguments": {}}],
    "expected_values": ["500"],
    "must_refuse": False,
}


def test_a_valid_file_gives_cases_with_calls_and_alternatives(tmp_path):
    case = load_cases(write(tmp_path, [{**GOOD, "expected_values": [["500", "five hundred"]]}]))[0]
    assert isinstance(case, Case)
    assert case.expected_calls == (ToolCall("order_count", {}),)
    assert case.expected_values == (("500", "five hundred"),)


@pytest.mark.parametrize("field", ["question", "expected_calls", "expected_values", "must_refuse"])
def test_a_missing_field_is_refused_and_named(tmp_path, field):
    broken = {k: v for k, v in GOOD.items() if k != field}
    with pytest.raises(CaseError, match=field):
        load_cases(write(tmp_path, [broken]))


def test_an_unknown_function_is_refused_and_the_case_is_named(tmp_path):
    bad = {**GOOD, "expected_calls": [{"name": "eval", "arguments": {}}]}
    with pytest.raises(CaseError, match="How many orders.*Unknown function"):
        load_cases(write(tmp_path, [bad]))


def test_bad_arguments_are_refused(tmp_path):
    bad = {**GOOD, "expected_calls": [{"name": "top_products", "arguments": {"n": "3"}}]}
    with pytest.raises(CaseError, match="n"):
        load_cases(write(tmp_path, [bad]))


def test_a_duplicate_question_is_refused(tmp_path):
    with pytest.raises(CaseError, match="twice"):
        load_cases(write(tmp_path, [GOOD, GOOD]))


@pytest.mark.parametrize("text", ["", "[]", "{}", "not json", "[1]", '[{"question": 5}]'])
def test_an_empty_or_broken_file_is_refused_with_a_message_not_a_traceback(tmp_path, text):
    with pytest.raises(CaseError):
        load_cases(write(tmp_path, text))


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(CaseError, match="Cannot read"):
        load_cases(tmp_path / "nowhere.json")


def test_a_case_that_must_be_refused_cannot_have_expected_calls_or_values(tmp_path):
    bad = {**GOOD, "must_refuse": True}
    with pytest.raises(CaseError, match="must_refuse"):
        load_cases(write(tmp_path, [bad]))


def test_a_case_that_must_be_answered_needs_a_call_and_a_value(tmp_path):
    with pytest.raises(CaseError, match="expected_calls"):
        load_cases(write(tmp_path, [{**GOOD, "expected_calls": []}]))
    with pytest.raises(CaseError, match="expected_values"):
        load_cases(write(tmp_path, [{**GOOD, "expected_values": []}]))


# --- run_evaluation ---------------------------------------------------------------------------


def test_a_good_model_passes_every_case_of_the_shipped_set(cases, orders):
    report = run_evaluation(cases, orders, fresh(Oracle(cases)))
    assert isinstance(report, Report)
    assert (report.passed, report.total) == (len(cases), len(cases))
    assert all(result.reason is None for result in report.results)


def test_a_model_that_calls_the_wrong_function_fails_exactly_that_case_and_says_which_was_expected(
    cases, orders
):
    question = "What is the total revenue?"
    report = run_evaluation(cases, orders, fresh(Oracle(cases, wrong=question)))
    failed = [r for r in report.results if not r.passed]
    assert [r.case.question for r in failed] == [question]
    assert "total_revenue()" in failed[0].reason and "order_count()" in failed[0].reason


def test_a_missing_expected_value_fails_and_names_it(cases, orders):
    question = "What are the three best-selling products?"
    report = run_evaluation(cases, orders, fresh(Oracle(cases, forget=question)))
    failed = [r for r in report.results if not r.passed]
    assert [r.case.question for r in failed] == [question]
    assert "175" in failed[0].reason or "Desk Lamp" in failed[0].reason


def test_an_answer_to_a_question_that_must_be_refused_fails(cases, orders):
    question = "What will the weather be tomorrow?"
    report = run_evaluation(cases, orders, fresh(Oracle(cases, talk=question)))
    failed = [r for r in report.results if not r.passed]
    assert [r.case.question for r in failed] == [question]
    assert "should have been refused" in failed[0].reason


def test_a_refusal_of_a_question_that_must_be_answered_fails(cases, orders):
    class Refuser(Oracle):
        def complete(self, messages, tools=None):
            return Completion("CANNOT_ANSWER")

    report = run_evaluation(cases, orders, fresh(Refuser(cases)))
    must_answer = [r for r in report.results if not r.case.must_refuse]
    assert all(not r.passed for r in must_answer)
    assert all(r.passed for r in report.results if r.case.must_refuse)
    assert "I can't answer that" in must_answer[0].reason


def test_a_failed_call_is_a_failure_with_its_reason_and_the_others_still_run(cases, orders):
    question = "How many orders are there?"
    report = run_evaluation(cases, orders, fresh(Oracle(cases, fail=question)))
    failed = [r for r in report.results if not r.passed]
    assert [r.case.question for r in failed] == [question]
    assert "timed out" in failed[0].reason and report.passed == len(cases) - 1


def test_each_case_gets_its_own_client_so_the_limit_of_calls_is_per_question(cases, orders):
    built = []

    def make():
        built.append(1)
        return Oracle(cases)

    run_evaluation(cases[:5], orders, make)
    assert len(built) == 5


def test_the_alternatives_of_a_value_are_any_of(cases, orders):
    case = Case(
        "How many orders are there?",
        (ToolCall("order_count", {}),),
        (("500", "five hundred"),),
        False,
    )

    class Says:
        def complete(self, messages, tools=None):
            if len(messages) == 2:
                return Completion("", (ToolCall("order_count", {}),))
            return Completion("There are 500 orders.")

    assert run_evaluation([case], orders, lambda: Says()).passed == 1


def test_a_value_is_found_with_thousands_separators_removed(orders):
    case = Case("Revenue?", (ToolCall("total_revenue", {}),), (("261333.44",),), False)

    class Says:
        def complete(self, messages, tools=None):
            if len(messages) == 2:
                return Completion("", (ToolCall("total_revenue", {}),))
            return Completion("Revenue was 261,333.44.")

    assert run_evaluation([case], orders, lambda: Says()).passed == 1


def test_the_report_text_has_a_line_for_each_case_and_the_total(cases, orders):
    report = run_evaluation(cases, orders, fresh(Oracle(cases, wrong="What is the total revenue?")))
    lines = format_report(report).splitlines()
    assert len(lines) == len(cases) + 1
    assert lines[0] == "FAIL  What is the total revenue?"[: len(lines[0])] or lines[0].startswith(
        "FAIL"
    )
    assert lines[-1] == f"Passed {len(cases) - 1} of {len(cases)}"
    assert sum(line.startswith("PASS") for line in lines) == len(cases) - 1


# --- the script -------------------------------------------------------------------------------


@pytest.fixture
def provider(monkeypatch, cases):
    for name in ("SALES_AI_PROVIDER", "SALES_AI_MODEL", "SALES_AI_API_KEY", "SALES_AI_MAX_CALLS"):
        monkeypatch.delenv(name, raising=False)
    saved = dict(factory._PROVIDERS)
    factory._PROVIDERS.clear()
    yield lambda **kwargs: (
        monkeypatch.setenv("SALES_AI_PROVIDER", "fake"),
        monkeypatch.setenv("SALES_AI_API_KEY", KEY),
        factory.register_provider("fake", lambda config: Oracle(cases, **kwargs)),
    )
    factory._PROVIDERS.clear()
    factory._PROVIDERS.update(saved)


def test_the_script_passes_a_good_model_prints_a_line_each_and_exits_0(provider, capsys):
    provider()
    code = main(["--questions", str(CASES), "--file", str(SAMPLE)])
    out = capsys.readouterr().out.splitlines()
    assert code == 0
    assert out[-1] == "Passed 24 of 24" and len(out) == 25
    assert all(line.startswith("PASS") for line in out[:-1])


def test_the_script_exits_84_when_a_case_fails(provider, capsys):
    provider(wrong="What is the total revenue?")
    code = main(["--questions", str(CASES), "--file", str(SAMPLE)])
    out = capsys.readouterr().out
    assert code == 84 and "Passed 23 of 24" in out and "FAIL" in out


def test_the_script_with_the_ai_switched_off_exits_84_and_names_the_variable(provider, capsys):
    code = main(["--questions", str(CASES), "--file", str(SAMPLE)])
    captured = capsys.readouterr()
    assert code == 84 and captured.out == ""
    assert "SALES_AI_API_KEY" in captured.err


def test_the_script_with_a_bad_file_of_questions_exits_84_with_a_message(
    provider, capsys, tmp_path
):
    provider()
    broken = tmp_path / "bad.json"
    broken.write_text("not json")
    code = main(["--questions", str(broken), "--file", str(SAMPLE)])
    captured = capsys.readouterr()
    assert code == 84 and captured.out == "" and "evaluation: error:" in captured.err


def test_the_script_never_prints_the_key(provider, capsys):
    provider(fail="How many orders are there?")
    main(["--questions", str(CASES), "--file", str(SAMPLE)])
    captured = capsys.readouterr()
    assert KEY not in captured.out + captured.err


def test_the_script_with_a_missing_data_file_exits_84(provider, capsys, tmp_path):
    provider()
    code = main(["--questions", str(CASES), "--file", str(tmp_path / "nowhere.csv")])
    assert code == 84 and "evaluation: error:" in capsys.readouterr().err


def test_the_messages_sent_never_contain_an_order_row(cases, orders):
    seen: list[list[Message]] = []

    class Spy(Oracle):
        def complete(self, messages, tools=None):
            seen.append(list(messages))
            return super().complete(messages, tools)

    run_evaluation(cases[:6], orders, fresh(Spy(cases)))
    text = " ".join(m.content for call in seen for m in call)
    assert "CUST" not in text and "OrderID" not in text


@pytest.mark.parametrize(
    "text, value, states",
    [
        ("Smartphone sold 186 units.", "186", True),
        ("Revenue was 1,660.0.", "1660.0", True),
        ("It sold 1,860 units.", "186", False),
        ("It sold 1186 units.", "186", False),
        ("It was 186.5.", "186", False),
        ("The best month was 2025-04.", "2025-04", True),
        ("Laptops led.", "Laptop", False),
        ("Laptop led.", "Laptop", True),
    ],
)
def test_a_value_is_stated_only_as_a_whole_word_or_number(text, value, states):
    from sales_insights.ai.evaluation import _states

    assert _states(text, value) is states
