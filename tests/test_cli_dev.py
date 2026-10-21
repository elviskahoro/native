"""Tests for cli/dev.py resolve_pages function."""

import sys
from pathlib import Path
from typing import Any

import pytest

cli_dir = Path(__file__).parent.parent / "cli"
if str(cli_dir) not in sys.path:
    sys.path.insert(0, str(cli_dir))


@pytest.fixture
def resolve_pages_func() -> Any:  # type: ignore[misc]
    """Import and return resolve_pages function."""
    from dev import resolve_pages as rp  # pyrefly: ignore[missing-import]

    return rp


@pytest.fixture
def sample_sections() -> dict[str, list[str]]:  # type: ignore[misc]
    """Sample sections structure for testing."""
    return {
        "components": ["button", "input", "dropdown"],
        "getting-started": ["introduction", "installation"],
    }


def test_resolve_single_bare_name(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
) -> None:
    """Test resolving a single bare page name."""
    result = resolve_pages_func(["button"], [], sample_sections)
    assert result == ["components/button"]


def test_resolve_multiple_bare_names(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
) -> None:
    """Test resolving multiple bare page names."""
    result = resolve_pages_func(["button", "input"], [], sample_sections)
    assert result == ["components/button", "components/input"]


def test_resolve_single_full_path(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
) -> None:
    """Test resolving a single full path."""
    result = resolve_pages_func(["components/button"], [], sample_sections)
    assert result == ["components/button"]


def test_resolve_multiple_full_paths(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
) -> None:
    """Test resolving multiple full paths."""
    result = resolve_pages_func(
        ["components/button", "getting-started/introduction"],
        [],
        sample_sections,
    )
    assert result == ["components/button", "getting-started/introduction"]


def test_resolve_mixed_bare_and_full_paths(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
) -> None:
    """Test resolving a mix of bare names and full paths."""
    result = resolve_pages_func(
        ["button", "getting-started/introduction"],
        [],
        sample_sections,
    )
    assert result == ["components/button", "getting-started/introduction"]


def test_resolve_unknown_bare_name(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
    capsys: Any,
) -> None:
    """Test that unknown bare name returns None and prints error."""
    result = resolve_pages_func(["nonexistent"], [], sample_sections)
    assert result is None
    captured = capsys.readouterr()
    assert "Error: page not found: 'nonexistent'" in captured.out


def test_resolve_invalid_full_path(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
    capsys: Any,
) -> None:
    """Test that invalid full path returns None and prints error."""
    result = resolve_pages_func(["components/nonexistent"], [], sample_sections)
    assert result is None
    captured = capsys.readouterr()
    assert "Error: page not found: 'components/nonexistent'" in captured.out


def test_resolve_ambiguous_bare_name(
    resolve_pages_func: Any,
    capsys: Any,
) -> None:
    """Test that ambiguous bare name returns None and prints error."""
    sections: dict[str, list[str]] = {
        "section1": ["page", "other"],
        "section2": ["page", "different"],
    }
    result = resolve_pages_func(["page"], [], sections)
    assert result is None
    captured = capsys.readouterr()
    assert "Error: 'page' is ambiguous" in captured.out
    assert "section1/page" in captured.out
    assert "section2/page" in captured.out


def test_resolve_with_section_names(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
) -> None:
    """Test resolving using section names (--section flag)."""
    result = resolve_pages_func([], ["components"], sample_sections)
    assert sorted(result) == [
        "components/button",
        "components/dropdown",
        "components/input",
    ]


def test_resolve_with_multiple_section_names(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
) -> None:
    """Test resolving with multiple section names."""
    result = resolve_pages_func(
        [],
        ["components", "getting-started"],
        sample_sections,
    )
    assert sorted(result) == [
        "components/button",
        "components/dropdown",
        "components/input",
        "getting-started/installation",
        "getting-started/introduction",
    ]


def test_resolve_invalid_section_name(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
    capsys: Any,
) -> None:
    """Test that invalid section name returns None and prints error."""
    result = resolve_pages_func([], ["nonexistent"], sample_sections)
    assert result is None
    captured = capsys.readouterr()
    assert "Error: section not found: 'nonexistent'" in captured.out


def test_resolve_deduplication(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
) -> None:
    """Test that duplicate pages are deduplicated."""
    result = resolve_pages_func(["button", "button"], [], sample_sections)
    assert result == ["components/button"]


def test_resolve_names_and_sections_combined(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
) -> None:
    """Test combining both names and section names."""
    result = resolve_pages_func(["button"], ["getting-started"], sample_sections)
    assert sorted(result) == [
        "components/button",
        "getting-started/installation",
        "getting-started/introduction",
    ]


def test_resolve_deduplication_across_names_and_sections(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
) -> None:
    """Test deduplication when same page specified in names and sections."""
    result = resolve_pages_func(["button"], ["components"], sample_sections)
    assert sorted(result) == [
        "components/button",
        "components/dropdown",
        "components/input",
    ]


def test_resolve_empty_input(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
) -> None:
    """Test that empty input returns None."""
    result = resolve_pages_func([], [], sample_sections)
    assert result is None


def test_resolve_multiple_errors(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
    capsys: Any,
) -> None:
    """Test that multiple errors are all reported."""
    result = resolve_pages_func(
        ["nonexistent1", "nonexistent2", "button"],
        [],
        sample_sections,
    )
    assert result is None
    captured = capsys.readouterr()
    assert "Error: page not found: 'nonexistent1'" in captured.out
    assert "Error: page not found: 'nonexistent2'" in captured.out


def test_resolve_empty_section(
    resolve_pages_func: Any,
) -> None:
    """Test with empty section."""
    sections: dict[str, list[str]] = {"empty": [], "components": ["button"]}
    result = resolve_pages_func([], ["empty"], sections)
    assert result is None


def test_resolve_single_page_in_section(
    resolve_pages_func: Any,
) -> None:
    """Test section with single page."""
    sections: dict[str, list[str]] = {"single": ["only_page"]}
    result = resolve_pages_func([], ["single"], sections)
    assert result == ["single/only_page"]


def test_resolve_order_preservation(
    resolve_pages_func: Any,
    sample_sections: dict[str, list[str]],
) -> None:
    """Test that order is preserved."""
    result = resolve_pages_func(
        ["dropdown", "button", "input"],
        [],
        sample_sections,
    )
    assert result == [
        "components/dropdown",
        "components/button",
        "components/input",
    ]
