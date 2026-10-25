"""Regression tests for the /typeset page layout.

Guards against the off-by-one breakpoint bug where the "Get Code"
panel (``#source-space``) became unreachable on viewports in the
Tailwind ``lg``-``xl`` band (1024px <= width < 1280px): the panel used
``xl:flex`` as its only desktop always-visible override while the
"Get Code/Preview" toggle button was ``lg:hidden``, leaving the
[1024, 1280)px range with neither a visible panel nor a toggle to
reveal it. The fix is to make the panel always visible at ``lg``
(``lg:flex``), matching the breakpoint where the page switches to its
three-column desktop layout (``lg:flex-row``) and where the toggle
disappears (``lg:hidden``).

These tests assert the class-string contract statically (no browser
required) so the regression cannot silently return.

Also guards the SPA-navigation select-sync fix for the desync bug
introduced in ``e6118bff`` (the commit that created the /typeset
playground): the page's ``on_mount`` script only re-applied the
persisted JS state to the preview and code blocks but never synced the
freshly remounted ``<select>`` controls to that state, and the
internal ``syncSelectsToState()`` was never exported on
``window.typesetPreview`` -- so after a user changed selections (or
clicked Shuffle) and then SPA-navigated away and back, the preview
and "Get Code" output reflected the prior selections while all seven
selects showed the Python defaults again. The fix mirrors the sibling
``/create`` page's ``a7c0cdb`` fix: export a ``syncAll()`` entry point
from ``assets/typeset-preview.js`` that calls
``ensureDefaults() -> syncSelectsToState() -> applyAll() ->
renderCodeBlocks()``, and invoke it from ``on_mount`` in place of the
bare ``applyAll()`` + ``renderCodeBlocks()`` pair.

The repo has no JS test runner, so the JS export surface is guarded
by Python regex against the JS source text -- the same convention
used by ``tests/test_theme_preset_url.py`` for ``theme-preview.js``.
"""

import pathlib
import re
from typing import Any

from native.pages.typeset import source_space, typeset_page

ROOT_DIR = pathlib.Path(__file__).parent.parent
TYPESET_PREVIEW_JS = ROOT_DIR / "assets" / "typeset-preview.js"

_CLASS_DELIMS = str.maketrans({'"': " ", "(": " ", ")": " ", ",": " "})


def _is_component(node: Any) -> bool:
    return hasattr(node, "children") and hasattr(node, "class_name")


def _find_by_id(root: Any, target_id: str) -> Any:
    """Depth-first search for a Reflex component whose ``id`` equals ``target_id``."""
    if _is_component(root):
        cid = root.id if hasattr(root, "id") else None
        if isinstance(cid, str) and cid == target_id:
            return root
        children = root.children if hasattr(root, "children") else None
        if isinstance(children, list):
            for child in children:
                found = _find_by_id(child, target_id)
                if found is not None:
                    return found
    return None


def _class_str(component: Any) -> str:
    cls = component.class_name
    return cls if isinstance(cls, str) else str(cls)


def _tokens(cls: str) -> set[str]:
    return set(cls.translate(_CLASS_DELIMS).split())


def test_source_space_is_always_visible_at_lg_not_xl() -> None:
    cls = source_space().class_name
    assert isinstance(cls, str)
    tokens = _tokens(cls)

    assert "hidden" in tokens, "base visibility must be hidden (mobile default)"
    assert "max-lg:group-data-[show=true]:flex" in tokens, (
        "mobile toggle-reveal rule must be preserved"
    )
    assert "lg:flex" in tokens, (
        "desktop always-visible override must activate at lg breakpoint"
    )
    assert "xl:flex" not in tokens, (
        "xl:flex reintroduces the 1024-1279px dead band: the panel would "
        "only reappear at 1280px while the lg:hidden toggle vanishes at 1024px"
    )


