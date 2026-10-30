"""Tests for the USAGE branch of `native.engine.parser.render_token`.

Regression coverage for a bug where `render_token` forwarded the raw,
un-normalized token argument to `usage()` instead of the cleaned name
from `_clean_arg`. This made `_usage_demo` do a case-sensitive
`ANATOMY.get()` on the un-normalized string and, on a miss, pass `None`
straight into `rx.el.code()`, which Reflex serializes as the literal
text `null` in the rendered Anatomy tab. The same raw argument was
interpolated into the import line, producing invalid Python like
`from components.ui.'Button' import 'Button'`, and a mangled header.

The component tree is walked directly (following `.children`) rather
than regexing the fragile `repr`, so assertions read the literal text
Reflex renders into each `<code>` block. A `None` child -- the bug --
shows up as a `LiteralNoneVar` (`_js_expr == "null"`), which
`_code_text` surfaces as `None`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import reflex as rx

from native.engine.parser import parse_and_render, render_token
from native.templates.anatomy import ANATOMY

if TYPE_CHECKING:
    from collections.abc import Iterator

# A valid usage import line: `from components.ui.<id> import <id>`.
_IMPORT_RE = re.compile(r"^from components\.ui\.([A-Za-z_]\w*) import ([A-Za-z_]\w*)$")

# A usage block renders at least an import line and an anatomy example.
_MIN_USAGE_CODE_BLOCKS = 2


# ---------------------------------------------------------------------------
# Tree-walk helpers (robust to Reflex Var escaping; no repr regexing).
# ---------------------------------------------------------------------------


def _walk(comp: object) -> Iterator[object]:
    yield comp
    for child in getattr(comp, "children", None) or ():
        yield from _walk(child)


def _code_text(code_comp: object) -> str | None:
    """Literal text of an `rx.el.code` block.

    `None` means Reflex would render this block as the literal text
    `null` -- the silent `None`-into-`rx.el.code` bug -- rather than an
    empty block (which returns `""`).
    """
    kids = getattr(code_comp, "children", None) or ()
    if not kids:
        return ""
    first = kids[0]
    if first is None:
        return None
    if isinstance(first, str):
        return first
    contents = getattr(first, "contents", None)
    if isinstance(contents, str):
        return contents
    if getattr(contents, "_js_expr", None) == "null":  # LiteralNoneVar
        return None
    raw = getattr(contents, "_var_value", None)
    return raw if isinstance(raw, str) else ""


def _code_blocks(root: object) -> list[str | None]:
    return [  # type: ignore[misc]
        _code_text(c) for c in _walk(root) if getattr(c, "tag", None) == "code"
    ]


def _usage_codes(arg: str) -> list[str | None]:
    """Code blocks of the usage block for `arg`: `[import, anatomy]`."""
    blocks = _code_blocks(render_token("usage", arg))
    assert len(blocks) >= _MIN_USAGE_CODE_BLOCKS, (
        f"usage({arg!r}) rendered {len(blocks)} code blocks, need >={_MIN_USAGE_CODE_BLOCKS}"
    )
    return blocks


def _import_text(arg: str) -> str:
    import_text = _usage_codes(arg)[0]
    assert import_text is not None, f"import line missing for {arg!r}"
    return import_text


def _anatomy_text(arg: str) -> str | None:
    return _usage_codes(arg)[1]


def _el_text(el: object) -> str:
    """Flatten an element's immediate children into a single string."""
    kids = getattr(el, "children", None) or ()
    parts: list[str] = []
    for k in kids:
        if isinstance(k, str):
            parts.append(k)
            continue
        contents = getattr(k, "contents", None)
        if isinstance(contents, str):
            parts.append(contents)
            continue
        raw = getattr(contents, "_var_value", None) if contents is not None else None
        if isinstance(raw, str):
            parts.append(raw)
    return "".join(parts)


# ---------------------------------------------------------------------------
# Normalization: every grammar form _clean_arg accepts must resolve to a
# correct anatomy lookup (the core of the bug).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(  # pyright: ignore[reportUntypedFunctionDecorator]
    "arg",
    ["'Button'", "Button", " button ", "['Button']"],
)
def test_usage_normalizes_token_arg_variants(arg: str) -> None:
    """A `--USAGE(arg)--` token in any form accepted by `_clean_arg`
    (quoted, mixed-case, whitespace-padded, bracketed) must render the
    same Anatomy snippet as the bare lowercase form, never the literal
    text `null`.
    """
    anatomy = _anatomy_text(arg)
    assert anatomy is not None, f"anatomy for {arg!r} rendered as 'null'"
    assert anatomy == ANATOMY["button"], f"anatomy for {arg!r} did not match 'button()'"


