import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"


def test_the_core_and_the_command_line_import_without_streamlit():
    # Streamlit is an optional extra: hiding it must not break the rest of the project.
    code = (
        "import sys\n"
        "sys.modules['streamlit'] = None\n"
        "import sales_insights\n"
        "import sales_insights.cli.main\n"
        "import sales_insights.analytics.filters\n"
        "import sales_insights.dashboard.data_source\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env={"PYTHONPATH": str(SRC), "PATH": ""},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_streamlit_is_declared_as_an_optional_dependency_only():
    text = (SRC.parent / "pyproject.toml").read_text()
    core = text.split("dependencies = [", 1)[1].split("]", 1)[0]
    assert "streamlit" not in core
    extras = text.split("[project.optional-dependencies]", 1)[1].split("\n[", 1)[0]
    assert "dashboard = [" in extras
    assert "streamlit" in extras.split("dashboard = [", 1)[1].split("]", 1)[0]
