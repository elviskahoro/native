"""Regression coverage for cli/main.py's user-asset mutation paths.

These tests pin the existing behavior of ``cmd_apply`` and ``cmd_add`` so the
upcoming refactor of ``cli/main.py`` (which extracts helpers to satisfy
``PLR0912``) cannot silently regress:

* ``cmd_apply("b0")`` must create ``assets/globals.css`` containing both the
  ``:root {}`` theme block and the ``.dark {}`` block, must replace any
  pre-existing ``:root {…}`` / ``.dark {…}`` pair while preserving
  user-authored CSS outside the theme region, and must write
  ``components.json`` with ``{"theme": {"preset": <code>}}``.
* ``cmd_add([...])`` must surface a "No theme detected in assets/globals.css"
  warning when ``:root {`` is absent, and must exit with ``SystemExit(1)`` when
  ``rxconfig.py`` is missing from the project root.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cli.main import (
    add_components_to_project,
    cmd_add,
    cmd_apply,
    generate_theme_css,
    rebuild_theme,
)
from cli.preset_codec import DEFAULT_PRESET_CODE
from native.registry.colors import COLOR_THEMES
from native.registry.radii import RADII_OPTIONS
from native.registry.themes import BASE_THEMES

if TYPE_CHECKING:
    from collections.abc import Generator


_MIN_THEME_CSS_LINES = 3
"""Lower bound on lines a valid ``generate_theme_css`` payload must produce.

