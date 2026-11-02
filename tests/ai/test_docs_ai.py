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
    names = ("openai", "anthropic", "claude", "gemini", "mistral", "cohere", "llama", "gpt")
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
