"""Guard: kit files must import siblings relatively so they work when vendored.

Components are copied into user projects under arbitrary packages, so an
absolute ``components.*`` import anywhere in ``components/`` breaks them.
"""

import ast
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

COMPONENTS_DIR = Path(__file__).resolve().parent.parent / "components"
FILES = sorted(p for p in COMPONENTS_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def _is_components(name: str) -> bool:
    return name == "components" or name.startswith("components.")


@pytest.mark.parametrize(
    "path",
    FILES,
    ids=lambda p: str(p.relative_to(COMPONENTS_DIR)),
)
def test_no_absolute_components_imports(path: Path) -> None:
    offenders: list[str] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            if _is_components(node.module or ""):
                offenders.append(f"line {node.lineno}: from {node.module}")
        elif isinstance(node, ast.Import):
            offenders += [
                f"line {node.lineno}: import {a.name}"
                for a in node.names
                if _is_components(a.name)
            ]
    assert not offenders, f"use relative imports: {offenders}"


def test_kit_imports_when_vendored_under_another_package(tmp_path: Path) -> None:
    """Vendor ``components/`` as ``web.components`` and import every module.

    The subprocess must not be able to resolve a top-level ``components``
    package, otherwise absolute imports would pass silently.
    """
    root = tmp_path / "vendored"
    pkg = root / "web" / "components"
    shutil.copytree(
        COMPONENTS_DIR,
        pkg,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (root / "web" / "__init__.py").touch()

    names = sorted(
        ".".join(p.relative_to(COMPONENTS_DIR).with_suffix("").parts).removesuffix(
            ".__init__",
        )
        for p in FILES
    )
    code = (
        "import importlib, importlib.util, os, sys\n"
        # Drop cwd and any entry (e.g. an editable-install repo root) that
        # exposes a top-level ``components`` package.
        "sys.path = [p for p in sys.path if p not in ('', '.')\n"
        "    and not os.path.isdir(os.path.join(p, 'components'))]\n"
        f"sys.path.insert(0, {str(root)!r})\n"
        "assert importlib.util.find_spec('components') is None, "
        "'test env leaks a top-level components package'\n"
        f"for n in {names!r}:\n"
        "    importlib.import_module('web.components.' + n)\n"
    )
    result = subprocess.run(  # noqa: S603  # nosec B603 - fixed argv, generated code
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
