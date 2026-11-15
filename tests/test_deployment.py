"""The container files and the deployment guide, checked as text (the suite runs no Docker)."""

import fnmatch
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


def test_the_base_is_a_slim_python_pinned_to_a_patch_version_that_is_supported():
    (base,) = instructions("FROM")
    match = re.fullmatch(r"python:(3\.\d+)\.\d+-slim", base)
    assert match, base
    required = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["requires-python"]
    minimum = tuple(int(p) for p in required.removeprefix(">=").split("."))
    assert tuple(int(p) for p in match.group(1).split(".")) >= minimum


def test_only_the_dashboard_extra_is_installed_no_development_tools():
    installs = [line for line in instructions("RUN") if "pip install" in line]
    assert installs and all('".[dashboard]"' in line for line in installs)
    assert "[dev" not in DOCKERFILE


def test_the_command_runs_as_a_user_and_group_without_privileges():
    users = instructions("USER")
    match = re.fullmatch(r"(\d+):(\d+)", users[-1]) if users else None
    assert match, users  # numeric, so that the platform can check it is not root
    uid, gid = (int(n) for n in match.groups())
    assert uid >= 1000 and gid >= 1000
    assert DOCKERFILE.index("USER") < DOCKERFILE.index("CMD")
    assert f"--uid {uid}" in DOCKERFILE and f"--gid {gid}" in DOCKERFILE


def test_no_program_of_the_image_keeps_a_setuid_bit():
    assert any("-perm /6000" in line and "chmod a-s" in line for line in instructions("RUN"))


def test_the_dashboard_is_the_command_on_port_8501_with_a_health_check():
    (port,) = instructions("EXPOSE")
    (command,) = instructions("CMD")
    assert "streamlit" in command and "src/sales_insights/dashboard/app.py" in command
    assert (ROOT / "src/sales_insights/dashboard/app.py").is_file()
    assert f"--server.port={port}" in command and "--server.address=0.0.0.0" in command
    (health,) = instructions("HEALTHCHECK")
    assert re.search(rf"http://127\.0\.0\.1:{port}/_stcore/health\b", health), health


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


def ignored(path: str) -> bool:
    """Whether .dockerignore leaves ``path`` out (patterns as Docker reads them, ! re-includes)."""
    result = False
    for line in IGNORE:
        pattern = line.split("#")[0].strip()
        if not pattern:
            continue
        keep = pattern.startswith("!")
        pattern = pattern.lstrip("!").rstrip("/")
        # "**/" matches zero or more folders, as in Docker; a match of a folder covers its files.
        patterns = {pattern, pattern.removeprefix("**/")}
        parts = path.split("/")
        prefixes = ["/".join(parts[: i + 1]) for i in range(len(parts))]
        tails = ["/".join(parts[i:]) for i in range(len(parts))]
        candidates = prefixes + [t for t in tails if "**/" in pattern]
        if any(fnmatch.fnmatch(c, p) for c in candidates for p in patterns):
            result = not keep
    return result


def test_the_build_context_keeps_what_the_image_copies_and_what_pip_needs():
    needed = [s for copy in instructions("COPY") for s in copy.split()[:-1]]
    needed += ["src/sales_insights/__init__.py", "src/sales_insights/dashboard/app.py"]
    for path in needed:
        assert not ignored(path), path


def test_an_egg_info_folder_anywhere_is_left_out():
    assert ignored("src/sales_insights.egg-info/PKG-INFO") and ignored("x.egg-info")


# --- docker-compose.yml -----------------------------------------------------------------------


def test_compose_publishes_the_port_and_reads_env_as_optional():
    assert re.search(r'^\s+- "8501:8501"$', COMPOSE, re.M)
    assert re.search(r"path: \.env\s+required: false", COMPOSE)


def test_compose_hardens_the_container():
    assert "read_only: true" in COMPOSE
    assert re.search(r"cap_drop:\s+- ALL\b", COMPOSE)
    assert re.search(r"security_opt:\s+- no-new-privileges:true\b", COMPOSE)
    assert re.search(r"tmpfs:\s+- /tmp$", COMPOSE, re.M)  # writable, with no size cap


def test_compose_names_the_image_of_the_guide():
    assert re.search(r"^\s+image: sales-insights$", COMPOSE, re.M)
    assert "docker build -t sales-insights ." in GUIDE


# --- the guide --------------------------------------------------------------------------------


def test_the_guide_names_every_variable_of_the_example_file():
    names = re.findall(r"^(\w+)=", (ROOT / ".env.example").read_text(), re.M)
    assert names
    for name in names:
        assert f"`{name}`" in GUIDE, name


def test_the_commands_of_the_guide_use_the_image_and_the_real_cli():
    runs = re.findall(r"^docker run (.*)$", GUIDE, re.M)
    assert runs
    for run in runs:
        words = run.split("#")[0].split()
        options_with_value = {"-p", "-v", "--env-file", "--name", "--tmpfs", "--cap-drop"}
        i = 0
        while words[i].startswith("-"):
            i += 2 if words[i] in options_with_value else 1
        assert words[i] == "sales-insights", run  # the image name of the build and compose
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


def test_the_guide_says_the_ai_needs_a_provider_and_how_to_add_one():
    assert "No provider is installed" in GUIDE and "register_provider" in GUIDE
    assert "ai.md#provider-names" in GUIDE


def test_the_guide_explains_hosts_where_no_new_privileges_cannot_start():
    assert "no-new-privileges" in GUIDE and "operation not permitted" in GUIDE
    assert "Compose 2.24" in GUIDE


def test_the_guide_says_each_check_once():
    assert GUIDE.count("These checks were run on the image") == 1
