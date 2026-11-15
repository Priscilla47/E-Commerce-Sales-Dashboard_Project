"""The container files and the deployment guide, checked as text (the suite runs no Docker)."""

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = (ROOT / "Dockerfile").read_text()
IGNORE = (ROOT / ".dockerignore").read_text().split("\n")
COMPOSE = (ROOT / "docker-compose.yml").read_text()
GUIDE_PATH = ROOT / "docs" / "deployment.md"
GUIDE = GUIDE_PATH.read_text()
README = (ROOT / "README.md").read_text()


def instructions(name: str) -> list[str]:
    """The arguments of every ``name`` instruction of the Dockerfile, continuations joined."""
    joined = re.sub(r"\\\n\s*", " ", DOCKERFILE)
    return [m.group(1).strip() for m in re.finditer(rf"^{name}\s+(.*)$", joined, re.M)]


# --- the Dockerfile ---------------------------------------------------------------------------


def test_the_base_is_a_slim_python_of_a_supported_version():
    (base,) = instructions("FROM")
    match = re.fullmatch(r"python:(3\.\d+)-slim", base)
    assert match, base
    required = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["requires-python"]
    minimum = tuple(int(p) for p in required.removeprefix(">=").split("."))
    assert tuple(int(p) for p in match.group(1).split(".")) >= minimum


def test_only_the_dashboard_extra_is_installed_no_development_tools():
    installs = [line for line in instructions("RUN") if "pip install" in line]
    assert installs and all('".[dashboard]"' in line for line in installs)
    assert "[dev" not in DOCKERFILE


def test_the_command_runs_as_a_user_without_privileges():
    users = instructions("USER")
    assert users and users[-1] not in ("root", "0")
    assert DOCKERFILE.index("USER") < DOCKERFILE.index("CMD")
    assert "useradd" in DOCKERFILE


def test_the_dashboard_is_the_command_on_port_8501_with_a_health_check():
    assert instructions("EXPOSE") == ["8501"]
    (command,) = instructions("CMD")
    assert "streamlit" in command and "src/sales_insights/dashboard/app.py" in command
    assert (ROOT / "src/sales_insights/dashboard/app.py").is_file()
    assert "--server.port=8501" in command and "0.0.0.0" in command
    (health,) = instructions("HEALTHCHECK")
    assert "/_stcore/health" in health


def test_every_file_the_image_copies_exists_and_no_secret_is_copied():
    for copy in instructions("COPY"):
        *sources, _ = copy.split()
        for source in sources:
            assert (ROOT / source).exists(), source
            assert ".env" not in source and "_private" not in source
    assert not re.search(r"^ENV\s.*(KEY|SALES_AI)", DOCKERFILE, re.M)


def test_the_sample_file_sits_where_the_dashboard_looks_for_it():
    # The dashboard finds data/ next to the source: the image keeps that layout.
    copies = instructions("COPY")
    assert "src ./src" in copies
    assert "data/sample_orders.csv ./data/sample_orders.csv" in copies
    assert any("pip install -e" in line for line in instructions("RUN"))


# --- .dockerignore ----------------------------------------------------------------------------


@pytest.mark.parametrize("entry", [".env", ".git", "tests", "_private", ".venv", "venv"])
def test_the_build_context_leaves_out(entry):
    assert entry in IGNORE


def test_the_build_context_keeps_what_the_image_copies():
    for copy in instructions("COPY"):
        *sources, _ = copy.split()
        for source in sources:
            assert source not in IGNORE and source.split("/")[0] not in IGNORE, source


# --- docker-compose.yml -----------------------------------------------------------------------


def test_compose_publishes_the_port_and_reads_env_as_optional():
    assert '"8501:8501"' in COMPOSE
    assert re.search(r"path: \.env\s+required: false", COMPOSE)


def test_compose_hardens_the_container():
    assert "read_only: true" in COMPOSE
    assert re.search(r"cap_drop:\s+- ALL", COMPOSE)
    assert "- /tmp" in COMPOSE


def test_compose_names_the_image_of_the_guide():
    assert "image: sales-insights" in COMPOSE
    assert "docker build -t sales-insights ." in GUIDE


# --- the guide --------------------------------------------------------------------------------


def test_the_guide_names_every_variable_of_the_example_file():
    names = re.findall(r"^(\w+)=", (ROOT / ".env.example").read_text(), re.M)
    assert names
    for name in names:
        assert f"`{name}`" in GUIDE, name


def test_the_commands_of_the_guide_use_the_image_and_the_real_cli():
    runs = re.findall(r"^docker run .*$", GUIDE, re.M)
    assert runs
    assert all(" sales-insights" in run for run in runs)
    assert "sales-insights -T data/sample_orders.csv" in GUIDE
    assert (ROOT / "data/sample_orders.csv").is_file()


def test_the_guide_says_what_a_public_deployment_must_add():
    for word in ("Authentication", "HTTPS", "sticky sessions", "/_stcore/health"):
        assert word in GUIDE, word


def test_the_links_of_the_guide_work():
    links = re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", GUIDE)
    assert links
    for link in links:
        assert (GUIDE_PATH.parent / link).resolve().exists(), link


def test_the_anchors_of_the_guide_exist():
    for page, anchor in re.findall(r"\]\(([^)#]*)#([^)]+)\)", GUIDE):
        target = (GUIDE_PATH.parent / page).resolve() if page else GUIDE_PATH
        headings = re.findall(r"^#+ (.+)$", target.read_text(), re.M)
        slugs = {re.sub(r"[^\w\- ]", "", h).strip().lower().replace(" ", "-") for h in headings}
        assert anchor in slugs, (page, anchor)


def test_the_readme_links_the_guide_and_ticks_the_roadmap():
    assert "docs/deployment.md" in README
    assert "- [x] Docker image and deployment guide" in README
