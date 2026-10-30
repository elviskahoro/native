"""Regression test for the cross-file invariant the Geist font-family bug
violated: every ``FONT_REGISTRY`` ``--font-family`` name must be a family
``GOOGLE_FONTS_URL`` actually loads, else the browser silently falls back to
the next entry in the stack.

Bug: the ``geist`` entry declared ``--font-family: '"Geist Sans", sans-serif'``
(the Vercel npm package's system name), but the only loader
(``native/hooks/stylesheets.py``'s ``GOOGLE_FONTS_URL``) requests
``family=Geist`` (the name Google Fonts serves). No ``@font-face`` matched, so
the default heading AND body on ``/typeset`` (``geist`` is the heading/body
default) silently fell back to generic ``sans-serif`` for every user without
a local Geist install. All 13 other registry entries matched their loaded
families character-for-character; ``geist`` was the lone mismatch.

The fix quotes ``"Geist"`` in the registry entry; the label
``"Geist Sans (Sans)"`` (the product name users see in the selects) is
preserved. The value flows verbatim through ``/typeset``,
``/create``, the CLI (``_apply_font_theme``), and the typeset builder's
exported Google Fonts snippet, so this single change fixes all of them.

This guard is parametrized over the whole registry so any future entry that
reintroduces the mismatch is caught by id, not by position.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from native.hooks.stylesheets import GOOGLE_FONTS_URL
from native.registry.fonts import FONT_REGISTRY
from native.registry.typeset_options import (
    DEFAULT_BODY_FONT_ID,
    DEFAULT_HEADING_FONT_ID,
)


def _quoted_font_family(entry: dict[str, Any]) -> str:
    """First quoted token of an entry's ``--font-family``.

    The registry's ``--font-family`` is always written as
    ``'"Family", fallback-stack'``, so the first quoted token is the CSS
    family name that must match a loaded ``@font-face``.
    """
    ff = entry["vars"]["--font-family"]
    assert isinstance(ff, str), (
        f"geist entry --font-family must be a str, got {type(ff)!r}"
    )
    m = re.match(r'^"([^"]+)"', ff)
    assert m, (
        f"FONT_REGISTRY entry {entry.get('id')!r} --font-family {ff!r} must "
        f"start with a quoted family name"
    )
    return m.group(1)


def _google_fonts_families(url: str) -> set[str]:
    """Family names (spaces restored) actually loaded by a Google Fonts
    ``css2`` URL. ``family=Plus+Jakarta+Sans:wght@...`` -> ``"Plus Jakarta
    Sans"``. Stops each family at ``:`` (the weight spec) or ``&``."""
    families: set[str] = set()
    for m in re.finditer(r"family=([^:&]+)", url):
        families.add(m.group(1).replace("+", " "))
    return families


_GF_FAMILIES = _google_fonts_families(GOOGLE_FONTS_URL)


class TestRegistryFontsLoadedByGoogleFonts:
    """Every selectable font's CSS family name must be loaded by
    ``GOOGLE_FONTS_URL``, else the browser silently falls back to the next
    family in the stack. Parametrized over the whole registry so any future
    entry that reintroduces a mismatch is caught by id, not by position."""

    @pytest.mark.parametrize(  # pyright: ignore[reportUntypedFunctionDecorator]
        "entry",
        FONT_REGISTRY,
        ids=[str(f["id"]) for f in FONT_REGISTRY],
    )
    def test_each_registry_family_is_loaded_by_google_fonts(
        self,
        entry: dict[str, Any],
    ) -> None:
        fam = _quoted_font_family(entry)
        assert fam in _GF_FAMILIES, (
            f"FONT_REGISTRY entry {entry.get('id')!r} declares CSS family "
            f"{fam!r} but GOOGLE_FONTS_URL never requests it; the browser "
            f"would have no matching @font-face and silently fall back to the "
            f"next family in the stack."
        )

    def test_default_heading_and_body_font_family_is_loaded(self) -> None:
        # 'geist' is the heading AND body default, so the default /typeset
        # route silently fell back to sans-serif when its family name matched
        # no loaded face.
        assert DEFAULT_HEADING_FONT_ID == "geist"
        assert DEFAULT_BODY_FONT_ID == "geist"
        entry = next(f for f in FONT_REGISTRY if f["id"] == "geist")
        assert _quoted_font_family(entry) in _GF_FAMILIES, (
            "The default heading/body font's CSS family name must match a "
            "@font-face the app actually loads, else /typeset's default "
            "typography silently falls back to a system font."
        )