def test_typeset_desktop_layout_and_source_panel_share_lg_breakpoint() -> None:
    page = typeset_page()

    wrapper = _find_by_id(page, "typeset-toggle-wrapper")
    assert wrapper is not None, "typeset-toggle-wrapper must exist"
    assert "lg:flex-row" in _tokens(_class_str(wrapper)), (
        "the page switches to its three-column desktop layout at lg; the "
        "source column must therefore also be visible at lg"
    )

    toggle = _find_by_id(page, "typeset-code-button")
    assert toggle is not None, "typeset-code-button toggle must exist"
    assert "lg:hidden" in _tokens(_class_str(toggle)), (
        "the 'Get Code/Preview' toggle must be hidden at lg+ since the "
        "panel is always visible there"
    )

    source = _find_by_id(page, "source-space")
    assert source is not None, "source-space panel must exist"
    source_tokens = _tokens(_class_str(source))
    assert "lg:flex" in source_tokens, (
        "source-space must become always-visible at the same lg breakpoint "
        "where the desktop layout starts (lg:flex-row) and the toggle "
        "disappears (lg:hidden)"
    )
    assert "xl:flex" not in source_tokens, (
        "an xl:flex override on source-space is inconsistent with the "
        "lg:flex-row wrapper and lg:hidden toggle and reintroduces the "
        "1024-1279px dead band"
    )


# ---------------------------------------------------------------------------
# SPA-navigation select-sync regression tests.
#
# The /typeset page persists its JS state in a <head> IIFE that survives
# client-side route changes, but React remounts the page DOM on every SPA
# navigation -- including the uncontrolled <select> controls, which reseed
# to their Python `default_value`. The on_mount hook must therefore sync
# the remounted selects back to the persisted JS state, not just re-apply
# it to the preview/code blocks. The fix mirrors the sibling /create page
# fix from a7c0cdb: export `syncAll()` from assets/typeset-preview.js and
# call it from on_mount. These tests lock in both sides of that contract.
# ---------------------------------------------------------------------------


def _on_mount_scripts(component: Any) -> list[str]:
    """Extract the JS bodies wired into a Reflex component's on_mount chain.

    Mirrors the helper in tests/test_theme_preset_url.py: each on_mount
    event carries its script as the `javascript_code` arg; we pull the
    literal string out so we can assert against it with regex.
    """
    assert "on_mount" in component.event_triggers, (
        "typeset_page() must wire an on_mount lifecycle hook"
    )
    chain = component.event_triggers["on_mount"]
    scripts: list[str] = []
    for event in chain.events:
        for name_var, val_var in event.args:
            if getattr(name_var, "_js_expr", None) == "javascript_code":
                scripts.append(val_var._var_value)  # noqa: SLF001
                break
    return scripts


_TYPESET_SCRIPTS = _on_mount_scripts(typeset_page())
_INIT_SCRIPT = _TYPESET_SCRIPTS[0]
_JS = TYPESET_PREVIEW_JS.read_text(encoding="utf-8")

_MIN_ON_MOUNT_SCRIPTS = 2


class TestTypesetOnMountScript:
    """Locks in the on_mount JS body emitted by native/pages/typeset.py."""

    def test_registries_are_populated_before_sync_all(self) -> None:
        assert "__TYPESET_REGISTRIES__" in _INIT_SCRIPT
        for key in (
            "headingBodyFonts:",
            "monoFonts:",
            "measure:",
            "size:",
            "leading:",
            "flow:",
        ):
            assert key in _INIT_SCRIPT, f"registry key {key!r} missing from on_mount"
        assert _INIT_SCRIPT.index("__TYPESET_REGISTRIES__") < _INIT_SCRIPT.index(
            "syncAll",
        ), "registries must be populated before the syncAll call reads them"

    def test_calls_sync_all_on_typeset_preview(self) -> None:
        assert re.search(
            r"window\.typesetPreview\.syncAll\s*\(\s*\)\s*;",
            _INIT_SCRIPT,
        ), "on_mount must call window.typesetPreview.syncAll() to re-sync selects"

    def test_does_not_use_bare_apply_all_plus_render_code_blocks(self) -> None:
        # The pre-fix shape (introduced in e6118bff) left the remounted
        # selects desynced: it only re-applied persisted state to the
        # preview and code blocks without first syncing the selects. This
        # regex would match that broken two-line body inside the
        # `if (window.typesetPreview)` block; the fix must not reintroduce it.
        bad = re.search(
            r"window\.typesetPreview\.applyAll\s*\(\s*\)\s*;"
            r"\s*window\.typesetPreview\.renderCodeBlocks\s*\(\s*\)\s*;",
            _INIT_SCRIPT,
        )
        assert bad is None, (
            "on_mount must not call applyAll()+renderCodeBlocks() directly; "
            "it must route through syncAll() so the selects are synced first"
        )

    def test_no_top_level_return_after_sync_all(self) -> None:
        # rx.call_script evaluates the body via top-level eval (no IIFE
        # wrap), so a bare `return;` is a SyntaxError silently swallowed
        # by Reflex's try/catch and the rest of the script never runs.
        # Guard against any top-level `return` after the syncAll() call.
        assert not re.search(
            r"syncAll\s*\(\s*\)\s*;\s*return\b",
            _INIT_SCRIPT,
        ), "on_mount must not use a top-level `return` after syncAll()"

    def test_prism_highlight_remains_wired(self) -> None:
        assert len(_TYPESET_SCRIPTS) >= _MIN_ON_MOUNT_SCRIPTS, (
            "second on_mount script (Prism.highlightAll) was dropped"
        )
        assert "Prism.highlightAll" in _TYPESET_SCRIPTS[1]


