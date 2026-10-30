"""Regression tests for the Get Code "Copy" button click delegation.

Bug: the "Copy" button in the Get Code pane (``native/templates/_get_code.py``)
renders as ``<button id="copy-css-preset"><span id="css-theme-copy-text">Copy
</span></button>``. Its only click handler lived in a document-level delegate in
``assets/theme-preview.js`` that matched with a strict
``e.target.id === "copy-css-preset"``. Because the visible "Copy" text is a
hit-testable ``<span>``, clicking directly on the label makes ``e.target`` the
span, the strict equality fails, and the copy action (including the "Copied!"
feedback) silently never runs; only clicks landing on the button's padding
(targeting the ``<button>``) worked, so the feature looked intermittently
broken — the most natural target (the label) produced zero feedback.

The same root cause affected the ``#copy-theme-button`` "Get Code"/"Preview"
toggle (``native/pages/create.py``): its labels are wrapped in ``<span>``s while
its delegate branch used a strict ``e.target.id === "copy-theme-button"`` match,
so clicking the label text skipped the ``#get-css-theme`` population (the
Reflex ``on_click`` pane toggle still fired). The sibling
``#copy-preset-button`` already used the correct ``e.target.closest("#...")``
idiom (commit 8a6edc1, "fix: create") and is the reference pattern.

Fix: route both span-wrapped buttons through ``e.target.closest("#...")`` —
``assets/theme-preview.js`` only; the Python markup is unchanged. Introduced in
commit 264d21c (the span markup and the strict-id handler were added together)
and never revisited until now.

The repo has no JS test runner, so the JS side is guarded with static-source
regex against ``assets/theme-preview.js`` (matching ``TestThemePreviewSurface``
in ``tests/test_theme_preset_url.py``). These tests pin the contract so the
strict-equality footgun cannot silently return.
"""

import pathlib
import re

import pytest

ROOT_DIR = pathlib.Path(__file__).parent.parent
THEME_PREVIEW_JS = ROOT_DIR / "assets" / "theme-preview.js"
_JS = THEME_PREVIEW_JS.read_text(encoding="utf-8")

# The two buttons whose labels are wrapped in hit-testable <span> children in
# the rendered DOM. A click anywhere on their surface — including directly on
# the label text, whose event target is the inner <span> — must still trigger
# the action, so the delegate MUST use ``e.target.closest("#<id>")`` rather than
# a strict ``e.target.id === "<id>"`` equality (which only matches clicks on
# the <button> itself).
_SPAN_WRAPPED_BUTTON_IDS = ("copy-css-preset", "copy-theme-button")


def _strip_line_comments(src: str) -> str:
    """Drop full-line ``//`` comments so the legacy commented-out handler
    (preserved verbatim in a comment block at the bottom of theme-preview.js,
    which still contains the old strict ``e.target.id === "..."`` checks)
    does not satisfy the "absent" guards.
    """
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


class TestSpanWrappedButtonsUseClosestDelegation:
    @pytest.mark.parametrize(  # pyright: ignore[reportUntypedFunctionDecorator]
        "btn_id",
        _SPAN_WRAPPED_BUTTON_IDS,
    )
    def test_delegates_via_closest(self, btn_id: str) -> None:
        assert re.search(
            rf'e\.target\.closest\s*&&\s*e\.target\.closest\(\s*"#{btn_id}"\s*\)',
            _JS,
        ), (
            f"the click delegate must match #{btn_id} via e.target.closest() so "
            "clicks on the inner <span> label still trigger the action"
        )

    @pytest.mark.parametrize(  # pyright: ignore[reportUntypedFunctionDecorator]
        "btn_id",
        _SPAN_WRAPPED_BUTTON_IDS,
    )
    def test_does_not_use_strict_target_id_match(self, btn_id: str) -> None:
        active = _strip_line_comments(_JS)
        assert not re.search(rf'e\.target\.id\s*===\s*"{btn_id}"', active), (
            f"the click delegate must not match {btn_id} via strict "
            'e.target.id === "..."; a click on the inner <span> label makes '
            "e.target the span and silently drops the action"
        )


class TestCopyCssPresetBranch:
    def test_branch_writes_clipboard_and_swaps_label_to_copied(self) -> None:
        """The whole copy contract — clipboard write + "Copied!" feedback +
        reset to "Copy" — lives inside the (now ``closest``-guarded) branch 1,
        delimited by the file's own section comments so the body is scoped to
        this button rather than to any neighbour."""
        match = re.search(
            r"//\s*---\s*1\.\s*COPY ACTION\s*---\n([\s\S]*?)\n\s*//\s*---\s*2\.\s*GET CODE",
            _JS,
        )
        assert match, "the '1. COPY ACTION' section must exist in theme-preview.js"
        body = match.group(1)
        assert 'closest("#copy-css-preset")' in body, (
            "the copy branch must be gated on e.target.closest('#copy-css-preset')"
        )
        assert "navigator.clipboard.writeText(getThemeCSS())" in body, (
            "the copy branch must write the generated theme CSS to the clipboard"
        )
        assert 'getElementById("css-theme-copy-text")' in body, (
            "the copy branch must read back the visible label span to swap its text"
        )
        assert '"Copied!"' in body, "clicking copy must show 'Copied!' feedback"
        assert '"Copy"' in body, "the label must reset back to 'Copy' after the timeout"
