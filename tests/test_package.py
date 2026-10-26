import importlib
import importlib.util
import re
import tomllib
from pathlib import Path

import pytest

import sales_insights

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
SUBPACKAGES = ["data", "analytics", "cli", "dashboard", "ai"]


def test_package_exposes_a_version_string():
    assert isinstance(sales_insights.__version__, str)
    assert re.fullmatch(r"\d+\.\d+\.\d+", sales_insights.__version__)


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackages_are_importable(name):
    assert importlib.import_module(f"sales_insights.{name}") is not None


def test_console_entry_point_resolves_to_a_callable():
    scripts = tomllib.loads(PYPROJECT.read_text())["project"]["scripts"]
    module_name, function_name = scripts["sales-insights"].split(":")
    entry_point = getattr(importlib.import_module(module_name), function_name)
    assert callable(entry_point)


def test_legacy_root_modules_no_longer_exist():
    root = PYPROJECT.parent
    for name in ("main.py", "calculate.py", "usage.py"):
        assert not (root / name).exists()


def test_the_legacy_analytics_module_no_longer_exists():
    assert importlib.util.find_spec("sales_insights.analytics.legacy") is None
    assert importlib.util.find_spec("sales_insights.cli.usage") is None
