"""The command-line reference must describe exactly what the command does."""

import re
import shlex
from pathlib import Path

import pytest

from sales_insights.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
DOC = (DOCS / "cli.md").read_text()


def section(heading: str) -> str:
    start = DOC.index(f"## {heading}\n")
    end = DOC.find("\n## ", start + 1)
    return DOC[start : end if end != -1 else len(DOC)]


def table_rows(heading: str) -> list[list[str]]:
    """The rows of the first table of a section, as the text of each cell."""
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in section(heading).splitlines()
        if line.startswith("| `")
    ]


def names_in(text: str) -> set[str]:
    return set(re.findall(r"(?<![\w-])(--?[A-Za-z][\w-]*)", text))


# --- options ----------------------------------------------------------------------------


def test_the_options_of_the_help_are_exactly_the_options_of_the_page(monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "100")
    assert main(["-h"]) == 0
    help_lines = capsys.readouterr().out.splitlines()
    in_help = set()
    for line in help_lines:
        if line.startswith("  -"):  # an option line, not a wrapped description
            in_help |= names_in(re.split(r"\s{2,}", line.strip())[0])

    in_doc = set()
    for row in table_rows("Options"):
        in_doc |= names_in(row[0].replace("`", ""))

    assert in_help == in_doc == {"-h", "--help", "-T", "-c", "-u", "-p", "-t", "--by", "--validate"}


def test_every_option_has_an_example():
    commands = [command for command, _ in examples()]
    for option in ("-T", "-u", "-p", "-c", "-t", "--by", "--validate"):
        assert any(option in shlex.split(command) for command in commands), option
    for value in ("country", "category", "month"):
        assert any(value in shlex.split(command) for command in commands), value


# --- examples ---------------------------------------------------------------------------


def examples() -> list[tuple[str, str]]:
    """Each ``$ sales-insights ...`` block of the page as (command, expected output)."""
    return re.findall(r"```console\n\$ (sales-insights [^\n]*)\n(.*?)\n```", DOC, re.DOTALL)


def test_the_page_has_examples():
    assert len(examples()) >= 10


@pytest.mark.parametrize(("command", "expected"), examples(), ids=[c for c, _ in examples()])
def test_every_example_prints_exactly_what_the_page_shows(monkeypatch, capsys, command, expected):
    monkeypatch.chdir(ROOT)  # the examples use the relative path data/sample_orders.csv
    code = main(shlex.split(command)[1:])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.err == ""
    assert captured.out.rstrip("\n") == expected


# --- errors -----------------------------------------------------------------------------

ERROR_SCENARIOS = {
    "the following arguments are required: file": ["-c", "data/sample_orders.csv"],
    "choose at least one option, for example -T (see -h)": ["data/sample_orders.csv"],
    "unrecognized arguments: -x": ["-x", "data/sample_orders.csv"],
    "argument -t: invalid int value: 'abc'": ["-t", "abc", "data/sample_orders.csv"],
    "argument --by: invalid choice: 'colour'": ["--by", "colour", "data/sample_orders.csv"],
    "Wrong number of products": ["-t", "99", "data/sample_orders.csv"],
}


def test_every_documented_error_has_a_scenario():
    documented = {row[0].strip("`") for row in table_rows("Exit codes and errors")}
    assert documented == set(ERROR_SCENARIOS)


@pytest.mark.parametrize(("message", "argv"), ERROR_SCENARIOS.items())
def test_every_documented_error_is_what_the_command_prints(monkeypatch, capsys, message, argv):
    monkeypatch.chdir(ROOT)
    assert main(argv) == 84
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"sales-insights: error: {message}" in captured.err


def test_the_documented_warning_is_what_the_command_prints(capsys, faulty_csv):
    documented = re.search(r"```\n(sales-insights: warning: [^\n]*)\n```", DOC).group(1)
    assert main(["-T", faulty_csv]) == 0
    assert capsys.readouterr().err.strip() == documented


# --- links ------------------------------------------------------------------------------


def slug(heading: str) -> str:
    """The anchor GitHub gives to a heading."""
    return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


@pytest.mark.parametrize("page", ["cli.md", "data-schema.md", "architecture.md"])
def test_the_links_of_the_page_point_to_something_that_exists(page):
    text = (DOCS / page).read_text()
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith("http"):
            continue
        file_part, _, anchor = target.partition("#")
        linked = DOCS / file_part if file_part else DOCS / page
        assert linked.is_file(), target
        if anchor:
            headings = re.findall(r"^#+ (.+)$", linked.read_text(), re.MULTILINE)
            assert anchor in {slug(heading) for heading in headings}, target


def test_the_readme_links_to_the_page():
    assert "docs/cli.md" in (ROOT / "README.md").read_text()