# ---------------------------------------------------------------------------
# Missing ANATOMY entry: the placeholder must render loudly, not as null.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(  # pyright: ignore[reportUntypedFunctionDecorator]
    "name",
    ["core", "hugeicon", "line_chart_01"],
)
def test_usage_missing_anatomy_renders_placeholder_not_null(name: str) -> None:
    """A component name with no `ANATOMY` entry (e.g. internal helpers and
    charts) must render an explicit `# No anatomy found for <name>` comment
    in the Anatomy tab instead of the silent literal text `null`, and must
    not raise. The import line must still be a valid Python identifier.
    """
    assert isinstance(render_token("usage", name), rx.Component)

    anatomy = _anatomy_text(name)
    assert anatomy is not None, f"{name!r} anatomy rendered as 'null'"
    assert anatomy == f"# No anatomy found for {name}"

    module, ident = _IMPORT_RE.match(_import_text(name)).groups()  # type: ignore[union-attr]
    assert module == ident == name


# ---------------------------------------------------------------------------
# Import line validity: must always be syntactically valid Python.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(  # pyright: ignore[reportUntypedFunctionDecorator]
    "arg",
    ["button", "'Button'", " button ", "['button_group']"],
)
def test_usage_import_line_is_valid_python(arg: str) -> None:
    """The Anatomy-tab import snippet must be `from components.ui.<id>
    import <id>` with a bare identifier, never a quoted/whitespace variant
    like `from components.ui.'Button' import 'Button'`.
    """
    text = _import_text(arg)
    match = _IMPORT_RE.match(text)
    assert match is not None, f"{arg!r} produced invalid import line: {text!r}"
    assert match.group(1) == match.group(2)


def test_usage_header_uses_cleaned_name() -> None:
    """The "Use the following to build the <Name> component." header must
    derive from the cleaned, title-cased name, so a quoted/whitespace arg
    no longer produces a mangled header.
    """
    strong = next(
        c
        for c in _walk(render_token("usage", "'button'"))
        if getattr(c, "tag", None) == "strong"
    )
    assert _el_text(strong) == "Button"


# ---------------------------------------------------------------------------
# End-to-end: every real docs page that carries a --USAGE(...)-- token
# renders through the production parser pipeline with no `null` anatomy,
# no broken import line, and each token resolves to a real ANATOMY entry
# (so live pages never ship the placeholder).
# ---------------------------------------------------------------------------

_DOCS_COMPONENTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "components"
_USAGE_TOKEN_RE = re.compile(r"--USAGE\(([^)]+)\)--", re.IGNORECASE)

_USAGE_DOCS = sorted(
    p
    for p in _DOCS_COMPONENTS_DIR.glob("*.md")
    if _USAGE_TOKEN_RE.search(p.read_text(encoding="utf-8"))
)


@pytest.mark.parametrize(  # pyright: ignore[reportUntypedFunctionDecorator]
    "md_file",
    _USAGE_DOCS,
    ids=[p.name for p in _USAGE_DOCS],
)
def test_real_usage_doc_renders_clean_anatomy_and_import(
    md_file: Path,
) -> None:
    """Rendering a real component docs page through `parse_and_render`
    must never serialize `None` as `null` in any code block, never emit a
    quoted import line, and every `--USAGE(arg)--` token must resolve to a
    real `ANATOMY` entry (the placeholder must never ship on a live page).
    """
    body = md_file.read_text(encoding="utf-8")

    pieces = parse_and_render(body)
    assert pieces, f"{md_file.name} rendered no components"
    assert all(isinstance(p, rx.Component) for p in pieces), (
        f"{md_file.name} produced a non-Component piece"
    )
    code_texts = [t for comp in pieces for t in _code_blocks(comp)]
    assert None not in code_texts, f"{md_file.name} rendered a 'null' code node"
    assert not any("from components.ui.'" in (t or "") for t in code_texts), (
        f"{md_file.name} rendered a quoted import line"
    )

    for arg in _USAGE_TOKEN_RE.findall(body):
        anatomy = _anatomy_text(arg)
        assert anatomy is not None, f"{md_file.name}: --USAGE({arg})-- rendered 'null'"
        assert anatomy in ANATOMY.values(), (
            f"{md_file.name}: --USAGE({arg})-- did not resolve to a real ANATOMY "
            f"entry (would ship '{anatomy}' on the public Anatomy tab)"
        )


# Guard against a silent zero-case so the parametrized test above can't
# quietly collect zero cases and look green while checking nothing.
def test_usage_docs_collection_is_not_empty() -> None:
    assert _USAGE_DOCS, f"No --USAGE(...)-- tokens found under {_DOCS_COMPONENTS_DIR}"
