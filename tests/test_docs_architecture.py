"""The architecture page must describe exactly how the code is organised."""

import ast
import re
import textwrap
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "sales_insights"
SRC = ROOT / "src" / PACKAGE
DOC = (ROOT / "docs" / "architecture.md").read_text()


def section(heading: str) -> str:
    start = DOC.index(f"## {heading}\n")
    end = DOC.find("\n## ", start + 1)
    return DOC[start : end if end != -1 else len(DOC)]


def backticked(text: str) -> list[str]:
    return re.findall(r"`([^`]+)`", text)


def paragraph_packages() -> set[str]:
    """The packages that have a ``### `name` `` paragraph in the page."""
    return {name.strip("`") for name in re.findall(r"^### (`\w+`)", DOC, re.M)}


def documented_rules() -> dict[str, tuple[set[str], set[str]]]:
    """The package table of the page: package -> (packages it may import, packages it must not)."""
    rules = {}
    for line in section("Packages").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("| `") and len(cells) == 4:
            rules[cells[0].strip("`")] = (set(backticked(cells[2])), set(backticked(cells[3])))
    return rules


# --- the import scan --------------------------------------------------------------------


def packages_in(src: Path) -> set[str]:
    return {path.parent.name for path in src.glob("*/__init__.py")}


def is_dynamic_import(call: ast.Call) -> bool:
    """``import_module(...)``, ``importlib.import_module(...)`` or ``__import__(...)``."""
    function = call.func
    name = function.id if isinstance(function, ast.Name) else getattr(function, "attr", "")
    return name in {"import_module", "__import__"}


