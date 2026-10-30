"""Regression coverage for the dialog popup crash when ``dismissible=False``
or ``on_open_change=...`` was passed to ``dialog.popup(...)``.

Both options previously raised at component-construction time:

    ValueError: The Dialog does not take in an 'on_cancel' event trigger
    ValueError: The Dialog does not take in an 'on_close' event trigger

because ``DialogPopup`` wired ``on_cancel`` / ``on_close`` into ``props`` and
passed them to ``rx.el.dialog(...)``, whose underlying element does not declare
those triggers. The tests pin the four contracts the fix restored:
``DialogPopup`` declares ``on_close`` / ``on_cancel`` as class-level triggers,
the popup renders a native ``<dialog>`` with ``data-slot="dialog-content"``,
``dismissible=False`` wires ``on_cancel`` only, and ``on_open_change=`` wires
``on_close`` only. See bug #4 and PR #23.
"""

from typing import Any

import reflex as rx
from reflex_components_core.el.elements.other import Dialog

from components.ui.dialog import DialogPopup, dialog


class _DialogState(rx.State):  # pyright: ignore [reportUntypedBaseClass]
    open: bool = True

    def set_open(self, *, value: bool) -> None:
        self.open = value


def test_dialog_popup_declares_on_close_and_on_cancel_triggers() -> None:
    triggers = DialogPopup.get_event_triggers()
    assert "on_close" in triggers
    assert "on_cancel" in triggers


def test_popup_is_a_dialog_element_with_data_slot() -> None:
    popup = dialog.popup(dialog.title("title"), dismissible=False)
    assert isinstance(popup, Dialog)
    assert popup.tag == "dialog"
    assert popup.custom_attrs.get("data-slot") == "dialog-content"


def test_dismissible_false_wires_on_cancel() -> None:
    popup = dialog.popup(dialog.title("title"), dismissible=False)
    assert "on_cancel" in popup.event_triggers
    assert "on_close" not in popup.event_triggers


def test_on_open_change_wires_on_close() -> None:
    handler: Any = _DialogState.set_open
    popup = dialog.popup(dialog.title("title"), on_open_change=handler)
    assert "on_close" in popup.event_triggers
    assert "on_cancel" not in popup.event_triggers


def test_dialog_parts_generate_no_ids_and_root_owns_handler() -> None:
    from components.ui.dialog import GLOBAL_HANDLERS_JS

    for part in (dialog.trigger("t"), dialog.close("c"), dialog.popup("p")):
        assert "id" not in part.render()["props"] or not any(
            p.startswith("id:") for p in part.render()["props"]
        )
    assert "getElementById" not in GLOBAL_HANDLERS_JS
    assert "__dialogGlobalHandlersAttached" in GLOBAL_HANDLERS_JS
    assert "on_mount" in dialog.root("x").event_triggers


# ---------------------------------------------------------------------------
# Backdrop-detection regression: interior clicks on the dialog's own
# padding/gap must NOT close a dismissible dialog -- only true outside
# (backdrop) clicks should. See the ff470dc backdrop-detection bug.
# ---------------------------------------------------------------------------

# Representative dialog bounding rect (the card occupies this box).
_RECT = {"left": 189, "top": 239, "right": 611, "bottom": 361}


def _popup(*, dismissible: bool = True, rect: dict[str, Any] = _RECT) -> dict[str, Any]:
    """Pseudo-DOM model of a ``dialog.popup`` element with the same dismissible
    opt-in and runtime bounding box the shipped JS reads."""
    return {"dismissible": dismissible, "rect": rect, "open": True}


def _dispatch(popup: dict[str, Any], kind: str, cx: int, cy: int) -> None:
    """Faithful pure-Python mirror of ``GLOBAL_HANDLERS_JS``'s capture-phase
    click handler. ``kind`` is the hit-test target the click resolves to in a
    real browser: ``"trigger"`` (nearest dialog-trigger ancestor), ``"close"``
    (nearest dialog-close ancestor), ``"child"`` (a descendant element, so
    ``target.matches('dialog...')`` is false), or ``"dialog"`` (the dialog
    element itself -- both interior padding/gaps AND the ::backdrop retarget
    to it, which is exactly the case the bounds check disambiguates)."""
    if kind == "trigger":
        popup["open"] = True
        return
    if kind == "close":
        popup["open"] = False
        return
    if kind == "child":
        return
    # kind == "dialog": target is the dialog element (interior OR backdrop).
    if not popup["dismissible"]:
        return
    r = popup["rect"]
    if cx < r["left"] or cx > r["right"] or cy < r["top"] or cy > r["bottom"]:
        popup["open"] = False


