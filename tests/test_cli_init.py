"""Regression coverage for ``cli.main.patch_rxconfig`` / ``cmd_init`` idempotency.

Pins the fix for the bug where ``buridan init`` patches the user's
``rxconfig.py`` to inject the ``TailwindV4Plugin`` but is not idempotent: the
guard checked for ``var(--background)`` (a string no CLI path ever writes into
``rxconfig.py``), so every re-run unconditionally appended another
``rx.plugins.TailwindV4Plugin(...)`` entry to ``plugins=[...]`` while the
single-line-only ``_cleanup_duplicate_plugins`` could not remove the
multi-line snippet the CLI itself injects. Repeated ``buridan init`` runs
silently accumulated duplicate plugin registrations in the user's
hand-maintained config, compounding on each run.

The fix replaces the dead sentinel with a direct ``TailwindV4Plugin``
presence check (so the injection is skipped when already configured) and
makes ``_cleanup_duplicate_plugins`` regex-based so it coalesces both
single-line and multi-line constructor forms down to a single entry —
repairing configs already corrupted by the old behavior rather than
compounding the damage.
"""

from __future__ import annotations

import ast
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cli.main import _cleanup_duplicate_plugins, patch_rxconfig
from cli.tailwind_config import TAILWIND_CONFIG_SNIPPET

if TYPE_CHECKING:
    from collections.abc import Generator

# The exact multi-line constructor form the CLI injects into ``plugins=[...]``,
# i.e. ``TAILWIND_CONFIG_SNIPPET`` after ``patch_rxconfig`` strips it.
_INJECTED_SNIPPET = TAILWIND_CONFIG_SNIPPET.strip().rstrip(",")
_IMPORT_STMT = "from reflex.plugins.shared_tailwind import TailwindConfig"

# Number of duplicate plugin registrations a config corrupted by the old,
# non-idempotent ``patch_rxconfig`` would accumulate (one per re-run). Kept as
# a named constant so the regression assertions don't trip ruff's PLR2004.
_CORRUPTED_ENTRY_COUNT = 3


def _count_plugin_calls(content: str) -> int:
    """Count actual ``TailwindV4Plugin(...)`` call sites.

    Uses the trailing ``(`` so the ``TailwindConfig`` import line is never
    mistaken for a plugin registration.
    """
    return content.count("TailwindV4Plugin(")


def _is_valid_python(content: str) -> bool:
    try:
        ast.parse(content)
    except SyntaxError:
        return False
    return True


