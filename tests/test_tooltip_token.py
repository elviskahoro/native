r"""Tests for the TOOLTIP token branch of `native.engine.parser.render_token`.

Regression coverage for a bug where `docs/resources/chart.md` carries a
`--tooltip(\_)--` token but `render_token` had no branch for the `tooltip`
command. The token fell through to the `_LIVE_REGISTRY` lookup, which can
never contain a key like `\_` (registry keys are lowercase Python
identifiers from `native/lib` and `components/`), so the lookup missed and
the parser rendered a visible red error box
`Error: Reference Target '\_' not found` in the middle of the publicly
served Tooltip section.

Root cause: commit `2f52558` (Jul 8 2026) refactored `render_token` and
dropped the `if "tooltip" in cmd:` placeholder-span branch; commit
`a870d64` (Jul 9 2026) then added `docs/resources/chart.md` containing a
`--tooltip(...)--` token. The token and its supporting branch never
coexisted, so from birth the token rendered nothing but the error box.

Fix: restore the `tooltip` placeholder-span branch in `render_token` so
`--tooltip(...)--` short-circuits before the registry lookup, matching the
behavior shipped in the initial commit (`2f0c3f1`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import reflex as rx

from native.engine.parser import parse_and_render, render_token

ROOT_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT_DIR / "docs"
CHART_DOC = DOCS_DIR / "resources" / "chart.md"

# The exact "Reference Target '<name>' not found" string the live parser
# emits from the registry-lookup miss path -- broader than the
# `Component \`x\` not found` regex in tests/test_docs_error.py (which only
# scans the generated `assets/docs/` mirror and a *different* error
# wording, leaving this bug invisible to CI).
_NOT_FOUND_RE = re.compile(r"Reference Target '[^']*' not found", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Unit tests: render_token("tooltip", ...) returns the placeholder span
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(  # pyright: ignore[reportUntypedFunctionDecorator]
    "raw_arg",
    [
        r"\_",  # the exact token in docs/resources/chart.md: --tooltip(\_)--
        "_",  # the unescaped original form: --tooltip(_)--
        "",  # argumentless: --tooltip--
    ],
)
def test_tooltip_token_renders_placeholder_not_error(raw_arg: str) -> None:
    """The TOOLTIP branch must short-circuit to the placeholder span for
    any argument, never reaching the `_LIVE_REGISTRY` lookup miss path that
    renders the visible `Error: Reference Target '<name>' not found` box.

    `_clean_arg` lowercases and strips quotes/brackets but does not strip
    backslashes, so the live `--tooltip(\\_)--` token reaches this branch as
    the name `\\_`; the branch must not depend on the argument resolving to
    any registry key.
    """
    result = render_token("tooltip", raw_arg)
    assert isinstance(result, rx.Component)

    rendered = repr(result)
    assert "Tooltip Trigger Placeholder" in rendered
    assert "not found" not in rendered.lower()
    assert "text-destructive" not in rendered, (
        "tooltip token must render the placeholder span, not the registry-miss "
        "error div styled with text-destructive"
    )


def test_tooltip_token_short_circuits_before_registry_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The TOOLTIP branch must not depend on `_LIVE_REGISTRY` at all: even if
    the registry is emptied (or the name happens to collide with a real
    component), the placeholder span is returned, not a demo or an error.
    """
    import native.engine.parser as parser_mod

    monkeypatch.setattr(parser_mod, "_LIVE_REGISTRY", {})

    result = render_token("tooltip", "button")
    assert isinstance(result, rx.Component)
    assert "Tooltip Trigger Placeholder" in repr(result)
    assert "not found" not in repr(result).lower()


# ---------------------------------------------------------------------------
# Integration: the real docs/resources/chart.md renders without the error box
# ---------------------------------------------------------------------------


def test_chart_doc_renders_tooltip_placeholder_without_error() -> None:
    """End-to-end: rendering the real `docs/resources/chart.md` (the doc that
    exposed the bug) through the production parser pipeline produces the
    tooltip placeholder span and never produces the `Reference Target ... not
    found` error box anywhere in the rendered component tree.
    """
    assert CHART_DOC.exists(), f"fixture missing: {CHART_DOC}"

    pieces = parse_and_render(CHART_DOC.read_text(encoding="utf-8"))
    assert pieces, "chart.md should render at least one component"
    assert all(isinstance(p, rx.Component) for p in pieces)

    joined = "".join(repr(p) for p in pieces)
    assert "Tooltip Trigger Placeholder" in joined, (
        "chart.md should render the tooltip placeholder span in its Tooltip section"
    )
    assert not _NOT_FOUND_RE.search(joined), (
        f"chart.md renders a visible error box: {_NOT_FOUND_RE.findall(joined)}"
    )


# ---------------------------------------------------------------------------
# End-to-end guard: no served doc page renders a "not found" error box.
#
# Closes the CI gap that let this bug ship: tests/test_docs_error.py only
# regex-scans the generated `assets/docs/` mirror (not the served `docs/`
# source), and when this bug shipped it only knew the `Component \`x\` not
# found` wording; the live parser emits a differently-worded `Reference
# Target '<name>' not found` string, so a mirror scan cannot catch a
# live-parser regression.
# ---------------------------------------------------------------------------


def _strip_frontmatter(text: str) -> str:
    return re.sub(r"^---.*?---\n", "", text, count=1, flags=re.DOTALL)


def _doc_files() -> list[Path]:
    return sorted(DOCS_DIR.rglob("*.md"))


def _md_file_id(md_file: Path) -> str:
    return str(md_file.relative_to(DOCS_DIR))


def test_doc_dir_is_not_empty() -> None:
    """Sanity check so the parametrized scan below cannot silently collect
    zero cases (mirrors the guard pattern in tests/test_docs_error.py and
    tests/test_toc_links.py).
    """
    assert _doc_files(), f"No markdown files found under {DOCS_DIR}"


@pytest.mark.parametrize(  # pyright: ignore[reportUntypedFunctionDecorator]
    "md_file",
    _doc_files(),
    ids=_md_file_id,
)
def test_no_doc_page_renders_reference_not_found_error(md_file: Path) -> None:
    """Every served doc page, run through the production `parse_and_render`
    pipeline, must produce no rendered component containing the
    `Reference Target '<name>' not found` error placeholder.

    This is the exact symptom that surfaced on the publicly served
    `/docs/resources/chart` page before the fix.
    """
    body = _strip_frontmatter(md_file.read_text(encoding="utf-8"))
    pieces = parse_and_render(body)
    joined = "".join(repr(p) for p in pieces)

    matches = _NOT_FOUND_RE.findall(joined)
    assert not matches, (
        f"{md_file.relative_to(ROOT_DIR)} renders a visible 'Reference Target "
        f"... not found' error box at a token that missed the registry lookup: "
        f"{matches}"
    )


def test_markdown_mirror_renders_tooltip_placeholder() -> None:
    """The offline mirror generator must agree with the live parser.

    ``scripts/generate_markdown.py`` has its own token table; without a
    ``tooltip`` case it shipped ``> Unknown token `tooltip` `` in
    ``assets/docs/resources/chart.md``.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "generate_markdown",
        ROOT_DIR / "scripts" / "generate_markdown.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    out = module.convert_to_markdown("--tooltip(\\_)--")
    assert "Unknown token" not in out
    assert "Tooltip Trigger Placeholder" in out

    mirror = (ROOT_DIR / "assets" / "docs" / "resources" / "chart.md").read_text(
        encoding="utf-8",
    )
    assert "Unknown token" not in mirror