def imports_of(path: Path, src: Path) -> set[str]:
    """The packages of the project that the module at ``path`` imports, whatever the style.

    Besides ``import`` statements it finds ``import_module("pkg.module")`` and
    ``__import__("pkg.module")`` with a literal name. A name computed at run time cannot be seen.
    """
    package = src.name
    known = packages_in(src)
    here = [package, *path.relative_to(src).parent.parts]  # the package of the module
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            targets = [alias.name.split(".") for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = here[: len(here) - (node.level - 1)] if node.level else []
            module = base + (node.module.split(".") if node.module else [])
            targets = [module]
            if module == [package]:  # from sales_insights import cli
                targets += [[package, alias.name] for alias in node.names]
        elif isinstance(node, ast.Call) and is_dynamic_import(node) and node.args:
            first = node.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue  # a name only known at run time cannot be checked
            targets = [first.value.split(".")]
        else:
            continue
        for target in targets:
            if len(target) > 1 and target[0] == package and target[1] in known:
                found.add(target[1])
    return found


def scan(src: Path) -> dict[str, dict[str, set[str]]]:
    """For each package, each of its modules with the project packages it imports."""
    result = {}
    for package in sorted(packages_in(src)):
        result[package] = {
            str(path.relative_to(src)): imports_of(path, src) - {package}
            for path in sorted((src / package).rglob("*.py"))
        }
    return result


# --- the page and the packages ----------------------------------------------------------


def test_every_package_named_in_the_page_exists():
    named = set(documented_rules()) | paragraph_packages()
    assert named
    for name in named:
        assert (SRC / name / "__init__.py").is_file(), name


def test_every_package_of_the_project_is_in_the_page():
    assert packages_in(SRC) == set(documented_rules())


def test_every_package_has_a_paragraph():
    assert paragraph_packages() == set(documented_rules())


def test_every_module_named_in_the_page_exists():
    for module in re.findall(r"`(\w+\.py)`", section("Packages")):
        assert list(SRC.rglob(module)), module


def test_the_function_names_of_the_page_exist():
    for dotted in re.findall(r"`((?:analytics|data|cli)\.\w+\.\w+)`", DOC):
        package, module, name = dotted.split(".")
        source = (SRC / package / f"{module}.py").read_text()
        assert re.search(rf"^(def|class) {name}\b", source, re.M), dotted


def test_the_table_is_complete():
    names = set(documented_rules())
    for package, (may, must_not) in documented_rules().items():
        assert not may & must_not, package
        assert may | must_not | {package} == names, package


# --- the dependency rule ----------------------------------------------------------------


def test_the_page_keeps_the_rules_that_define_the_architecture():
    """The table can be edited, but not loosened by accident: these rules are pinned here."""
    rules = documented_rules()
    interfaces = {"cli", "dashboard"}
    assert rules["data"][0] == set(), "data imports nothing else of the project"
    assert rules["analytics"][1] >= {"cli", "dashboard", "ai"}, "the core knows no consumer"
    assert rules["ai"][1] >= interfaces, "the AI layer knows no interface"
    for interface in interfaces:
        assert interfaces - {interface} <= rules[interface][1], "interfaces do not use each other"
        assert not rules[interface][0] - {"analytics", "data", "ai"}
    for package, (may, _) in rules.items():
        assert package not in may, f"{package} does not list itself"


def test_analytics_does_not_import_the_interfaces_or_the_ai_layer():
    for module, imported in scan(SRC)["analytics"].items():
        assert not imported & {"cli", "dashboard", "ai"}, module


@pytest.mark.parametrize("package", sorted(packages_in(SRC)))
def test_every_package_respects_the_rule_of_the_page(package):
    may, must_not = documented_rules()[package]
    for module, imported in scan(SRC)[package].items():
        assert not imported & must_not, f"{module} imports {sorted(imported & must_not)}"
        assert imported <= may, f"{module} imports {sorted(imported - may)}"


# --- the scanner itself -----------------------------------------------------------------


@pytest.fixture
def toy(tmp_path):
    """A small project with a package ``alpha`` that imports ``beta`` and ``gamma`` in many ways."""
    src = tmp_path / "toy"
    for name in ("alpha", "beta", "gamma", "delta"):
        (src / name).mkdir(parents=True)
        (src / name / "__init__.py").write_text("")
    return src


def write(src, relative, code):
    (src / relative).write_text(textwrap.dedent(code))
    return src / relative


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("import toy.beta\n", {"beta"}),
        ("import toy.beta.deep as b\n", {"beta"}),
        ("from toy.beta import thing\n", {"beta"}),
        ("from toy.beta.deep import thing\n", {"beta"}),
        ("from toy import gamma\n", {"gamma"}),
        ("from toy import beta, gamma\n", {"beta", "gamma"}),
        ("from .. import beta\n", {"beta"}),
        ("from ..beta import thing\n", {"beta"}),
        ("from ..beta.deep import thing\n", {"beta"}),
        ("def f():\n    import toy.gamma\n", {"gamma"}),
        ("def f():\n    from toy.gamma import thing\n", {"gamma"}),
        ("if False:\n    from toy.delta import thing\n", {"delta"}),
        ("from . import sibling\n", {"alpha"}),
        ("import os\nimport pandas as pd\nfrom pathlib import Path\n", set()),
        ("from toy import __version__\n", set()),
        ("import toy\n", set()),
        ("import beta_extras\nfrom betamax import x\n", set()),
    ],
)
def test_the_scanner_finds_an_import_in_every_style(toy, code, expected):
    module = write(toy, "alpha/module.py", code)
    assert imports_of(module, toy) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ('import importlib\nimportlib.import_module("toy.beta")\n', {"beta"}),
        ('import importlib\nimportlib.import_module("toy.beta.deep")\n', {"beta"}),
        ('from importlib import import_module\nimport_module("toy.gamma")\n', {"gamma"}),
        ('__import__("toy.delta")\n', {"delta"}),
        ('import importlib\nimportlib.import_module("toy", "x")\n', set()),
        ('import importlib\nimportlib.import_module("os.path")\n', set()),
        ("import importlib\nimportlib.import_module(name)\n", set()),
        ('import importlib\nimportlib.import_module(".beta", package="toy.alpha")\n', set()),
        ("def import_module(x):\n    return x\nimport_module('toy.beta')\n", {"beta"}),
    ],
    ids=[
        "import_module",
        "import_module deep",
        "from-imported import_module",
        "__import__",
        "not a package of the project",
        "standard library",
        "name only known at run time",
        "relative name",
        "any function of that name",
    ],
)
def test_the_scanner_finds_an_import_made_by_a_call(toy, code, expected):
    module = write(toy, "alpha/module.py", code)
    assert imports_of(module, toy) == expected


def test_the_scanner_reports_a_violation_planted_in_a_module(toy):
    write(toy, "beta/ok.py", "import toy.alpha\n")
    write(toy, "beta/bad.py", "from toy.gamma import something\n")
    found = scan(toy)["beta"]
    assert found["beta/ok.py"] == {"alpha"}
    assert found["beta/bad.py"] == {"gamma"}


def test_the_scanner_ignores_a_package_importing_itself(toy):
    write(toy, "alpha/one.py", "import toy.alpha.two\nfrom . import two\n")
    assert scan(toy)["alpha"]["alpha/one.py"] == set()


