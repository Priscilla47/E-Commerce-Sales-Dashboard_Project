import re
from pathlib import Path

from sales_insights.ai.config import VARIABLES

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / ".env.example"
PAGE = ROOT / "docs" / "ai.md"


def test_the_env_example_lists_every_variable_that_load_config_reads_and_no_other():
    names = re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", EXAMPLE.read_text(), re.M)
    assert sorted(names) == sorted(VARIABLES)


def test_the_env_example_holds_no_real_looking_key():
    text = EXAMPLE.read_text()
    assert not re.search(r"sk-[A-Za-z0-9]{10,}", text)
    for line in text.splitlines():
        if line.startswith("SALES_AI_API_KEY"):
            assert line.split("=", 1)[1].strip() == ""


def test_every_variable_has_a_comment_above_it():
    lines = EXAMPLE.read_text().splitlines()
    for index, line in enumerate(lines):
        if re.match(r"#?\s*[A-Z][A-Z0-9_]+=", line):
            assert lines[index - 1].startswith("#"), line


def test_env_is_ignored_by_git_but_the_example_is_not():
    ignored = (ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in ignored
    assert ".env.example" not in ignored


def test_the_page_names_every_variable():
    text = PAGE.read_text()
    for name in VARIABLES:
        assert f"`{name}`" in text, name


def test_the_page_states_the_principles_and_the_switched_off_mode():
    text = PAGE.read_text().lower()
    for phrase in ("numbers come from pandas", "switched off", "provider"):
        assert phrase in text, phrase


def test_the_page_records_the_decision_about_provider_names():
    text = PAGE.read_text()
    assert "## Provider names" in text


def test_no_provider_name_appears_in_the_code_or_the_docs_of_the_ai_package():
    # Written in pieces, so that this file does not itself name a provider.
    names = (
        "open" + "ai",
        "anthr" + "opic",
        "cla" + "ude",
        "gem" + "ini",
        "mis" + "tral",
        "co" + "here",
        "lla" + "ma",
        "g" + "pt",
    )
    files = [*(ROOT / "src" / "sales_insights" / "ai").rglob("*.py"), PAGE, EXAMPLE]
    for file in files:
        text = file.read_text().lower()
        for name in names:
            assert name not in text, f"{file.name} names a provider: {name}"


def test_the_links_of_the_page_work():
    for link in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", PAGE.read_text()):
        if not link.startswith("http"):
            assert (PAGE.parent / link).resolve().exists(), link


def test_the_fake_client_example_of_the_page_runs_and_says_the_truth():
    blocks = re.findall(r"```python\n(.*?)```", PAGE.read_text(), re.S)
    example = next(block for block in blocks if "FakeLLM" in block)
    namespace: dict = {}
    exec(example, namespace)  # noqa: S102 - the code of our own documentation page
    assert namespace["fake"].complete.__self__ is namespace["fake"]
    assert [call.messages[0].content for call in namespace["fake"].calls] == ["first", "second"]


def test_the_forecast_example_of_the_page_runs_and_says_the_truth(monkeypatch):
    blocks = re.findall(r"```python\n(.*?)```", PAGE.read_text(), re.S)
    example = next(block for block in blocks if "forecast_revenue" in block)
    namespace: dict = {}
    monkeypatch.chdir(ROOT)
    exec(example, namespace)  # noqa: S102 - the code of our own documentation page
    result = namespace["result"]
    text = PAGE.read_text()
    assert len(result.table) == 3
    assert result.method_used == "naive"  # the comment of the example
    assert result.table["period"].iloc[0] == namespace["orders"]["Date"].max().replace(day=1)
    assert "January to April" in text and str(result.history_months) == "4"
    assert namespace["quality"].model.mae == namespace["quality"].baseline.mae


def test_the_page_names_the_three_months_and_the_24_months_and_the_metrics():
    text = PAGE.read_text()
    for phrase in ("24 months", "At least 3 months", "MAE", "MAPE", "never rounded", "95%"):
        assert phrase in text, phrase


def test_the_facts_example_of_the_page_runs_and_says_the_truth(monkeypatch):
    blocks = re.findall(r"```python\n(.*?)```", PAGE.read_text(), re.S)
    example = next(block for block in blocks if "compute_facts" in block)
    monkeypatch.chdir(ROOT)
    namespace: dict = {}
    exec(example, namespace)  # noqa: S102 - the code of our own documentation page
    facts = namespace["facts"]
    assert (facts.orders, facts.top_product.name) == (500, "Smartphone")
    assert facts.trend.direction == "up" and facts.best_month.period == "2025-04"
    text = PAGE.read_text()
    assert "Smartphone" in text and "2025-04" in text and "500" in text


def test_the_page_states_the_rules_of_the_facts():
    text = PAGE.read_text()
    for phrase in (
        "1% of the mean",
        "more than 2 standard deviations",
        "at least 6 complete months",
        "5 percentage points",
        "first and the second half",
    ):
        assert phrase in text, phrase


def test_the_page_lists_every_function_a_model_may_ask_for_and_the_safety_rules():
    from sales_insights.ai.tools import MAX_ROWS, registry

    text = PAGE.read_text()
    start = text.index("## Functions a model may ask for")
    section = text[
        start : text.find("\n## ", start + 1) if text.find("\n## ", start + 1) != -1 else len(text)
    ]
    for tool in registry():
        assert f"`{tool.name}`" in section, tool.name
    for phrase in (
        f"{MAX_ROWS} rows",
        "No `eval`",
        "closed schema",
        "ToolError",
        "never an instruction",
    ):
        assert phrase in section, phrase


def test_the_questions_section_runs_its_example_and_states_the_limits(monkeypatch):
    text = PAGE.read_text()
    start = text.index("## Questions in plain language")
    end = text.find("\n## ", start + 1)
    section = text[start : end if end != -1 else len(text)]
    code = re.search(r"```python\n(.*?)```", section, re.S).group(1)
    monkeypatch.chdir(ROOT)
    namespace: dict = {}
    exec(code, namespace)  # noqa: S102 - the code of our own documentation page
    assert namespace["answer"].answered is True
    assert namespace["refused"].answered is False
    assert namespace["refused"].reason in section
    for phrase in (
        "at most 3 functions",
        "2 rounds",
        "500 characters",
        "CANNOT_ANSWER",
        "Data, not instructions:",
        "not in the results",
        "never an order row",
    ):
        assert phrase in section, phrase
