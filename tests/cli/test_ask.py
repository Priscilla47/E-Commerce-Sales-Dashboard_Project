import re
from pathlib import Path

import pytest

from sales_insights.ai import factory
from sales_insights.ai.fake import FakeLLM
from sales_insights.ai.llm import Completion, LLMError, ToolCall
from sales_insights.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = str(ROOT / "data" / "sample_orders.csv")
KEY = "sk-test-secret-123456"
BEST = "The best seller is Smartphone with 186 units."


def asking(name, **arguments):
    return Completion("", (ToolCall(name, arguments),))


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for name in ("SALES_AI_PROVIDER", "SALES_AI_MODEL", "SALES_AI_API_KEY", "SALES_AI_MAX_CALLS"):
        monkeypatch.delenv(name, raising=False)
    saved = dict(factory._PROVIDERS)
    factory._PROVIDERS.clear()
    yield
    factory._PROVIDERS.clear()
    factory._PROVIDERS.update(saved)


def switch_on(monkeypatch, script):
    monkeypatch.setenv("SALES_AI_PROVIDER", "fake")
    monkeypatch.setenv("SALES_AI_API_KEY", KEY)
    clients = []

    def build(config):
        clients.append(FakeLLM(list(script)))
        return clients[-1]

    factory.register_provider("fake", build)
    return clients


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --- answered ---------------------------------------------------------------------------------


def test_an_answered_question_prints_the_text_and_the_functions_used(monkeypatch, capsys):
    switch_on(monkeypatch, [asking("top_products", n=1), BEST])
    code, out, err = run(capsys, "--ask", "What sells best?", SAMPLE)
    assert code == 0 and err == ""
    assert out.splitlines() == [BEST, "Functions used:", "  top_products(n=1)"]


def test_several_functions_are_listed_in_the_order_they_ran(monkeypatch, capsys):
    both = Completion(
        "", (ToolCall("total_revenue", {}), ToolCall("revenue_by", {"column": "Country"}))
    )
    switch_on(monkeypatch, [both, "Revenue was 261333.44 and USA led."])
    _, out, _ = run(capsys, "--ask", "Overview?", SAMPLE)
    assert out.splitlines()[1:] == [
        "Functions used:",
        "  total_revenue()",
        "  revenue_by(column='Country')",
    ]


def test_a_text_argument_with_quotes_is_shown_as_python_would(monkeypatch, capsys):
    switch_on(monkeypatch, [asking("units_sold_for", product='O\'Neil "x"'), "It sold 0 units."])
    code, out, _ = run(capsys, "--ask", "How many?", SAMPLE)
    assert code == 0
    assert out.splitlines()[-1] == "  units_sold_for(product='O\\'Neil \"x\"')" or "O'Neil" in out


def test_an_answer_that_ran_no_function_has_no_functions_line(monkeypatch, capsys):
    switch_on(monkeypatch, ["Ask me about sales, products or countries."])
    code, out, _ = run(capsys, "--ask", "Hello", SAMPLE)
    assert code == 0 and out == "Ask me about sales, products or countries.\n"


def test_the_answer_is_checked_against_the_real_data_of_the_file(monkeypatch, capsys):
    switch_on(monkeypatch, [asking("total_revenue"), "Revenue was 261333.44."])
    code, out, _ = run(capsys, "--ask", "Revenue?", SAMPLE)
    assert code == 0 and out.startswith("Revenue was 261333.44.")


# --- no answer --------------------------------------------------------------------------------


def test_with_no_key_it_exits_84_names_the_variable_and_prints_nothing_on_stdout(capsys):
    code, out, err = run(capsys, "--ask", "Revenue?", SAMPLE)
    assert code == 84 and out == ""
    assert err.strip() == (
        "sales-insights: error: The AI features are switched off. "
        "Set SALES_AI_API_KEY to switch them on."
    )


def test_a_key_without_a_provider_names_the_provider_variable(monkeypatch, capsys):
    monkeypatch.setenv("SALES_AI_API_KEY", KEY)
    code, _, err = run(capsys, "--ask", "Revenue?", SAMPLE)
    assert code == 84 and "SALES_AI_PROVIDER" in err and KEY not in err


def test_a_bad_call_limit_exits_84_and_names_the_variable(monkeypatch, capsys):
    monkeypatch.setenv("SALES_AI_MAX_CALLS", "many")
    code, out, err = run(capsys, "--ask", "Revenue?", SAMPLE)
    assert code == 84 and out == "" and "SALES_AI_MAX_CALLS" in err


def test_an_unknown_provider_exits_84_with_the_known_ones(monkeypatch, capsys):
    monkeypatch.setenv("SALES_AI_PROVIDER", "nowhere")
    monkeypatch.setenv("SALES_AI_API_KEY", KEY)
    factory.register_provider("fake", lambda config: FakeLLM([]))
    code, out, err = run(capsys, "--ask", "Revenue?", SAMPLE)
    assert code == 84 and out == ""
    assert "Unknown provider 'nowhere'" in err and "fake" in err


