"""Tests for the docs in-page table of contents.

``native.engine.generator.generate_docs_library`` builds each page's TOC via
``native.engine.parser.extract_toc``, which renders each markdown chunk with the
same python-markdown extensions used to render the page and collects the
resulting <h1>/<h2>. This file guards the contract that was previously broken
by a raw-text regex that captured ``#``/``##`` lines *inside fenced code blocks*
as spurious level-1/2 TOC entries (visible "On This Page" sidebar pollution), and
that the TOC ids match the rendered page's heading ids so sidebar links resolve.
"""

from __future__ import annotations

import pathlib

import markdown  # pyright: ignore[reportMissingModuleSource]
import pytest  # pyrefly: ignore[missing-import]
from bs4 import BeautifulSoup  # pyrefly: ignore[missing-import]

from native.engine.generator import generate_docs_library
from native.engine.parser import (
    _MD_EXTENSIONS,  # pyright: ignore[reportPrivateUsage]
    extract_toc,
)
from native.engine.utils import parse_frontmatter

ROOT_DIR = pathlib.Path(__file__).parent.parent
DOCS_DIR = ROOT_DIR / "docs"


def test_only_code_block_with_hashes_returns_empty() -> None:
    """The core bug: a fenced code block with '#'/'##' lines yields no TOC
    entries — fenced code is never treated as headings.
    """
    body = "```python\n# Not a heading one\n## Not a heading two\nx = 1\n```\n"
    assert extract_toc(body) == []


def test_ids_are_python_markdown_slugs() -> None:
    """TOC ids are python-markdown's toc-extension slugs (punctuation stripped),
    so the sidebar href resolves to the rendered heading's id — not the raw
    heading text that toc.py would otherwise re-slugify naively.
    """
    body = "# Basic Table\n## `table.root`\n## Row selection (opt-in convention)\n"
    toc = extract_toc(body)
    assert [e["id"] for e in toc] == [
        "basic-table",
        "tableroot",
        "row-selection-opt-in-convention",
    ]


def test_chunked_duplicate_across_token_keeps_page_id() -> None:
    """A heading duplicated across a --TOKEN-- boundary keeps the same unsuffixed id.

    The TOC matches the chunked-rendered page's id. parse_and_render renders per
    chunk, so python-markdown disambiguates duplicates only within a chunk; a
    single full-document TOC pass would wrongly suffix the second copy and
    diverge from the page. (The docs/components/field.md case.)
    """
    body = "## field.root\n\nintro\n\n--DEMO(field_demo)--\n\n## field.root\n"
    toc = extract_toc(body)
    assert [e["id"] for e in toc] == ["fieldroot", "fieldroot"]


@pytest.mark.parametrize(  # pyright: ignore[reportUntypedFunctionDecorator]
    ("slug", "spurious_substrings"),
    [
        (
            "components/table",
            ["Header — select-all checkbox", "Row — must have a unique"],
        ),
        ("getting-started/cli", ["Warning: 'button' requested"]),
        ("utilities/markdown", ["Welcome", "Page title", "Section heading"]),
    ],
)
def test_generate_docs_library_toc_has_no_spurious_entries(
    monkeypatch: pytest.MonkeyPatch,
    slug: str,
    spurious_substrings: list[str],
) -> None:
    """The app-boot entry point (called by native/export.py), in dev mode for
    each affected page, emits a table_of_content with no code-block-capture
    entries — guards the extract_toc wiring in generate_docs_library.
    """
    monkeypatch.setenv("BURIDAN_DEV_MODE", "true")
    monkeypatch.setenv("BURIDAN_DEV_PAGES", slug)

    docs = generate_docs_library()
    assert len(docs) == 1, f"expected 1 dev-mode doc for {slug}, got {len(docs)}"
    doc = docs[0]
    assert doc.url.endswith(slug), f"{slug}: unexpected url {doc.url!r}"

    texts = [e["text"] for e in doc.table_of_content]
    for needle in spurious_substrings:
        assert not any(needle in t for t in texts), (
            f"{slug}: spurious TOC entry {needle!r} present in {texts}"
        )
    assert doc.table_of_content, f"{slug}: expected legitimate TOC entries"


def _all_docs_files() -> list[pathlib.Path]:
    return sorted(DOCS_DIR.rglob("*.md"))


_DOCS = _all_docs_files()


def _full_doc_render_headings(body: str) -> list[tuple[str, int]]:
    html = markdown.markdown(body, extensions=_MD_EXTENSIONS)
    soup = BeautifulSoup(html, "html.parser")
    return [(h.get_text().strip(), int(h.name[1])) for h in soup.find_all(["h1", "h2"])]


@pytest.mark.parametrize(  # pyright: ignore[reportUntypedFunctionDecorator]
    "md_file",
    _DOCS,
    ids=[str(p.relative_to(DOCS_DIR)) for p in _DOCS],
)
def test_toc_matches_rendered_headings(md_file: pathlib.Path) -> None:
    """Every docs file's extract_toc (text, level) list equals the heading list
    of an independent full-document python-markdown render (a different code
    path than extract_toc's chunked render). Catches any code-block capture,
    missed/extra/out-of-order heading, or level mismatch across all docs.
    """
    body = parse_frontmatter(md_file.read_text(encoding="utf-8"))[1]
    expected = _full_doc_render_headings(body)
    actual = [(e["text"], e["level"]) for e in extract_toc(body)]
    assert actual == expected, (
        f"{md_file.relative_to(ROOT_DIR)}: extract_toc (text, level) list "
        f"diverges from an independent full-doc python-markdown render.\n"
        f"expected: {expected}\nactual:   {actual}"
    )


def test_docs_dir_is_non_empty_guard() -> None:
    """If _DOCS is empty the parametrized guard above silently runs 0 cases."""
    assert _DOCS, f"No markdown files found under {DOCS_DIR}"