def test_the_scanner_looks_into_subfolders(toy):
    (toy / "alpha" / "inner").mkdir()
    write(toy, "alpha/inner/deep.py", "from ...beta import thing\n")
    assert scan(toy)["alpha"]["alpha/inner/deep.py"] == {"beta"}


def test_the_scanner_finds_the_project_modules_correctly():
    scanned = scan(SRC)
    assert "analytics/products.py" in scanned["analytics"]
    assert scanned["analytics"]["analytics/breakdowns.py"] == {"data"}
    assert scanned["cli"]["cli/main.py"] == {"analytics", "data"}


# --- the diagram ------------------------------------------------------------------------


def diagram() -> str:
    return re.search(r"```mermaid\n(.*?)```", DOC, re.DOTALL).group(1)


NODE = r'(\w+)(?:\["([^"]*)"\])?(?::::\w+)?'
ARROW = r"\s*(?:-->|-\.->)(?:\|[^|]*\|)?\s*"


def diagram_nodes() -> dict[str, str]:
    """Each node id with its label, wherever in a line the node is defined."""
    return {name: label for name, label in re.findall(r'(\w+)\["([^"]*)"\]', diagram())}


def diagram_edges() -> list[tuple[str, str]]:
    """The arrows of the diagram as (from id, to id), also when a line chains several."""
    edges = []
    for line in diagram().splitlines():
        parts = re.split(ARROW, line.strip())
        if len(parts) < 2:
            continue
        ids = [re.fullmatch(NODE, part).group(1) for part in parts]
        edges += list(zip(ids, ids[1:], strict=False))
    return edges


def package_of(label: str) -> str | None:
    """The package a node stands for (``data.storage`` -> ``data``), None for the others."""
    first = label.split("<br/>")[0].split(".")[0].strip()
    return first if first in documented_rules() else None


def test_the_page_has_one_mermaid_diagram_of_a_known_kind():
    assert DOC.count("```mermaid") == 1
    assert diagram().lstrip().startswith("flowchart ")


def test_the_diagram_has_balanced_quotes_and_brackets():
    text = diagram()
    assert text.count('"') % 2 == 0
    assert text.count("[") == text.count("]")
    assert text.count("(") == text.count(")")


def test_every_edge_of_the_diagram_joins_two_defined_nodes():
    nodes = diagram_nodes()
    edges = diagram_edges()
    assert len(edges) >= 9
    for left, right in edges:
        assert left in nodes, left
        assert right in nodes, right


def test_every_node_of_the_diagram_is_connected():
    used = {name for edge in diagram_edges() for name in edge}
    assert set(diagram_nodes()) == used


def test_a_node_is_defined_only_once():
    definitions = re.findall(r'(\w+)\["', diagram())
    assert len(definitions) == len(set(definitions))


def test_every_package_appears_in_the_diagram():
    drawn = {package_of(label) for label in diagram_nodes().values()}
    assert drawn >= set(documented_rules())


def test_the_planned_packages_are_drawn_as_planned():
    text = diagram()
    for package in ("dashboard", "ai"):
        node = re.search(rf'\w+\["{package}<br/>planned"\](:::\w+)?', text)
        assert node and node.group(1) == ":::planned", package
    assert "classDef planned" in text


def test_the_arrows_of_the_diagram_follow_the_dependency_rule():
    """An arrow runs from the producer to the consumer, and the consumer imports the producer."""
    nodes = diagram_nodes()
    checked = 0
    for left, right in diagram_edges():
        source, target = package_of(nodes[left]), package_of(nodes[right])
        if source and target and source != target:
            assert source in documented_rules()[target][0], f"{target} cannot import {source}"
            checked += 1
    assert checked >= 5


# --- the example ------------------------------------------------------------------------


def example_code() -> str:
    steps = section("Add an analytics function")
    return re.search(r"```python\n(.*?)```", steps, re.DOTALL).group(1)


def test_the_example_function_and_its_test_run_on_the_shared_fixture(loaded_orders):
    namespace = {"pd": pd, "pytest": pytest}
    exec(example_code(), namespace)  # noqa: S102 - the code of our own documentation page
    namespace["test_average_units_per_order"](loaded_orders)
    assert namespace["average_units_per_order"](loaded_orders) == pytest.approx(10 / 6)


def test_the_example_does_not_break_the_dependency_rule():
    assert not re.search(r"\b(import|from)\s+sales_insights\.(cli|dashboard|ai)", example_code())


# --- links ------------------------------------------------------------------------------


def test_the_readme_links_to_the_page():
    assert "docs/architecture.md" in (ROOT / "README.md").read_text()
