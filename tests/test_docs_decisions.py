"""The decision records must follow their format and be listed in the index."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "docs" / "decisions"
INDEX = DECISIONS / "README.md"
SECTIONS = ["Status", "Context", "Options", "Decision", "Consequences"]
STATUSES = {"Proposed", "Accepted", "Superseded", "Rejected"}
RECORD = re.compile(r"\d{4}-[a-z0-9-]+\.md")


def records() -> list[Path]:
    return sorted(path for path in DECISIONS.iterdir() if RECORD.fullmatch(path.name))


def headings(text: str) -> list[str]:
    return re.findall(r"^## (.+)$", text, re.MULTILINE)


def section(text: str, name: str) -> str:
    start = text.index(f"## {name}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def test_the_folder_has_an_index_and_at_least_the_two_first_records():
    assert INDEX.is_file()
    names = [path.name for path in records()]
    assert "0001-use-pandas.md" in names
    assert "0002-use-streamlit.md" in names


def test_every_file_of_the_folder_is_the_index_or_a_record():
    for path in DECISIONS.iterdir():
        assert path.name == "README.md" or RECORD.fullmatch(path.name), path.name


def test_record_numbers_are_unique_and_follow_each_other():
    numbers = [int(path.name[:4]) for path in records()]
    assert numbers == list(range(1, len(numbers) + 1))


@pytest.mark.parametrize("record", records(), ids=lambda path: path.name)
def test_a_record_has_the_five_sections_in_order(record):
    assert headings(record.read_text()) == SECTIONS


@pytest.mark.parametrize("record", records(), ids=lambda path: path.name)
def test_a_record_title_carries_its_number(record):
    title = record.read_text().splitlines()[0]
    assert re.fullmatch(rf"# {int(record.name[:4])}\. .+", title), title


@pytest.mark.parametrize("record", records(), ids=lambda path: path.name)
def test_a_record_has_a_known_status(record):
    status = section(record.read_text(), "Status").splitlines()[2]
    assert status.split()[0].strip("*.:") in STATUSES, status


@pytest.mark.parametrize("record", records(), ids=lambda path: path.name)
def test_no_section_is_empty(record):
    text = record.read_text()
    for name in SECTIONS:
        body = section(text, name).split("\n", 1)[1].strip()
        assert len(body) > 20, f"{record.name}: '{name}' is empty"


@pytest.mark.parametrize("record", records(), ids=lambda path: path.name)
def test_options_name_what_was_ruled_out(record):
    options = section(record.read_text(), "Options")
    assert len(re.findall(r"^### ", options, re.MULTILINE)) >= 3, "fewer than three options"
    assert "Ruled out" in options or "Chosen" in options


@pytest.mark.parametrize("record", records(), ids=lambda path: path.name)
def test_a_record_says_when_it_would_be_revisited(record):
    consequences = section(record.read_text(), "Consequences")
    paragraph = re.search(r"^\*\*When we would revisit it\.\*\* (.+)$", consequences, re.MULTILINE)
    assert paragraph, "no paragraph starting with 'When we would revisit it.'"
    assert len(paragraph.group(1)) > 40


def test_every_record_is_listed_in_the_index():
    linked = set(re.findall(r"\]\((\d{4}-[a-z0-9-]+\.md)\)", INDEX.read_text()))
    assert linked == {path.name for path in records()}


def test_the_index_lists_each_record_with_its_title_and_status():
    rows = [line for line in INDEX.read_text().splitlines() if re.match(r"\| \[\d{4}", line)]
    assert len(rows) == len(records())
    for record, row in zip(records(), rows, strict=True):
        title = record.read_text().splitlines()[0].split(". ", 1)[1]
        status = section(record.read_text(), "Status").splitlines()[2].split()[0].strip("*.:")
        assert title in row, row
        assert status in row, row


def test_every_link_of_the_index_and_of_the_records_works():
    for page in [INDEX, *records()]:
        for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", page.read_text()):
            if target.startswith("http"):
                continue
            assert (page.parent / target).resolve().exists(), f"{page.name}: {target}"


def test_the_index_describes_the_format_and_how_to_add_a_record():
    text = INDEX.read_text()
    for name in SECTIONS:
        assert name in text
    assert re.search(r"add a (new )?record", text, re.IGNORECASE)


def test_the_pandas_record_matches_the_declared_dependency():
    pyproject = (ROOT / "pyproject.toml").read_text()
    minimum = re.search(r'"pandas>=([\d.]+)"', pyproject).group(1)
    decision = section((DECISIONS / "0001-use-pandas.md").read_text(), "Decision")
    assert f"pandas, version {minimum} or newer" in decision


def test_the_streamlit_record_is_consistent_with_the_architecture_page():
    record = (DECISIONS / "0002-use-streamlit.md").read_text()
    assert "`dashboard`" in record


def test_the_architecture_page_and_the_readme_link_to_the_decisions():
    assert "decisions/README.md" in (ROOT / "docs" / "architecture.md").read_text()
    assert "docs/decisions/README.md" in (ROOT / "README.md").read_text()
