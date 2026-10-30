"""Regression coverage for ``components/ui/table.py``'s ``DATA_TABLE_JS`` client
controller when the table's rows change dynamically (add / delete / async load
via ``rx.State`` / ``rx.foreach``).

The controller shipped in commit 94b22ce snapshot the ``<tbody><tr>`` set once
at mount (``rows = tbody.querySelectorAll('tr')`` captured immediately after the
init-time ``tbody`` lookup) and every later filter / sort / paginate pass
operated on that frozen array. Because Reflex re-renders the table through
React reconciliation on every state delta (``on_mount`` compiles to
``useEffect(() => {...}, [])`` in reflex 0.10.0, so ``init`` runs exactly once),
any state-driven row mutation silently diverged the controller's internal
snapshot from the live DOM:

* newly added ``<tr>`` elements were never in ``rows`` and stayed fully visible,
  bypassing the active search filter and pagination;
* deleted ``<tr>`` elements still existed as detached node references in
  ``rows`` and were re-inserted into the live ``tbody`` by ``tbody.appendChild(r)``
  in ``render()`` (rows visibly resurrected, sometimes duplicated);
* count labels ("1-5 of 10", "Page 1 of 2") derived from ``rows.length`` went
  stale; and
* a table whose ``<tbody>`` mounted after ``init`` was permanently dead, because
  ``root.__dtInitialized`` was set before the ``if (!tbody) return`` bail-out.

The fix re-snapshots the rows on every render (deriving ``rows`` lazily inside
``render()``), re-queries ``tbody`` per render so a replaced ``<tbody>`` is
handled, drives re-renders automatically via a ``MutationObserver`` on the
table root (so added/removed rows are re-filtered/re-paginated without any user
interaction), moves the row-checkbox ``change`` listener onto ``root`` so it
survives ``<tbody>`` replacement, and exposes a ``refresh(tableId)`` hook for
an explicit re-snapshot. The observer is disconnected while ``render()`` writes
to the DOM so the re-order ``appendChild`` never re-triggers the callback.

There is no JS runtime in the test suite (the established convention for JS
controllers in this repo — see ``test_tabs.py`` / ``test_dialog.py`` /
``test_menu.py``), so these tests guard the shipped ``DATA_TABLE_JS`` source
constant with structural substring/anti-substring assertions that pin the
re-snapshot design and catch any regression to the frozen-snapshot model. The
controller's end-to-end behaviour (add/delete/search/paginate over a
state-backed table) was verified against the shipped JS in a real browser
via Playwright.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import reflex as rx

from components.ui.table import DATA_TABLE_JS, TableRoot, table

if TYPE_CHECKING:
    from collections.abc import Iterator


# ---------------------------------------------------------------------------
# JS-source guardrails: the fix signatures must be present, the bug
# signatures must be gone. This is the primary committed verification of the
# client-side controller (no JS runtime in the suite).
# ---------------------------------------------------------------------------


def test_re_snapshot_lives_inside_render_not_at_init() -> None:
    """The frozen mount-time snapshot was ``var rows = ...querySelectorAll(':scope > tr')``
    captured *before* ``var render``. After the fix the only
    ``querySelectorAll(':scope > tr')`` call is made *inside* ``render`` on every
    pass, so the snapshot index must
    land after the ``render`` definition. This single ordering assertion is the
    structural signature that distinguishes the re-snapshot design from the
    frozen one (in both designs the call appears exactly once; only its
    position relative to ``var render`` changes)."""
    render_idx = DATA_TABLE_JS.index("var render = function")
    snapshot_idx = DATA_TABLE_JS.index("querySelectorAll(':scope > tr')")
    assert render_idx < snapshot_idx, (
        "the <tbody><tr> re-snapshot must be made inside render(); before the"
        " fix it was captured once at init (before render) and frozen forever"
    )


def test_tbody_is_re_queried_per_render() -> None:
    """render() must look up ``tbody`` on every call (not close over a mount-time
    reference) so a React-reconciled ``<tbody>`` replacement is handled. The
    re-query must happen *inside* render, after the render definition."""
    render_idx = DATA_TABLE_JS.index("var render = function")
    tbody_idx = DATA_TABLE_JS.index("var tbody = root.querySelector('tbody')")
    assert render_idx < tbody_idx, (
        "tbody must be re-queried inside render(); a mount-time closure goes"
        " stale when React replaces <tbody>"
    )


def test_selection_pruned_to_live_rows_inside_render() -> None:
    """A state-driven row deletion fires no ``change`` event, so without an
    explicit prune ``state.selected`` keeps values of rows no longer in the DOM
    and a re-added row recycling a deleted id renders pre-checked. render() must
    intersect ``state.selected`` with the live rows' checkbox values on every
    pass. This is the core behavioral fix of the commit, so it gets its own
    structural pin: deleting the pruning block must fail this test."""
    assert "var liveValues = {};" in DATA_TABLE_JS, (
        "render must build a set of live checkbox values to prune against"
    )
    assert "if (!liveValues[v]) state.selected.delete(v);" in DATA_TABLE_JS, (
        "render must delete stale values from state.selected"
    )
    # The prune must run inside render() after the :scope > tr re-snapshot.
    render_idx = DATA_TABLE_JS.index("var render = function")
    snapshot_idx = DATA_TABLE_JS.index("querySelectorAll(':scope > tr')")
    prune_idx = DATA_TABLE_JS.index("var liveValues = {};")
    assert render_idx < snapshot_idx < prune_idx, (
        "the selection prune must sit inside render() after the row re-snapshot"
    )


def test_mutation_observer_auto_rerenders_on_dom_change() -> None:
    """A ``MutationObserver`` on the root must re-render on row add/remove so a
    newly inserted row is re-filtered/re-paginated without any user
    interaction (the bug: added rows sat visible under an active search)."""
    assert "new MutationObserver(" in DATA_TABLE_JS, (
        "controller must observe the table DOM and re-render on change"
    )
    assert "observer.observe(root, { childList: true, subtree: true })" in DATA_TABLE_JS
    assert "childList: true, subtree: true" in DATA_TABLE_JS


def test_render_disconnects_observer_during_dom_writes() -> None:
    """render() re-orders rows with ``tbody.appendChild`` (a childList mutation).
    To keep the observer from re-triggering render off its own writes, render
    must disconnect before mutating the DOM and reconnect afterwards."""
    assert "if (observer) observer.disconnect()" in DATA_TABLE_JS
    assert (
        "if (observer) observer.observe(root, { childList: true, subtree: true })"
        in DATA_TABLE_JS
    )
    disc_idx = DATA_TABLE_JS.index("observer.disconnect()")
    append_idx = DATA_TABLE_JS.index("tbody.appendChild(r)")
    # The reconnect that CLOSES render is the first observer.observe at or after
    # the appendChild; the no-tbody early-return branch also observes, so a
    # naive .index() would pick that earlier occurrence and lose the ordering.
    recon_idx = DATA_TABLE_JS.find(
        "observer.observe(root, { childList: true, subtree: true })",
        append_idx,
    )
    assert recon_idx != -1, "render must reconnect the observer after its writes"
    assert disc_idx < append_idx < recon_idx, (
        "render must disconnect the observer before its appendChild writes and"
        " reconnect only after them, otherwise the re-order re-triggers render"
    )


def test_refresh_hook_is_exposed() -> None:
    """The recommended refresh(tableId) re-snapshot hook must exist both on the
    per-table registry entry and as a top-level ``window.__dataTable.refresh``
    for callers that want to force a re-render."""
    assert "refresh: function ()" in DATA_TABLE_JS
    assert "render();" in DATA_TABLE_JS
    assert "refresh(tableId)" in DATA_TABLE_JS, (
        "window.__dataTable.refresh(tableId) top-level hook must be exposed"
    )
    assert "entry.refresh()" in DATA_TABLE_JS


def test_row_checkbox_change_listener_is_on_root_not_tbody() -> None:
    """The change listener must be delegated to ``root`` (always present) so it
    survives a React ``<tbody>`` replacement; attaching it to the mount-time
    ``tbody`` reference is lost when React swaps the body."""
    assert "root.addEventListener('change'" in DATA_TABLE_JS
    assert "tbody.addEventListener('change'" not in DATA_TABLE_JS, (
        "the row-checkbox change listener must not be bound to the mount-time"
        " tbody; it dies when React replaces <tbody>"
    )


def test_init_no_longer_bails_dead_when_tbody_is_missing_at_mount() -> None:
    """The old controller set ``root.__dtInitialized = true`` *before* its
    ``if (!tbody) return`` bail-out, so a table whose ``<tbody>`` mounted after
    init was permanently dead (re-init was a no-op). The early ``return`` is
    gone; ``tbody`` absence is now handled inside render() and the observer
    re-renders once ``<tbody>`` appears."""
    assert "if (!tbody) return;" not in DATA_TABLE_JS, (
        "the unconditional init-level `if (!tbody) return;` is gone; render()"
        " handles a missing tbody with a guarded reconnect+return instead"
    )
    assert "root.__dtInitialized = true" in DATA_TABLE_JS, (
        "the once-per-mount re-init guard must be preserved to avoid"
        " double-attaching listeners/observers on remount"
    )


def test_init_still_guards_double_init_and_bails_on_missing_root() -> None:
    """The re-init guard and the document/root existence checks from the original
    controller must remain (regression guard for sibling behaviour)."""
    assert 'if (typeof document === "undefined") return' in DATA_TABLE_JS
    assert "if (!root || root.__dtInitialized) return" in DATA_TABLE_JS
    assert "window.__dataTable = window.__dataTable || {" in DATA_TABLE_JS


# ---------------------------------------------------------------------------
# Component-level wiring: on_mount must still launch the controller, and the
# controller module must still ship as custom code.
# ---------------------------------------------------------------------------


def _walk_components(comp: Any) -> Iterator[Any]:
    yield comp
    for child in getattr(comp, "children", []) or []:
        if hasattr(child, "custom_attrs") or hasattr(child, "event_triggers"):
            yield from _walk_components(child)


def _extract_event_js(
    comp: Any,
    trigger_name: str,
    needle: str | None = None,
) -> list[str]:
    """Walk the rendered component tree and pull the JS string(s) injected into a
    given event trigger. Mirrors the pattern in ``test_tabs.py`` so the on_mount
    call_script can be asserted on without a JS runtime."""
    out: list[str] = []
    for node in _walk_components(comp):
        et = getattr(node, "event_triggers", {}) or {}
        spec = et.get(trigger_name)
        if spec is None:
            continue
        events = getattr(spec, "events", None) or [spec]
        for ev in events:
            stack: list[Any] = list(getattr(ev, "args", None) or ())
            while stack:
                item = stack.pop()
                if isinstance(item, (tuple, list)):
                    stack.extend(item)
                    continue
                value = getattr(item, "_var_value", None)
                if isinstance(value, str) and (needle is None or needle in value):
                    out.append(value)
    return out


def _build_table(**root_kwargs: Any) -> Any:
    return table.root(
        table.header(table.row(table.head("Name", sort_key="name"))),
        table.body(
            table.row(table.cell("Acme"), **{"data-dt-row": "1"}),
        ),
        **root_kwargs,
    )


def test_on_mount_launches_controller_with_id_and_page_size() -> None:
    """``TableRoot.create`` must wire ``on_mount`` to ``window.__dataTable.init``
    baking the runtime table id and the configured page size (the entry point
    the fix runs through)."""
    comp = _build_table(id="my-tbl", paginate=True, page_size=7)
    scripts = _extract_event_js(comp, "on_mount", needle="window.__dataTable.init")
    assert scripts, "TableRoot must attach the controller init script on mount"
    js = scripts[0]
    assert "window.__dataTable.init('my-tbl', {pageSize: 7})" in js, (
        f"init script must bake the runtime id and page size; got {js!r}"
    )


def test_on_mount_present_even_without_search_or_pagination() -> None:
    """The controller must always mount (it owns sort + selection even without
    toolbar/pagination), so ``on_mount`` is present for the minimal table."""
    comp = _build_table()
    assert _extract_event_js(comp, "on_mount", needle="window.__dataTable.init"), (
        "on_mount controller init must be attached even without searchable/paginate"
    )


def test_custom_code_ships_data_table_js() -> None:
    """``TableRoot.add_custom_code`` must emit exactly ``[DATA_TABLE_JS]`` so the
    controller module lands on the page once per table-root mount."""
    comp = _build_table(id="x")
    assert comp.add_custom_code() == [DATA_TABLE_JS]
    assert TableRoot.add_custom_code.__name__ == "add_custom_code"


# ---------------------------------------------------------------------------
# Demo build smoke (mirrors test_switch_passthrough / test_tabs demo tests):
# every shipped table demo must still construct cleanly after the controller
# rework.
# ---------------------------------------------------------------------------


DEMO_MODULES = [
    ("native.lib.components.table_demo", "table_block"),
    ("native.lib.components.table_demo_two", "table_demo_two"),
]


@pytest.mark.parametrize(
    ("module_path", "fn_name"),
    DEMO_MODULES,
    ids=[m[1] for m in DEMO_MODULES],
)  # pyright: ignore[reportUntypedFunctionDecorator]
def test_in_repo_table_demos_build(module_path: str, fn_name: str) -> None:
    """Both shipped demos render rows from hardcoded module-level constants and
    must still build (the controller is wired on mount; construction must not
    regress)."""
    import importlib

    mod = importlib.import_module(module_path)
    comp = getattr(mod, fn_name)()
    assert isinstance(comp, rx.Component), (
        f"{fn_name} did not return an rx.Component: {type(comp).__name__}"
    )
