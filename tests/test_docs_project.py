"""The pages that describe the whole project: README, contribution guide, changelog, templates."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text()
CONTRIBUTING = (ROOT / "CONTRIBUTING.md").read_text()
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
PAGES = {"README.md": README, "CONTRIBUTING.md": CONTRIBUTING, "CHANGELOG.md": CHANGELOG}


STALE = re.compile(
    r"\b(?:is|are)\s+planned\b|\bto come\b(?!\s+(?:up|back|in|out))|\bearly stage\b"
    r"|\bbeing restructured\b|\bwill come once\b",
    re.I,
)


@pytest.mark.parametrize("name", sorted(PAGES))
def test_no_page_calls_a_built_feature_planned_or_to_come(name):
    assert not STALE.search(PAGES[name]), STALE.search(PAGES[name])


def test_the_stale_wording_check_does_not_catch_ordinary_sentences():
    assert not STALE.search("so the change can be planned; ideas to come up with")
    assert STALE.search("The chat page is planned.") and STALE.search("insights to come")


def test_the_package_description_does_not_call_a_feature_planned():
    assert "planned" not in (ROOT / "pyproject.toml").read_text()


def test_the_layout_of_the_readme_lists_every_package_under_the_source():
    layout = re.search(r"## Project layout\n(.*?)\n## ", README, re.S).group(1)
    source = layout[layout.index("src/sales_insights/") : layout.index("tests/")]
    listed = set(re.findall(r"── (\w+)/", source))
    packages = {
        p.name for p in (ROOT / "src" / "sales_insights").iterdir() if (p / "__init__.py").is_file()
    }
    assert listed == packages


def test_the_readme_links_every_guide_the_contribution_guide_and_the_changelog():
    for page in (ROOT / "docs").glob("*.md"):
        assert f"docs/{page.name}" in README, page.name
    assert "CONTRIBUTING.md" in README and "CHANGELOG.md" in README


def slugs(text: str) -> set[str]:
    """The anchors GitHub gives to the headings of a page."""
    headings = re.findall(r"^#+ (.+)$", text, re.M)
    return {re.sub(r"[^\w\- ]", "", h).strip().lower().replace(" ", "-") for h in headings}


@pytest.mark.parametrize("name", sorted(PAGES))
def test_the_links_and_anchors_of_the_page_work(name):
    for page, anchor in re.findall(r"\]\(([^)#\s]*)(?:#([^)\s]+))?\)", PAGES[name]):
        if page.startswith("http"):
            continue
        target = ROOT / page if page else ROOT / name
        assert target.exists(), (name, page)
        if anchor:
            assert anchor in slugs(target.read_text()), (name, page, anchor)


def test_the_contribution_guide_runs_the_checks_of_the_ci():
    install = re.search(r'pip install -e "\.\[(\w+)\]"', CI).group(1)
    assert f'pip install -e ".[{install}]"' in CONTRIBUTING
    assert f'pip install -e ".[{install}]"' in README
    for command in ("ruff check .", "ruff format --check .", "--cov-fail-under=85"):
        assert command in CI and command in CONTRIBUTING, command


def test_the_contribution_guide_names_the_rules_and_the_branch():
    for word in ("Conventional Commits", "develop", "FakeLLM", "Closes #", "72 characters", "Fork"):
        assert word in CONTRIBUTING, word


def test_the_changelog_has_an_unreleased_section_with_added_changed_and_fixed():
    unreleased = re.search(r"## \[Unreleased\]\n(.*?)(?=\n## |\Z)", CHANGELOG, re.S).group(1)
    for heading in ("### Added", "### Changed", "### Fixed"):
        assert heading in unreleased, heading


REPOSITORY = "https://github.com/Priscilla47/E-Commerce-Sales-Dashboard_Project"


def test_every_issue_of_the_changelog_is_a_link_to_that_issue():
    links = re.findall(r"\[#(\d+)\]\(([^)]+)\)", CHANGELOG)
    assert links
    for number, url in links:
        assert url == f"{REPOSITORY}/issues/{number}", (number, url)
    bare = re.findall(r"(?<!\[)#\d+", CHANGELOG)
    assert bare == [], bare  # a bare #n is not a link in a rendered file


def test_the_changelog_fixes_cite_the_three_bug_issues_and_unreleased_has_a_link():
    fixed = re.search(r"### Fixed\n(.*?)(?=\n## |\n\[|\Z)", CHANGELOG, re.S).group(1)
    assert set(re.findall(r"\[#(\d+)\]", fixed)) == {"9", "10", "11"}
    assert f"[Unreleased]: {REPOSITORY}/compare/main...develop" in CHANGELOG


TEMPLATES = sorted((ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))


def test_there_are_templates_for_a_bug_a_feature_and_a_question():
    names = {path.stem for path in TEMPLATES}
    assert {"bug_report", "feature_request", "question", "config"} <= names


@pytest.mark.parametrize("path", [p for p in TEMPLATES if p.stem != "config"], ids=str)
def test_every_issue_template_is_valid_with_a_name_a_description_and_a_body(path):
    form = yaml.safe_load(path.read_text())
    assert form["name"] and form["description"] and form["body"]
    assert "python3 main.py" not in path.read_text()  # the old entry point is gone


def test_the_pull_request_template_asks_for_tests_docs_and_the_issue():
    text = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text()
    for phrase in ("Closes #", "tests", "documentation", "Conventional Commits"):
        assert phrase in text, phrase


def test_the_pages_say_that_ci_is_started_by_hand_and_that_no_provider_ships():
    assert "workflow_dispatch" in CI
    assert "started by hand" in CONTRIBUTING and "started by hand" in README
    assert "no provider" in README and "ai.md#provider-names" in README
