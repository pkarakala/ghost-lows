"""Repository rules from CLAUDE.md that can be checked mechanically."""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "ghostlows"

# CLAUDE.md (Stack): the upload app runs these subpackages in Pyodide.
PYODIDE_SUBPACKAGES = ["io", "metrics", "retro"]
PYODIDE_ALLOWED = {"numpy", "pandas"}

# `# SOURCE: <key>[; <key>...]`, each key optionally followed by a locator, e.g. "(Table 1)".
SOURCE_RE = re.compile(r"#\s*SOURCE:\s*(.+)$")


def imported_modules(path: Path, package: str) -> set[str]:
    """Absolute names of the modules a file imports; relative imports resolve against `package`."""
    tree = ast.parse(path.read_text(), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")[: len(package.split(".")) - node.level + 1]
                names.add(".".join(base + ([node.module] if node.module else [])))
            else:
                names.add(node.module)
    return names


def pyodide_safe(module: str) -> bool:
    parts = module.split(".")
    if parts[0] == "ghostlows":
        return len(parts) == 1 or parts[1] in PYODIDE_SUBPACKAGES
    return parts[0] in PYODIDE_ALLOWED or parts[0] in sys.stdlib_module_names


def test_pyodide_safe_classifier():
    assert all(map(pyodide_safe, ["json", "numpy.linalg", "pandas", "ghostlows.metrics"]))
    assert not any(map(pyodide_safe, ["scipy.signal", "simglucose", "ghostlows.sim", "sklearn"]))


def test_relative_imports_resolve(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("from . import tir\nfrom ..sim import env\nimport numpy as np\n")
    assert imported_modules(f, "ghostlows.metrics") == {
        "ghostlows.metrics",
        "ghostlows.sim",
        "numpy",
    }


def module_file(module: str) -> Path | None:
    """Source file of a ghostlows module (package -> its __init__.py)."""
    rel = Path(*module.split("."))
    for candidate in (SRC.parent / rel.with_suffix(".py"), SRC.parent / rel / "__init__.py"):
        if candidate.exists():
            return candidate
    return None


def test_pyodide_closure_imports_only_pyodide_safe_modules():
    """Everything the upload app can reach (io, metrics, retro and every ghostlows module they
    import, with their packages' __init__) imports only the stdlib, numpy and pandas."""
    queue = [f"ghostlows.{sub}" for sub in PYODIDE_SUBPACKAGES]
    queue += [
        ".".join(p.relative_to(SRC.parent).with_suffix("").parts)
        for sub in PYODIDE_SUBPACKAGES
        for p in (SRC / sub).rglob("*.py")
        if p.name != "__init__.py"
    ]
    seen, bad = set(), []
    while queue:
        module = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        path = module_file(module)
        if path is None:
            continue
        # importing a module runs its parent packages' __init__ first
        parts = module.split(".")
        queue += [".".join(parts[:i]) for i in range(2, len(parts))]
        package = module if path.name == "__init__.py" else ".".join(parts[:-1])
        for imported in imported_modules(path, package):
            top = imported.split(".")[0]
            if top == "ghostlows":
                queue.append(imported)
                # `from package import name` may import a submodule called name
                queue += [f"{imported}.{n}" for n in _imported_names(path, imported)]
            elif top not in PYODIDE_ALLOWED and top not in sys.stdlib_module_names:
                bad.append(f"{path.relative_to(ROOT)}: {imported}")
    assert not bad, "non-Pyodide imports reachable from the upload app:\n" + "\n".join(bad)


def _imported_names(path: Path, module: str) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and module.endswith(node.module):
            names += [a.name for a in node.names]
    return names


def citation_keys() -> set[str]:
    """First-column keys of every table in docs/CITATIONS.md."""
    keys = set()
    for line in (ROOT / "docs" / "CITATIONS.md").read_text().splitlines():
        if not line.startswith("|"):
            continue
        first = line.strip("|").split("|")[0].strip()
        if first and first != "Key" and not set(first) <= set("-: "):
            keys.add(first)
    return keys


def split_keys(text: str) -> list[str]:
    """Split a SOURCE comment on ';' outside parentheses, so locators may contain ';'."""
    items, depth, current = [], 0, ""
    for ch in text:
        depth += (ch == "(") - (ch == ")")
        if ch == ";" and depth == 0:
            items.append(current.strip())
            current = ""
        else:
            current += ch
    return [i for i in [*items, current.strip()] if i]


def cites_known_key(item: str, keys: set[str]) -> bool:
    return any(item == k or (item.startswith(k) and item[len(k)] in " ,(:") for k in keys)


def test_citation_keys_parse():
    keys = citation_keys()
    assert {"Facchinetti 2016", "Battelino 2023", "simglucose", "US 11,406,331"} <= keys
    assert cites_known_key("Baysal 2014 (Table 1)", keys)
    assert not cites_known_key("Idi 2025", keys)
    assert split_keys("Baysal 2014 (Table 3; trial set); Cameron 2012") == [
        "Baysal 2014 (Table 3; trial set)",
        "Cameron 2012",
    ]


def test_every_source_comment_cites_a_known_key():
    keys = citation_keys()
    unknown = []
    for folder in ["src", "scripts", "experiments", "app"]:
        for path in sorted((ROOT / folder).rglob("*.py")):
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                match = SOURCE_RE.search(line)
                if not match:
                    continue
                for item in split_keys(match.group(1)):
                    if not cites_known_key(item, keys):
                        unknown.append(f"{path.relative_to(ROOT)}:{lineno}: {item!r}")
    assert not unknown, "SOURCE keys missing from docs/CITATIONS.md:\n" + "\n".join(unknown)
