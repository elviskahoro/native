"""Guard: kit files must import siblings relatively so they work when vendored.

Components are copied into user projects under arbitrary packages, so an
absolute ``components.ui.*`` import in ``components/ui`` breaks them.
"""

import ast
from pathlib import Path

import pytest

UI_DIR = Path(__file__).resolve().parent.parent / "components" / "ui"
FILES = sorted(UI_DIR.rglob("*.py"))


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(UI_DIR)))
def test_no_absolute_components_imports(path: Path) -> None:
    offenders = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            mod = node.module or ""
            if mod == "components" or mod.startswith("components."):
                offenders.append(f"line {node.lineno}: from {mod}")
        elif isinstance(node, ast.Import):
            offenders += [
                f"line {node.lineno}: import {a.name}"
                for a in node.names
                if a.name == "components" or a.name.startswith("components.")
            ]
    assert not offenders, f"use relative imports: {offenders}"


def test_kit_imports_when_vendored_under_another_package(tmp_path: Path) -> None:
    """Copy components/ui under ``vendored/web/components`` (no top-level
    ``components`` on the path) and import every module in a subprocess."""
    import shutil
    import subprocess
    import sys

    pkg = tmp_path / "vendored" / "web" / "components"
    shutil.copytree(
        UI_DIR.parent, pkg, ignore=shutil.ignore_patterns("__pycache__")
    )
    for d in (pkg.parent.parent, pkg.parent):
        (d / "__init__.py").touch()

    names = sorted(
        ".".join(p.relative_to(UI_DIR).with_suffix("").parts).removesuffix(".__init__")
        for p in UI_DIR.rglob("*.py")
    )
    code = (
        "import importlib, sys\n"
        "sys.path = [p for p in sys.path if p not in ('', '.')]\n"
        f"sys.path.insert(0, {str(tmp_path / 'vendored')!r})\n"
        f"for n in {names!r}:\n"
        "    importlib.import_module('web.components.ui.' + n if n != 'ui' else 'web.components.ui')\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, cwd=tmp_path
    )
    assert result.returncode == 0, result.stderr[-2000:]