class TestTypesetPreviewSurface:
    """Static guards on assets/typeset-preview.js for the public surface the
    on_mount syncAll() call depends on. The repo has no JS test runner, so
    these regex checks are the only automated guard for the JS side."""

    def test_sync_all_is_exported_on_window_typeset_preview(self) -> None:
        # The pre-fix export object (introduced in e6118bff) exposed only
        # state/applyAll/shuffle/getFontLinkCode/getThemeTokensCode/getUsageCode/
        # renderCodeBlocks -- syncAll was missing, so on_mount could not sync
        # the remounted selects. Assert syncAll is now a member of the
        # exported object.
        m = re.search(
            r"window\.typesetPreview\s*=\s*\{([\s\S]*?)\};",
            _JS,
        )
        assert m, "window.typesetPreview export object must exist"
        export_body = m.group(1)
        assert re.search(r"syncAll\s*:\s*syncAll\s*,?", export_body), (
            "syncAll must be a member of the window.typesetPreview export object"
        )

    def test_sync_all_body_calls_required_steps_in_order(self) -> None:
        # syncAll must (1) bail out if registries aren't loaded, (2) sync the
        # remounted selects to the persisted state, (3) re-apply the state to
        # the preview, (4) re-render the code blocks. The ordering matters:
        # syncSelectsToState must run before applyAll/renderCodeBlocks so the
        # controls and the preview/code reflect the same state on the same
        # mount.
        m = re.search(
            r"function\s+syncAll\s*\([^)]*\)\s*\{([\s\S]*?)\}",
            _JS,
        )
        assert m, "syncAll function must be defined in typeset-preview.js"
        body = m.group(1)
        assert re.search(r"ensureDefaults\s*\(\s*\)", body), (
            "syncAll must guard on ensureDefaults() before touching the DOM"
        )
        for needle in ("syncSelectsToState", "applyAll", "renderCodeBlocks"):
            assert needle in body, f"syncAll must call {needle}()"
        idx_ensure = body.index("ensureDefaults")
        idx_sync = body.index("syncSelectsToState")
        idx_apply = body.index("applyAll")
        idx_render = body.index("renderCodeBlocks")
        assert idx_ensure < idx_sync < idx_apply < idx_render, (
            "syncAll must call ensureDefaults -> syncSelectsToState -> applyAll "
            "-> renderCodeBlocks, in that order, so selects are synced before "
            "the preview/code blocks are re-rendered from the same state"
        )

    def test_sync_selects_to_state_targets_select_ids(self) -> None:
        # The function that does the actual <select>.value = state[field]
        # assignment must keep targeting the `field + "-select"` ids that the
        # page emits (measure-select, heading-select, ...). This is the
        # mechanism syncAll depends on; if it were renamed or retargeted the
        # fix would silently stop working.
        m = re.search(
            r"function\s+syncSelectsToState\s*\([^)]*\)\s*\{([\s\S]*?)\}",
            _JS,
        )
        assert m, "syncSelectsToState function must be defined"
        body = m.group(1)
        assert re.search(r'field\s*\+\s*"-select"', body), (
            "syncSelectsToState must look up selects by field + '-select' id"
        )
