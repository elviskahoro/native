"""Regression tests for the docs "On This Page" sidebar TOC links.

Background: sidebar hrefs were built with a hand-rolled slug transform
(`entry['id'].lower().replace(' ', '-')`) that diverged from the slugify
python-markdown applies to rendered <h1>/<h2> ids. Any heading containing
punctuation (dots, apostrophes, ampersands, colons, slashes, commas,
em-dashes, parentheses) produced a dead-click href that resolved to no
element (e.g. `#accordion.root` vs the rendered `id="accordionroot"`).

The fix makes python-markdown the single source of truth: toc ids come from
`native.engine.parser.extract_toc_data` (a whole-body `markdown.markdown`
pass), and `native.templates.toc._create_markdown_toc_links` uses them
verbatim. These tests guard against re-introducing the divergence.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest

from native.engine.parser import extract_toc_data, parse_and_render

ROOT_DIR = Path(__file__).parent.parent
DOCS_DIR = ROOT_DIR / "docs"
ACCORDION_DOC = DOCS_DIR / "components" / "accordion.md"

_HEADING_RE = re.compile(r'<h([12])\s+id="([^"]+)"[^>]*>(.*?)</h\1>', re.DOTALL)


def _strip_frontmatter(text: str) -> str:
    return re.sub(r"^---.*?---\n", "", text, count=1, flags=re.DOTALL)


def _doc_files() -> list[Path]:
    return sorted(DOCS_DIR.rglob("*.md"))


def _served_headings(md_path: Path) -> list[dict]:
    """Heading ids the browser actually receives: run the production chunked
    parse_and_render pipeline and read <h1>/<h2 id="..."> from each
    dangerouslySetInnerHTML payload (verbatim, matching the served DOM)."""
    body = _strip_frontmatter(md_path.read_text(encoding="utf-8"))
    out: list[dict] = []
    for piece in parse_and_render(body):
        if type(piece).__name__ != "Html":
            continue
        payload = getattr(piece.dangerouslySetInnerHTML, "_var_value", None)
        if not payload or "__html" not in payload:
            continue
        for m in _HEADING_RE.finditer(payload["__html"]):
            text = html.unescape(re.sub(r"<[^>]+>", "", m.group(3))).strip()
            out.append({"id": m.group(2), "text": text})
    return out


def _is_expected_noop(entry_id: str, served: list[dict]) -> bool:
    """An out-of-scope cross-chunk duplicate-id no-op: the entry id is a
    dedup-suffixed variant (`<base>_<N>`) whose base id appears more than once
    in the served DOM. Such suffixed ids are absent from the served DOM
    because parse_and_render renders per-chunk (no cross-chunk dedup); fixing
    that is a separate parser.py-side defect, tracked as out of scope."""
    m = re.match(r"^(.*)_(\d+)$", entry_id)
    if not m:
        return False
    base = m.group(1)
    return sum(1 for s in served if s["id"] == base) > 1


# ---------------------------------------------------------------------------
# Unit tests: extract_toc_data produces python-markdown's real heading ids
# ---------------------------------------------------------------------------

_TOC_CASES = [
    pytest.param(
        "## accordion.root",
        [(2, "accordionroot", "accordion.root")],
        id="dotted-namespace-heading",
    ),
    pytest.param(
        "# What's Included",
        [(1, "whats-included", "What's Included")],
        id="apostrophe-heading",
    ),
    pytest.param(
        "# Optional: handling table overflow",
        [(1, "optional-handling-table-overflow", "Optional: handling table overflow")],
        id="colon-heading",
    ),
    pytest.param(
        "# Use buridan/create",
        [(1, "use-buridancreate", "Use buridan/create")],
        id="slash-heading",
    ),
    pytest.param(
        "# Async Handlers & Yielding",
        [(1, "async-handlers-yielding", "Async Handlers & Yielding")],
        id="ampersand-heading-entity-unescape",
    ),
    pytest.param(
        "# No Overflow, No Fade",
        [(1, "no-overflow-no-fade", "No Overflow, No Fade")],
        id="comma-heading",
    ),
    pytest.param(
        "# foo \u2014 bar (em dash)",
        [(1, "foo-bar-em-dash", "foo \u2014 bar (em dash)")],
        id="em-dash-paren-heading",
    ),
    pytest.param(
        "## Row selection (opt-in convention)",
        [(2, "row-selection-opt-in-convention", "Row selection (opt-in convention)")],
        id="parenthesized-heading",
    ),
    pytest.param(
        "# Examples\n\n## Basic",
        [(1, "examples", "Examples"), (2, "basic", "Basic")],
        id="plain-headings-still-work",
    ),
]


@pytest.mark.parametrize("body, expected", _TOC_CASES)
def test_extract_toc_data_ids_match_python_markdown_slugify(body, expected):
    toc = extract_toc_data(body)
    assert [(e["level"], e["id"], e["text"]) for e in toc] == expected


def test_extract_toc_data_unescapes_html_entities_in_text():
    toc = extract_toc_data("# A & B > C")
    assert toc[0]["text"] == "A & B > C"
    assert toc[0]["id"] == "a-b-c"


def test_extract_toc_data_strips_inline_formatting_from_text():
    toc = extract_toc_data("## Use `code` here")
    assert toc[0]["text"] == "Use code here"
    assert toc[0]["id"] == "use-code-here"


def test_extract_toc_data_skips_fenced_code_phantom_headings():
    body = (
        "# Real Heading\n\n"
        "```python\n"
        "# this looks like a heading but is a code comment\n"
        "x = 1\n"
        "```\n\n"
        "## Also Real\n"
    )
    toc = extract_toc_data(body)
    assert [e["text"] for e in toc] == ["Real Heading", "Also Real"]
    assert [e["id"] for e in toc] == ["real-heading", "also-real"]


def test_extract_toc_data_dedups_duplicate_headings_within_document():
    body = "## Dev\n\nfirst\n\n## Dev\n\nsecond\n"
    toc = extract_toc_data(body)
    assert [e["id"] for e in toc] == ["dev", "dev_1"]
    assert [e["text"] for e in toc] == ["Dev", "Dev"]


def test_extract_toc_data_preserves_heading_order_and_levels():
    body = "# One\n\n## Two\n\n# Three\n\n## Four\n"
    toc = extract_toc_data(body)
    assert [(e["level"], e["id"]) for e in toc] == [
        (1, "one"),
        (2, "two"),
        (1, "three"),
        (2, "four"),
    ]


def test_extract_toc_data_returns_empty_for_no_headings():
    assert extract_toc_data("Just a paragraph.\n\nNo headings here.") == []


# ---------------------------------------------------------------------------
# End-to-end: every sidebar href resolves to a real rendered heading id,
# for every docs page, with no misdirects and no unexpected no-ops.
# ---------------------------------------------------------------------------


def test_doc_dir_is_not_empty():
    assert _doc_files(), f"No markdown files found under {DOCS_DIR}"


@pytest.mark.parametrize(
    "md_file", _doc_files(), ids=lambda p: str(p.relative_to(DOCS_DIR))
)
def test_every_sidebar_href_resolves_in_served_dom(md_file):
    served = _served_headings(md_file)
    # getElementById returns the FIRST element with a given id; setdefault
    # keeps the first occurrence's text (a plain dict comprehension would keep
    # the last and falsely report duplicate-id entries as misdirects).
    served_first_text: dict[str, str] = {}
    for s in served:
        served_first_text.setdefault(s["id"], s["text"])
    toc = extract_toc_data(_strip_frontmatter(md_file.read_text(encoding="utf-8")))

    unexpected_noops: list[tuple] = []
    misdirects: list[tuple] = []

    for entry in toc:
        eid = entry["id"]
        if eid in served_first_text:
            if served_first_text[eid] != entry["text"]:
                misdirects.append((entry["text"], eid, served_first_text[eid]))
        elif not _is_expected_noop(eid, served):
            unexpected_noops.append((entry["text"], eid))

    assert not unexpected_noops, (
        f"{md_file.relative_to(ROOT_DIR)}: sidebar href(s) that resolve to no "
        f"rendered heading and are not known cross-chunk duplicates "
        f"(slug-divergence regression): {unexpected_noops}"
    )
    assert not misdirects, (
        f"{md_file.relative_to(ROOT_DIR)}: sidebar href(s) scroll to a "
        f"different section (misdirect regression): {misdirects}"
    )


def test_accordion_dotted_subsections_resolve():
    """The headline symptom: dotted `## accordion.<part>` subsections under a
    component's API Reference must resolve to rendered heading ids, and the
    dot must NOT be retained in the id (the original bug)."""
    body = _strip_frontmatter(ACCORDION_DOC.read_text(encoding="utf-8"))
    toc = extract_toc_data(body)
    served_ids = {s["id"] for s in _served_headings(ACCORDION_DOC)}
    dotted = [e for e in toc if e["text"].startswith("accordion.")]
    assert dotted, "expected dotted accordion.* subsections in this fixture"
    for entry in dotted:
        assert "." not in entry["id"], (
            f"{entry['text']!r} id {entry['id']!r} retained punctuation"
        )
        assert entry["id"] in served_ids, (
            f"accordion subsection {entry['text']!r} -> #{entry['id']} does "
            f"not resolve to a rendered heading id"
        )


# ---------------------------------------------------------------------------
# toc.py: href is the rendered id verbatim, no re-slugging
# ---------------------------------------------------------------------------


def _rendered_hrefs(component) -> list[str]:
    hrefs: list[str] = []

    def walk(node):
        if type(node).__name__ == "ReactRouterLink":
            to = node.__dict__.get("to")
            value = getattr(to, "_var_value", None)
            if isinstance(value, str):
                hrefs.append(value)
        for child in getattr(node, "children", []) or []:
            walk(child)

    walk(component)
    return hrefs


def test_toc_links_use_id_verbatim_no_reslugging():
    """The href must be `f"#{entry['id']}"` with no slug transform. A synthetic
    id with mixed case, a space and a dot is preserved verbatim; the old
    `.lower().replace(' ', '-')` transform would have slugified it."""
    from native.templates.toc import _create_markdown_toc_links

    entries = [
        {"text": "accordion.item", "id": "accordionitem", "level": 2},
        {"text": "What's Included", "id": "whats-included", "level": 1},
        {"text": "Async & Yielding", "id": "async-handlers-yielding", "level": 1},
        {"text": "synthetic", "id": "Mixed CASE With Space.dot", "level": 1},
    ]
    hrefs = _rendered_hrefs(_create_markdown_toc_links("accordion", entries))
    assert hrefs == [f"#{e['id']}" for e in entries], (
        f"toc links must use entry id verbatim; got {hrefs}"
    )
    assert "#Mixed CASE With Space.dot" in hrefs


def test_toc_links_integral_with_extract_toc_data():
    """End-to-end at the template layer: the href for a real punctuated
    heading, piped through toc.py, equals #<rendered-id>."""
    from native.templates.toc import _create_markdown_toc_links

    toc = extract_toc_data("# Async Handlers & Yielding\n\n## accordion.root\n")
    hrefs = _rendered_hrefs(_create_markdown_toc_links("doc", toc))
    assert hrefs == ["#async-handlers-yielding", "#accordionroot"]
