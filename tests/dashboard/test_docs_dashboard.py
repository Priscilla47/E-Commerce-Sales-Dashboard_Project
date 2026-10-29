import inspect
import re
from pathlib import Path

import pytest

from sales_insights.dashboard.data_source import describe_problems, load_from_bytes
from sales_insights.data.schema import SchemaError

REPOSITORY = Path(__file__).resolve().parents[2]
PAGE = REPOSITORY / "docs" / "dashboard.md"
TEXT = PAGE.read_text()

# A csv block immediately followed by a text block: the file, and what the dashboard says.
EXAMPLES = re.findall(r"```csv\n(.*?)```\s*\n+(?:[^`\n][^\n]*\n+)?```text\n(.*?)```", TEXT, re.S)


def test_the_page_exists_and_starts_with_its_title():
    assert TEXT.startswith("# Dashboard\n")


def test_the_page_has_at_least_two_examples_to_check():
    assert len(EXAMPLES) >= 2


@pytest.mark.parametrize(("csv", "shown"), EXAMPLES)
def test_what_the_page_shows_is_what_the_dashboard_would_say(csv, shown):
    try:
        loaded = load_from_bytes(csv.encode())
    except SchemaError as error:
        assert shown.strip() == str(error)
    else:
        assert shown.strip().splitlines() == describe_problems(loaded.report)


def test_one_example_is_blocked_and_one_lists_lines():
    kinds = []
    for csv, _ in EXAMPLES:
        try:
            load_from_bytes(csv.encode())
            kinds.append("loaded")
        except SchemaError:
            kinds.append("blocked")
    assert "blocked" in kinds
    assert "loaded" in kinds


def test_the_page_names_the_three_states_and_the_cap():
    for heading in ("### Blocked", "### Loaded with errors", "### Loaded"):
        assert heading in TEXT
    limit = inspect.signature(describe_problems).parameters["limit"].default
    assert f"{limit} lines" in TEXT or f"first {limit}" in TEXT


def test_the_page_names_the_widgets_of_the_sidebar_and_the_cards():
    for name in ("Sample data", "Upload a CSV", "Period", "Countries", "Categories"):
        assert f"**{name}**" in TEXT
    for name in ("Revenue", "Orders", "Average order value", "Customers"):
        assert f"**{name}**" in TEXT


def test_the_run_command_of_the_page_points_to_an_existing_file():
    commands = re.findall(r"streamlit run (\S+)", TEXT)
    assert commands
    assert all((REPOSITORY / command).is_file() for command in commands)


def test_the_links_of_the_page_work():
    links = re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", TEXT)
    assert links
    for link in links:
        if link.startswith("http"):
            continue
        assert (PAGE.parent / link).resolve().exists(), link


def test_the_readme_links_to_the_page():
    assert "docs/dashboard.md" in (REPOSITORY / "README.md").read_text()