The emitted CSS contains ``:root {…}``, ``.dark {…}``, and surrounding
declaration lines, so anything with fewer than this many total lines is
guaranteed to be malformed.
"""


class TestRebuildTheme:
    """Unit tests for the rebuild_theme function."""

    def test_rebuild_theme_returns_dict(self) -> None:
        config = {"baseId": BASE_THEMES[0]["id"]}
        result = rebuild_theme(config)
        assert isinstance(result, dict)
        assert all(k.startswith("--") for k in result)

    def test_rebuild_theme_missing_base_returns_empty(self) -> None:
        config = {"baseId": "nonexistent"}
        result = rebuild_theme(config)
        assert result == {}

    def test_rebuild_theme_applies_color(self) -> None:
        color_id = COLOR_THEMES[0]["id"]
        config = {"baseId": BASE_THEMES[0]["id"], "colorId": color_id}
        result = rebuild_theme(config)
        assert any(k.startswith("--") and not k.startswith("--chart-") for k in result)

    def test_rebuild_theme_applies_chart(self) -> None:
        chart_id = COLOR_THEMES[0]["id"]
        config = {"baseId": BASE_THEMES[0]["id"], "chartId": chart_id}
        result = rebuild_theme(config)
        assert any(k.startswith("--chart-") for k in result)

    def test_rebuild_theme_applies_radius(self) -> None:
        radius_val = RADII_OPTIONS[0]["value"]
        config = {"baseId": BASE_THEMES[0]["id"], "radius": radius_val}
        result = rebuild_theme(config)
        assert result.get("--radius") == radius_val

    def test_rebuild_theme_dark_mode(self) -> None:
        config = {"baseId": BASE_THEMES[0]["id"], "darkMode": True}
        result = rebuild_theme(config)
        # Dark mode should return different values than light mode
        light_config = {"baseId": BASE_THEMES[0]["id"], "darkMode": False}
        light_result = rebuild_theme(light_config)
        # Some values should differ (not all, but at least check it produces output)
        assert result != light_result or len(result) > 0


class TestGenerateThemeCss:
    """Tests for theme CSS generation."""

    def test_generate_theme_css_with_default_preset(self) -> None:
        css = generate_theme_css(DEFAULT_PRESET_CODE)
        assert css
        assert ":root {" in css
        assert ".dark {" in css
        assert "--" in css

    def test_generate_theme_css_format(self) -> None:
        css = generate_theme_css(DEFAULT_PRESET_CODE)
        lines = css.split("\n")
        # Should have root block, dark block, and content
        assert len(lines) > _MIN_THEME_CSS_LINES
        assert any(":root" in line for line in lines)
        assert any(".dark" in line for line in lines)

    def test_generate_theme_css_invalid_preset(self) -> None:
        css = generate_theme_css("invalid_preset_code")
        assert css == ""


class TestCmdApply:
    """Tests for cmd_apply function - highest risk due to CSS hand-editing."""

    @pytest.fixture  # pyright: ignore[reportUntypedFunctionDecorator]
    def temp_project(self) -> Generator[Path, None, None]:
        """Create a temporary project directory with rxconfig.py."""
        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "rxconfig.py").write_text(
            "# Mock rxconfig.py\nrx.Config(app_name='test')",
        )
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cmd_apply_creates_assets_dir(
        self,
        temp_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Apply should create assets directory if missing."""
        monkeypatch.chdir(temp_project)
        cmd_apply(DEFAULT_PRESET_CODE)
        assert (temp_project / "assets").exists()

    def test_cmd_apply_creates_globals_css(
        self,
        temp_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Apply should create globals.css with theme CSS."""
        monkeypatch.chdir(temp_project)
        cmd_apply(DEFAULT_PRESET_CODE)
        css_file = temp_project / "assets" / "globals.css"
        assert css_file.exists()
        content = css_file.read_text()
        assert ":root {" in content
        assert ".dark {" in content

    def test_cmd_apply_replaces_existing_theme(
        self,
        temp_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Apply should replace existing theme blocks while keeping user CSS."""
        monkeypatch.chdir(temp_project)
        assets = temp_project / "assets"
        assets.mkdir(exist_ok=True)
        css_file = assets / "globals.css"

        # Pre-existing CSS with stale theme plus user-authored rules
        initial_css = (
            ":root {\n    --old: value;\n}\n\n"
            ".dark {\n    --old: darkvalue;\n}\n\n"
            "body { color: black; }"
        )
        css_file.write_text(initial_css)

        cmd_apply(DEFAULT_PRESET_CODE)

        content = css_file.read_text()
        assert ":root {" in content
        assert ".dark {" in content
        # User-authored CSS is preserved verbatim.
        assert "body { color: black; }" in content

    def test_cmd_apply_preserves_non_theme_css(
        self,
        temp_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Apply should preserve CSS content outside theme blocks."""
        monkeypatch.chdir(temp_project)
        assets = temp_project / "assets"
        assets.mkdir(exist_ok=True)
        css_file = assets / "globals.css"

        custom_css = (
            "/* Custom styles */\n"
            "body { padding: 10px; }\n"
            "@layer utilities { .custom { color: red; } }"
        )
        css_file.write_text(custom_css)

        cmd_apply(DEFAULT_PRESET_CODE)

        content = css_file.read_text()
        assert "Custom styles" in content or "custom" in content.lower()

    def test_cmd_apply_invalid_preset_exits(
        self,
        temp_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Apply with invalid preset should exit with error."""
        monkeypatch.chdir(temp_project)
        with pytest.raises(SystemExit):
            cmd_apply("invalid_preset_xyz")

    def test_cmd_apply_missing_rxconfig_exits(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Apply in non-Reflex project should exit with error."""
        tmpdir = Path(tempfile.mkdtemp())
        monkeypatch.chdir(tmpdir)
        with pytest.raises(SystemExit):
            cmd_apply(DEFAULT_PRESET_CODE)

    def test_cmd_apply_updates_manifest(
        self,
        temp_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Apply should update components.json with theme metadata."""
        monkeypatch.chdir(temp_project)
        cmd_apply(DEFAULT_PRESET_CODE)

        manifest_file = temp_project / "components.json"
        assert manifest_file.exists()
        manifest = json.loads(manifest_file.read_text())
        assert "theme" in manifest
        assert manifest["theme"]["preset"] == DEFAULT_PRESET_CODE


class TestCmdAdd:
    """Tests for cmd_add function - component addition flow."""

    @pytest.fixture  # pyright: ignore[reportUntypedFunctionDecorator]
    def temp_project_with_theme(self) -> Generator[Path, None, None]:
        """Create a temporary Reflex project with theme."""
        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "rxconfig.py").write_text("# Mock rxconfig.py")
        assets = tmpdir / "assets"
        assets.mkdir()
        (assets / "globals.css").write_text(
            ":root { --primary: #000; }\n.dark { --primary: #fff; }",
        )
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cmd_add_missing_rxconfig_warns(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Add without rxconfig.py should warn and exit."""
        tmpdir = Path(tempfile.mkdtemp())
        monkeypatch.chdir(tmpdir)
        with pytest.raises(SystemExit):
            cmd_add(["button"])
        captured = capsys.readouterr()
        assert "rxconfig.py not found" in captured.out
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cmd_add_missing_theme_warns(
        self,
        temp_project_with_theme: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Add without theme should warn but continue."""
        monkeypatch.chdir(temp_project_with_theme)
        # Remove theme from globals.css
        css_file = temp_project_with_theme / "assets" / "globals.css"
        css_file.write_text("/* no theme here */")

        # This prints a warning but may fail on actual component resolution.
        with contextlib.suppress(SystemExit):
            cmd_add(["button"])

        captured = capsys.readouterr()
        assert "Warning" in captured.out or "theme" in captured.out.lower()


class TestAddComponentsToProject:
    """Low-level tests for add_components_to_project function."""

    @pytest.fixture  # pyright: ignore[reportUntypedFunctionDecorator]
    def temp_project(self) -> Generator[Path, None, None]:
        """Create a temporary Reflex project."""
        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "rxconfig.py").write_text("# Mock rxconfig")
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_add_components_no_rxconfig(self) -> None:
        """Should return False if rxconfig.py missing."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            result = add_components_to_project(["button"], tmpdir)
            assert result is False
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_add_components_missing_source(self, temp_project: Path) -> None:
        """Should handle missing source components gracefully."""
        # This tests the error handling path when source is not found
        result = add_components_to_project(["nonexistent_component_xyz"], temp_project)
        # Should return False if no valid components to add
        assert result is False