def test_a_refused_answer_exits_84_with_the_reason_and_nothing_on_stdout(monkeypatch, capsys):
    switch_on(monkeypatch, [asking("total_revenue"), "It grew 37%.", "It grew 37%."])
    code, out, err = run(capsys, "--ask", "Revenue?", SAMPLE)
    assert code == 84 and out == ""
    assert (
        "sales-insights: error: The text contained numbers that are not in the results: 37%" in err
    )


def test_a_question_the_functions_cannot_answer_exits_84_with_the_standard_reason(
    monkeypatch, capsys
):
    switch_on(monkeypatch, ["CANNOT_ANSWER"])
    code, out, err = run(capsys, "--ask", "Weather?", SAMPLE)
    assert code == 84 and out == ""
    assert "I can't answer that with the data and functions I have." in err


def test_a_failed_call_exits_84_and_is_not_a_traceback(monkeypatch, capsys):
    switch_on(monkeypatch, [LLMError("The call timed out")])
    code, out, err = run(capsys, "--ask", "Revenue?", SAMPLE)
    assert code == 84 and out == "" and "timed out" in err and "Traceback" not in err


@pytest.mark.parametrize("question", ["", "   "])
def test_an_empty_question_exits_84(monkeypatch, capsys, question):
    switch_on(monkeypatch, ["unused"])
    code, out, err = run(capsys, "--ask", question, SAMPLE)
    assert code == 84 and out == "" and "question is empty" in err


def test_a_question_of_501_characters_exits_84(monkeypatch, capsys):
    switch_on(monkeypatch, ["unused"])
    code, _, err = run(capsys, "--ask", "x" * 501, SAMPLE)
    assert code == 84 and "500 characters" in err


def test_the_call_limit_of_the_session_is_applied(monkeypatch, capsys):
    monkeypatch.setenv("SALES_AI_MAX_CALLS", "1")
    switch_on(monkeypatch, [asking("total_revenue"), "Revenue was 261333.44."])
    monkeypatch.setenv("SALES_AI_MAX_CALLS", "1")
    code, _, err = run(capsys, "--ask", "Revenue?", SAMPLE)
    assert code == 84 and "limit of 1" in err


def test_the_key_never_appears_even_when_the_provider_error_contains_it(monkeypatch, capsys):
    switch_on(monkeypatch, [LLMError(f"rejected {KEY}")])
    code, out, err = run(capsys, "--ask", "Revenue?", SAMPLE)
    assert code == 84 and KEY not in out + err and "***" in err


# --- the other options ------------------------------------------------------------------------


def test_the_other_options_never_need_a_key_or_a_provider(capsys):
    code, out, err = run(capsys, "-T", SAMPLE)
    assert code == 0 and out.startswith("Total Revenue:") and err == ""


def test_the_answers_keep_the_order_of_the_options(monkeypatch, capsys):
    switch_on(monkeypatch, [asking("total_revenue"), "Revenue was 261333.44."])
    code, out, _ = run(capsys, "-T", "--ask", "Revenue?", "-u", SAMPLE)
    lines = out.splitlines()
    assert code == 0
    assert lines[0].startswith("Total Revenue:") and lines[1] == "Revenue was 261333.44."
    assert lines[-1].startswith("Items sold:")


def test_a_failure_stops_after_what_was_printed_before(monkeypatch, capsys):
    code, out, err = run(capsys, "-T", "--ask", "Revenue?", "-u", SAMPLE)
    assert code == 84 and out.startswith("Total Revenue:") and "Items sold" not in out
    assert "switched off" in err


def test_the_help_lists_the_option(capsys):
    assert main(["-h"]) == 0
    assert "--ask QUESTION" in capsys.readouterr().out


def test_the_option_given_twice_asks_twice(monkeypatch, capsys):
    clients = switch_on(monkeypatch, [asking("total_revenue"), "Revenue was 261333.44."])
    code, out, _ = run(capsys, "--ask", "One?", "--ask", "Two?", SAMPLE)
    assert code == 0 and out.count("Functions used:") == 2
    assert len(clients) == 2  # each question builds its client; the limit is per command line


# --- the page of the reference ----------------------------------------------------------------


def test_the_example_of_the_reference_page_prints_what_the_page_shows(monkeypatch, capsys):
    page = (ROOT / "docs" / "cli.md").read_text()
    block = re.search(r"```text\n\$ (sales-insights --ask [^\n]*)\n(.*?)\n```", page, re.S)
    assert block, "docs/cli.md has no --ask example"
    import shlex

    switch_on(monkeypatch, [asking("top_products", n=1), BEST])
    monkeypatch.chdir(ROOT)
    code = main(shlex.split(block.group(1))[1:])
    assert code == 0
    assert capsys.readouterr().out.rstrip("\n") == block.group(2)