class TestPatchRxconfigIdempotency:
    """``patch_rxconfig`` must not append a second plugin on re-run."""

    @pytest.fixture  # pyright: ignore[reportUntypedFunctionDecorator]
    def temp_project(self) -> Generator[Path, None, None]:
        """A disposable project directory; tests write their own rxconfig.py."""
        tmpdir = Path(tempfile.mkdtemp())
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def _rxconfig(self, project: Path, body: str) -> Path:
        path = project / "rxconfig.py"
        path.write_text(body)
        return path

    def test_no_plugins_kwarg_idempotent_across_runs(
        self,
        temp_project: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Re-running on a plugin-less config must NOT append a second entry.

        Regression for the reported no-``plugins=`` path
        (``_inject_plugins_into_new``): previously the count grew 1 -> 2 on
        the second run.
        """
        path = self._rxconfig(temp_project, 'config = rx.Config(app_name="demo")')

        patch_rxconfig(path)
        first = path.read_text()
        assert _count_plugin_calls(first) == 1
        assert _IMPORT_STMT in first
        assert "@tailwindcss/typography" in first

        patch_rxconfig(path)
        second = path.read_text()

        assert _count_plugin_calls(second) == 1, "re-run appended a duplicate plugin"
        assert second == first, "re-run changed an already-configured rxconfig.py"
        assert _is_valid_python(second)
        assert "already contains TailwindV4Plugin — skipping" in capsys.readouterr().out

    def test_existing_plugins_kwarg_idempotent_across_runs(
        self,
        temp_project: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A config that already has a ``plugins=`` kwarg must also stay stable.

        Regression for the reported existing-``plugins=`` path
        (``_inject_plugins_into_existing`` unconditionally replacing
        ``plugins=[``): previously the count grew 2 -> 3 on the second run.
        """
        body = (
            "config = rx.Config(\n"
            '    app_name="demo",\n'
            "    plugins=[rx.plugins.SomeOtherPlugin()],\n"
            ")"
        )
        path = self._rxconfig(temp_project, body)

        patch_rxconfig(path)
        first = path.read_text()
        assert _count_plugin_calls(first) == 1
        assert "SomeOtherPlugin" in first  # user's plugin preserved

        patch_rxconfig(path)
        second = path.read_text()

        assert _count_plugin_calls(second) == 1, "re-run appended a duplicate plugin"
        assert "SomeOtherPlugin" in second  # user's plugin still preserved
        assert _is_valid_python(second)
        assert "already contains TailwindV4Plugin — skipping" in capsys.readouterr().out


class TestPatchRxconfigHealCorruption:
    """A config already corrupted by the old bug must be repaired, not worsened."""

    @pytest.fixture  # pyright: ignore[reportUntypedFunctionDecorator]
    def temp_project(self) -> Generator[Path, None, None]:
        tmpdir = Path(tempfile.mkdtemp())
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def _corrupted(
        self,
        project: Path,
        *,
        duplicates: int,
        first_entry: str = "rx.plugins.SomeOtherPlugin()",
        plugin_entry: str = _INJECTED_SNIPPET,
    ) -> Path:
        """Build a valid rxconfig.py mimicking the old bug's accumulated state.

        Each entry carries the trailing comma the CLI's injection always
        appends, so the file stays syntactically valid — which is exactly why
        the old bug went undetected (duplicates kept the file parseable).
        """
        entries = "\n".join(f"{plugin_entry}," for _ in range(duplicates))
        body = (
            f"{_IMPORT_STMT}\n\n"
            "config = rx.Config(\n"
            '    app_name="demo",\n'
            "    plugins=[\n"
            f"{first_entry},\n"
            f"{entries}\n"
            "    ],\n"
            ")\n"
        )
        assert _is_valid_python(body), "corruption fixture must be parseable"
        path = project / "rxconfig.py"
        path.write_text(body)
        return path

    def test_three_duplicate_entries_coalesced_to_one(
        self,
        temp_project: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A config with duplicate plugin entries is repaired down to one.

        Re-running ``buridan init`` must heal configs already corrupted by the
        old, non-idempotent behavior rather than compound the damage.
        """
        path = self._corrupted(temp_project, duplicates=_CORRUPTED_ENTRY_COUNT)
        assert _count_plugin_calls(path.read_text()) == _CORRUPTED_ENTRY_COUNT

        patch_rxconfig(path)

        content = path.read_text()
        assert _count_plugin_calls(content) == 1, "duplicates were not coalesced"
        assert _is_valid_python(content)
        assert "@tailwindcss/typography" in content
        assert "SomeOtherPlugin" in content  # unrelated plugin preserved
        assert "removed duplicate TailwindV4Plugin entries" in capsys.readouterr().out


class TestCleanupDuplicatePlugins:
    """Unit tests for the regex-based coalesce helper.

    Guards against two regressions: (1) reverting to single-line-only cleanup
    that cannot match the multi-line snippet the CLI injects, and (2) the
    coalesce regex becoming too greedy and eating a single entry or
    neighboring plugins.
    """

    def test_single_multi_line_entry_unchanged(self) -> None:
        """A single multi-line entry must not be touched by coalesce."""
        src = f"config = rx.Config(\n    plugins=[\n{_INJECTED_SNIPPET},\n    ],\n)\n"
        assert _cleanup_duplicate_plugins(src) == src

    def test_multi_line_duplicates_coalesced(self) -> None:
        """Duplicate multi-line entries (the form the CLI injects) coalesce
        to a single one and the result stays syntactically valid.
        """
        entries = "\n".join(f"{_INJECTED_SNIPPET}," for _ in range(3))
        src = f"config = rx.Config(\n    plugins=[\n{entries}\n    ],\n)\n"
        assert _is_valid_python(src)
        out = _cleanup_duplicate_plugins(src)
        assert _count_plugin_calls(out) == 1
        assert _is_valid_python(out)

    def test_unrelated_plugins_preserved(self) -> None:
        """Coalescing duplicates must keep neighboring plugins intact and the
        resulting list syntactically valid.
        """
        src = (
            "config = rx.Config(\n"
            "    plugins=[\n"
            "        rx.plugins.SomeOtherPlugin(),\n"
            f"{_INJECTED_SNIPPET},\n"
            f"{_INJECTED_SNIPPET},\n"
            "        rx.plugins.AnotherPlugin(),\n"
            "    ],\n"
            ")\n"
        )
        assert _is_valid_python(src)
        out = _cleanup_duplicate_plugins(src)
        assert _count_plugin_calls(out) == 1
        assert "SomeOtherPlugin" in out
        assert "AnotherPlugin" in out
        assert _is_valid_python(out)