def test_global_handlers_js_backdrop_close_is_gated_by_bounds_check() -> None:
    """The shipped JS must distinguish a true backdrop click from a click on
    the dialog's own padding/gap with a client-coordinate bounds check -- the
    naive ``target.close()`` after only a target/disisible match closed the
    dialog on interior clicks. Pin the fix's structural pieces in the actual
    JS string so the regression can't silently return."""
    from components.ui.dialog import GLOBAL_HANDLERS_JS

    assert (
        "target.matches('dialog[data-slot=\"dialog-content\"]')" in GLOBAL_HANDLERS_JS
    )
    assert "target.getAttribute('data-dismissible') === 'true'" in GLOBAL_HANDLERS_JS
    assert "getBoundingClientRect()" in GLOBAL_HANDLERS_JS
    assert "e.clientX" in GLOBAL_HANDLERS_JS and "e.clientY" in GLOBAL_HANDLERS_JS
    assert "e.clientX < r.left" in GLOBAL_HANDLERS_JS
    assert "e.clientX > r.right" in GLOBAL_HANDLERS_JS
    assert "e.clientY < r.top" in GLOBAL_HANDLERS_JS
    assert "e.clientY > r.bottom" in GLOBAL_HANDLERS_JS
    # The bugged form closed immediately after the dismissible check with no
    # bounds check; that exact sequence must be gone.
    assert "=== 'true'\n        ) {\n            target.close();\n        }" not in (
        GLOBAL_HANDLERS_JS
    ), "dialog must not close on a target match alone -- bounds check is required"


def test_interior_clicks_on_padding_and_gap_keep_dismissible_dialog_open() -> None:
    """Clicks inside the dialog box that hit the dialog element -- the p-4
    padding strip and the gap-4 gutter between children -- previously dismissed
    the dialog (target === dialog indistinguishable from ::backdrop). They must
    keep a dismissible dialog open so in-progress input is not discarded."""
    p = _popup()
    _dispatch(p, "dialog", _RECT["left"] + 8, _RECT["top"] + 8)
    assert p["open"] is True
    _dispatch(p, "dialog", _RECT["right"] - 8, _RECT["bottom"] - 8)
    assert p["open"] is True
    # Midpoint of the gap-4 gutter between header and body.
    _dispatch(
        p,
        "dialog",
        (_RECT["left"] + _RECT["right"]) // 2,
        (_RECT["top"] + _RECT["bottom"]) // 2,
    )
    assert p["open"] is True


def test_true_backdrop_click_closes_dismissible_dialog() -> None:
    """A click outside the dialog rect (the m-auto margin / ::backdrop area)
    must still close a dismissible dialog -- the bounds check must not break
    intended dismissal on any side."""
    p = _popup()
    _dispatch(p, "dialog", _RECT["left"] - 40, (_RECT["top"] + _RECT["bottom"]) // 2)
    assert p["open"] is False
    p = _popup()
    _dispatch(p, "dialog", _RECT["right"] + 40, (_RECT["top"] + _RECT["bottom"]) // 2)
    assert p["open"] is False
    p = _popup()
    _dispatch(p, "dialog", (_RECT["left"] + _RECT["right"]) // 2, _RECT["top"] - 40)
    assert p["open"] is False
    p = _popup()
    _dispatch(p, "dialog", (_RECT["left"] + _RECT["right"]) // 2, _RECT["bottom"] + 40)
    assert p["open"] is False


def test_edge_pixel_clicks_on_rect_border_keep_dialog_open() -> None:
    """The bounds check uses strict ``<``/``>``, so a click exactly on the
    rect border is inside the dialog and must keep it open -- pin the strict
    comparison so a future ``<=``/``>=`` change can't silently dismiss at the
    card edges."""
    p = _popup()
    _dispatch(p, "dialog", _RECT["left"], _RECT["top"])
    assert p["open"] is True
    _dispatch(p, "dialog", _RECT["right"], _RECT["bottom"])
    assert p["open"] is True
    _dispatch(p, "dialog", _RECT["right"], _RECT["top"])
    assert p["open"] is True
    _dispatch(p, "dialog", _RECT["left"], _RECT["bottom"])
    assert p["open"] is True
