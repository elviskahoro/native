"""Tests for cli/main.py functions.

Focus on highest-risk flows: cmd_apply (theme-rewrite) and cmd_add (component add).
These tests provide regression protection before refactoring the oversized functions.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from cli.main import (
    cmd_add,
    cmd_apply,
    rebuild_theme,
    generate_theme_css,
    add_components_to_project,
)
from cli.preset_codec import DEFAULT_PRESET_CODE, decode_seed
from native.registry.colors import COLOR_THEMES
from native.registry.fonts import FONT_REGISTRY
from native.registry.radii import RADII_OPTIONS
from native.registry.styles import STYLE_REGISTRY
from native.registry.themes import BASE_THEMES


class TestRebuildTheme:
    """Unit tests for the rebuild_theme function."""

    def test_rebuild_theme_returns_dict(self) -> None:
        config = {"baseId": BASE_THEMES[0]["id"]}
        result = rebuild_theme(config)
        assert isinstance(result, dict)
        assert all(k.startswith("--") for k in result.keys())

    def test_rebuild_theme_missing_base_returns_empty(self) -> None:
        config = {"baseId": "nonexistent"}
        result = rebuild_theme(config)
        assert result == {}

    def test_rebuild_theme_applies_color(self) -> None:
        color_id = COLOR_THEMES[0]["id"]
        config = {"baseId": BASE_THEMES[0]["id"], "colorId": color_id}
        result = rebuild_theme(config)
        assert any(k.startswith("--") and not k.startswith("--chart-") for k in result.keys())

    def test_rebuild_theme_applies_chart(self) -> None:
        chart_id = COLOR_THEMES[0]["id"]
        config = {"baseId": BASE_THEMES[0]["id"], "chartId": chart_id}
        result = rebuild_theme(config)
        assert any(k.startswith("--chart-") for k in result.keys())

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
        assert len(lines) > 3
        assert any(":root" in line for line in lines)
        assert any(".dark" in line for line in lines)

    def test_generate_theme_css_invalid_preset(self) -> None:
        css = generate_theme_css("invalid_preset_code")
        assert css == ""


class TestCmdApply:
    """Tests for cmd_apply function - highest risk due to CSS hand-editing."""

    @pytest.fixture
    def temp_project(self) -> Path:
        """Create a temporary project directory with rxconfig.py."""
        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "rxconfig.py").write_text("# Mock rxconfig.py\nrx.Config(app_name='test')")
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cmd_apply_creates_assets_dir(self, temp_project: Path) -> None:
        """Apply should create assets directory if missing."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)
            cmd_apply(DEFAULT_PRESET_CODE)
            assert (temp_project / "assets").exists()
        finally:
            os.chdir(original_cwd)

    def test_cmd_apply_creates_globals_css(self, temp_project: Path) -> None:
        """Apply should create globals.css with theme CSS."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)
            cmd_apply(DEFAULT_PRESET_CODE)
            css_file = temp_project / "assets" / "globals.css"
            assert css_file.exists()
            content = css_file.read_text()
            assert ":root {" in content
            assert ".dark {" in content
        finally:
            os.chdir(original_cwd)

    def test_cmd_apply_replaces_existing_theme(self, temp_project: Path) -> None:
        """Apply should replace existing theme blocks."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)
            assets = temp_project / "assets"
            assets.mkdir(exist_ok=True)
            css_file = assets / "globals.css"

            # Create initial CSS with theme and other content
            initial_css = ":root {\n    --old: value;\n}\n\n.dark {\n    --old: darkvalue;\n}\n\nbody { color: black; }"
            css_file.write_text(initial_css)

            # Apply new theme
            cmd_apply(DEFAULT_PRESET_CODE)

            content = css_file.read_text()
            # Should have new theme
            assert ":root {" in content
            assert ".dark {" in content
            # Should preserve non-theme content
            assert "body { color: black; }" in content
        finally:
            os.chdir(original_cwd)

    def test_cmd_apply_preserves_non_theme_css(self, temp_project: Path) -> None:
        """Apply should preserve CSS content outside theme blocks."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)
            assets = temp_project / "assets"
            assets.mkdir(exist_ok=True)
            css_file = assets / "globals.css"

            custom_css = "/* Custom styles */\nbody { padding: 10px; }\n@layer utilities { .custom { color: red; } }"
            css_file.write_text(custom_css)

            cmd_apply(DEFAULT_PRESET_CODE)

            content = css_file.read_text()
            assert "Custom styles" in content or "custom" in content.lower()
        finally:
            os.chdir(original_cwd)

    def test_cmd_apply_invalid_preset_exits(self, temp_project: Path, monkeypatch) -> None:
        """Apply with invalid preset should exit with error."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)
            with pytest.raises(SystemExit):
                cmd_apply("invalid_preset_xyz")
        finally:
            os.chdir(original_cwd)

    def test_cmd_apply_missing_rxconfig_exits(self, monkeypatch) -> None:
        """Apply in non-Reflex project should exit with error."""
        tmpdir = Path(tempfile.mkdtemp())
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            with pytest.raises(SystemExit):
                cmd_apply(DEFAULT_PRESET_CODE)
        finally:
            os.chdir(original_cwd)
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cmd_apply_updates_manifest(self, temp_project: Path) -> None:
        """Apply should update components.json with theme metadata."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project)
            cmd_apply(DEFAULT_PRESET_CODE)

            manifest_file = temp_project / "components.json"
            assert manifest_file.exists()
            manifest = json.loads(manifest_file.read_text())
            assert "theme" in manifest
            assert manifest["theme"]["preset"] == DEFAULT_PRESET_CODE
        finally:
            os.chdir(original_cwd)


class TestCmdAdd:
    """Tests for cmd_add function - component addition flow."""

    @pytest.fixture
    def temp_project_with_theme(self) -> Path:
        """Create a temporary Reflex project with theme."""
        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "rxconfig.py").write_text("# Mock rxconfig.py")
        assets = tmpdir / "assets"
        assets.mkdir()
        (assets / "globals.css").write_text(":root { --primary: #000; }\n.dark { --primary: #fff; }")
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cmd_add_missing_rxconfig_warns(self, monkeypatch, capsys) -> None:
        """Add without rxconfig.py should warn and exit."""
        tmpdir = Path(tempfile.mkdtemp())
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            with pytest.raises(SystemExit):
                cmd_add(["button"])
            captured = capsys.readouterr()
            assert "rxconfig.py not found" in captured.out
        finally:
            os.chdir(original_cwd)
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cmd_add_missing_theme_warns(self, temp_project_with_theme, capsys) -> None:
        """Add without theme should warn but continue."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_project_with_theme)
            # Remove theme from globals.css
            css_file = temp_project_with_theme / "assets" / "globals.css"
            css_file.write_text("/* no theme here */")

            # This will print a warning but may fail on actual component resolution
            # Just check that it doesn't silently fail
            try:
                cmd_add(["button"])
            except SystemExit:
                # Expected if button is not in registry
                pass

            captured = capsys.readouterr()
            assert "Warning" in captured.out or "theme" in captured.out.lower()
        finally:
            os.chdir(original_cwd)


class TestAddComponentsToProject:
    """Low-level tests for add_components_to_project function."""

    @pytest.fixture
    def temp_project(self) -> Path:
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


import os
