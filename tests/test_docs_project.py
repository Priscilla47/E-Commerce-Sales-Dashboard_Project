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


@pytest.mark.parametrize("name", sorted(PAGES))
def test_no_page_calls_a_built_feature_planned_or_to_come(name):
    text = PAGES[name].lower()
    for phrase in ("planned", "to come", "early stage", "being restructured", "will come"):
        assert phrase not in text, (name, phrase)


def test_the_package_description_does_not_call_a_feature_planned():
    assert "planned" not in (ROOT / "pyproject.toml").read_text()


def test_the_layout_of_the_readme_lists_every_package():
    layout = re.search(r"## Project layout\n(.*?)\n## ", README, re.S).group(1)
    packages = [p.name for p in (ROOT / "src" / "sales_insights").iterdir() if p.is_dir()]
    for package in packages:
        if package != "__pycache__":
            assert f"{package}/" in layout, package


def test_the_readme_links_every_guide_the_contribution_guide_and_the_changelog():
    for page in (ROOT / "docs").glob("*.md"):
        assert f"docs/{page.name}" in README, page.name
    assert "CONTRIBUTING.md" in README and "CHANGELOG.md" in README


@pytest.mark.parametrize("name", sorted(PAGES))
def test_the_links_of_the_page_work(name):
    for link in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", PAGES[name]):
        if not link.startswith("http"):
            assert (ROOT / link).exists(), (name, link)


def test_the_contribution_guide_runs_the_checks_of_the_ci():
    install = re.search(r'pip install -e "\.\[(\w+)\]"', CI).group(1)
    assert f'pip install -e ".[{install}]"' in CONTRIBUTING
    assert f'pip install -e ".[{install}]"' in README
    for command in ("ruff check .", "ruff format --check .", "--cov-fail-under=85"):
        assert command in CI and command in CONTRIBUTING, command


def test_the_contribution_guide_names_the_rules_and_the_branch():
    for word in ("Conventional Commits", "develop", "FakeLLM", "Closes #", "72 characters"):
        assert word in CONTRIBUTING, word


def test_the_changelog_has_an_unreleased_section_with_added_changed_and_fixed():
    unreleased = re.search(r"## \[Unreleased\]\n(.*?)(?=\n## |\Z)", CHANGELOG, re.S).group(1)
    for heading in ("### Added", "### Changed", "### Fixed"):
        assert heading in unreleased, heading


def test_the_issue_numbers_of_the_changelog_are_well_formed_and_cover_the_fixes():
    numbers = [int(n) for n in re.findall(r"#(\d+)", CHANGELOG)]
    assert numbers and all(0 < n < 1000 for n in numbers)
    fixed = re.search(r"### Fixed\n(.*?)(?=\n## |\Z)", CHANGELOG, re.S).group(1)
    assert {"#9", "#10", "#11"} <= set(re.findall(r"#\d+", fixed))


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
