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


def test_the_section_names_the_cards_and_the_filters_of_the_page():
    text = section("Dashboard")
    for name in ("Revenue", "Orders", "Average order value", "Customers", "Period", "Countries"):
        assert name in text


def test_the_development_install_also_installs_the_dashboard_so_that_no_test_is_skipped():
    extras = tomllib.loads((REPOSITORY / "pyproject.toml").read_text())["project"][
        "optional-dependencies"
    ]
    assert "sales-insights[dashboard]" in extras["dev"]
    assert 'pip install -e ".[dev]"' in section("Development")


def test_the_readme_lists_the_forecast_option_and_the_forecast_tab():
    assert "`--forecast N`" in README
    assert "**Forecast** tab" in section("Dashboard")


def test_the_readme_no_longer_says_the_dashboard_is_on_the_roadmap():
    assert "- [x] Interactive dashboard" in section("Roadmap")
    assert "The dashboard and AI features are on the roadmap" not in README
    assert "(soon) an interactive dashboard" not in README
