import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "ai.md"
TEXT = PAGE.read_text()


def section() -> str:
    start = TEXT.index("## Written insights")
    end = TEXT.find("\n## ", start + 1)
    return TEXT[start : end if end != -1 else len(TEXT)]


def test_the_page_has_a_pipeline_diagram_with_the_five_steps():
    diagram = re.search(r"```mermaid\n(.*?)```", section(), re.S).group(1)
    for step in ("data", "facts", "prompt", "text", "check"):
        assert step in diagram.lower(), step
    assert diagram.count("[") == diagram.count("]")
    assert diagram.lstrip().startswith("flowchart ")


def test_the_page_states_the_rules_of_the_check_and_its_limits():
    text = section()
    for phrase in (
        "261,333.44",
        "261k",
        "rounded to 0, 1 or 2 decimals",
        "percent sign",
        "retried once",
        "A year, a month",
        "sign",
        "causes",
        "AIDisabled",
    ):
        assert phrase in text, phrase


def test_the_page_says_what_the_model_receives_and_what_it_does_not():
    text = section().lower()
    assert "never an order" in text or "not the orders" in text
    assert "prompts/insights.txt" in text


def test_the_example_of_the_page_runs_and_says_the_truth(monkeypatch):
    code = re.search(r"```python\n(.*?)```", section(), re.S).group(1)
    namespace: dict = {}
    monkeypatch.chdir(ROOT)
    exec(code, namespace)  # noqa: S102 - the code of our own documentation page
    assert namespace["result"].grounded is True
    assert namespace["rejected"].grounded is False
    assert "37%" in namespace["rejected"].reason
    assert "grounded=True" in section() and "grounded=False" in section()
