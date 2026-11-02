import re
import tomllib
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
README = (REPOSITORY / "README.md").read_text()


def section(title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", README, re.S | re.M)
    assert match, f"README has no '## {title}' section"
    return match.group(1)


def test_the_readme_has_a_dashboard_section_before_the_development_section():
    assert README.index("## Dashboard") < README.index("## Development")


def test_the_install_command_names_an_extra_that_exists():
    extras = tomllib.loads((REPOSITORY / "pyproject.toml").read_text())["project"][
        "optional-dependencies"
    ]
    commands = re.findall(r'pip install -e "\.\[(\w+)\]"', section("Dashboard"))
    assert commands == ["dashboard"]
    assert "dashboard" in extras


def test_the_run_command_points_to_an_existing_file():
    commands = re.findall(r"streamlit run (\S+)", section("Dashboard"))
    assert commands, "the section must say how to start the dashboard"
    for command in commands:
        assert (REPOSITORY / command).is_file()


def test_the_section_says_what_the_user_sees_and_the_data_choices():
    text = section("Dashboard")
    assert "Sample data" in text
    assert "Upload a CSV" in text
    assert "localhost:8501" in text
