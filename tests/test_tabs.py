from __future__ import annotations

from typing import TYPE_CHECKING, Any

import reflex as rx

from components.ui.tabs import GLOBAL_HANDLERS_JS, tabs

if TYPE_CHECKING:
    from collections.abc import Iterator

Node = dict[str, Any]

DEMO_MODULES = {
    "basic": ("native.lib.components.tabs_basic", "tabs_basic"),
    "disabled": ("native.lib.components.tabs_disabled", "tabs_disabled"),
    "icons": ("native.lib.components.tabs_icons", "tabs_icons"),
    "line": ("native.lib.components.tabs_line_variant", "tabs_line"),
    "vertical": ("native.lib.components.tabs_vertical", "tabs_vertical"),
}

GUARD_SUBSTRING = "closest('[data-slot=\"tabs\"]') !== root"


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
    out = []
    for node in _walk_components(comp):
        et = getattr(node, "event_triggers", {}) or {}
        spec = et.get(trigger_name)
        if spec is None:
            continue
        events = getattr(spec, "events", None) or [spec]
        for ev in events:
            stack = list(getattr(ev, "args", None) or ())
            while stack:
                item = stack.pop()
                if isinstance(item, (tuple, list)):
                    stack.extend(item)
                    continue
                value = getattr(item, "_var_value", None)
                if isinstance(value, str) and (needle is None or needle in value):
                    out.append(value)
    return out


def _extract_on_click_js(comp: Any) -> list[str]:
    return _extract_event_js(comp, "on_click", needle="querySelectorAll")


def _extract_on_mount_js(comp: Any) -> list[str]:
    return _extract_event_js(comp, "on_mount", needle="addEventListener")


def _build_nested_tree(default_inner: str = "profile") -> Any:
    return tabs.root(
        tabs.list(
            tabs.trigger("Home", value="home", id="outer-home"),
            tabs.trigger("Settings", value="settings", id="outer-settings"),
        ),
        tabs.content(
            tabs.root(
                tabs.list(
                    tabs.trigger("Profile", value="profile", id="inner-prof"),
                    tabs.trigger("Security", value="security", id="inner-sec"),
                ),
                tabs.content("Profile panel", value="profile"),
                tabs.content("Security panel", value="security"),
                default_value=default_inner,
            ),
            value="settings",
        ),
        default_value="settings",
    )


def _dom_tree(comp: Any) -> Node:
    ca = getattr(comp, "custom_attrs", {}) or {}
    return {
        "slot": ca.get("data-slot"),
        "value": ca.get("data-value"),
        "id": getattr(comp, "id", None),
        "active": None,
        "children": [
            _dom_tree(child)
            for child in (getattr(comp, "children", []) or [])
            if hasattr(child, "custom_attrs") or hasattr(child, "event_triggers")
        ],
    }


def _index_parents(
    node: Node,
    parent: Node | None = None,
    mapping: dict[int, Node | None] | None = None,
) -> dict[int, Node | None]:
    if mapping is None:
        mapping = {}
    mapping[id(node)] = parent
    for child in node["children"]:
        _index_parents(child, node, mapping)
    return mapping


def _closest(node: Node, slot: str, parents: dict[int, Node | None]) -> Node | None:
    cur = node
    while cur is not None:
        if cur.get("slot") == slot:
            return cur
        cur = parents.get(id(cur))
    return None


def _descendants_with_slot(node: Node, slot: str) -> list[Node]:
    out: list[Node] = []
    for child in node["children"]:
        if child.get("slot") == slot:
            out.append(child)
        out.extend(_descendants_with_slot(child, slot))
    return out


def _find_by_id(node: Node, node_id: str) -> Node | None:
    if node.get("id") == node_id:
        return node
    for child in node["children"]:
        found = _find_by_id(child, node_id)
        if found:
            return found
    return None


def _all_triggers(node: Node) -> list[Node]:
    out: list[Node] = []
    for child in node["children"]:
        if child.get("slot") == "tabs-trigger":
            out.append(child)
        out.extend(_all_triggers(child))
    return out


def _simulate_mount(root: Node) -> None:
    parents = _index_parents(root)
    for trigger in _all_triggers(root):
        group = _closest(trigger, "tabs", parents)
        trigger["active"] = (
            "true" if group and group.get("value") == trigger.get("value") else "false"
        )


def _simulate_click(root: Node, trigger_node: Node, *, with_guard: bool) -> None:
    parents = _index_parents(root)
    group = _closest(trigger_node, "tabs", parents)
    if group is None:
        return
    clicked_value = trigger_node.get("value")
    group["value"] = clicked_value
    for target in _descendants_with_slot(group, "tabs-trigger"):
        own_group = _closest(target, "tabs", parents)
        if with_guard and own_group is not group:
            continue
        target["active"] = "true" if target.get("value") == clicked_value else "false"


def test_on_click_handler_contains_scope_guard() -> None:
    """Highlight JS moved off the trigger (which is shared across foreach copies)
    and onto a single delegated listener attached by the root on mount. The scope
    guard must still be present in that global handler."""
    comp = tabs.root(
        tabs.list(tabs.trigger("Home", value="home", id="t1")),
        tabs.content("p", value="home"),
        default_value="home",
    )
    handlers = _extract_on_mount_js(comp)
    assert len(handlers) == 1, "expected exactly one delegated click-handler script"
    assert GUARD_SUBSTRING in handlers[0]


def test_global_handler_resolves_trigger_and_value_from_runtime_dom() -> None:
    """The shared highlight script must not bake a build-time id or the per-item
    value Var into the JS source; it must read both off the runtime DOM so one
    script works for every rendered copy (including rx.foreach items)."""
    comp = tabs.root(
        tabs.list(tabs.trigger("Home", value="home", id="t1")),
        tabs.content("p", value="home"),
        default_value="home",
    )
    handlers = _extract_on_mount_js(comp)
    assert handlers, "root must attach the global handler on mount"
    js = handlers[0]
    assert "document.addEventListener('click'" in js, (
        "highlight must be a delegated click listener (real DOM event, not a"
        " call_script eval with no event scope)"
    )
    assert "getAttribute('data-value')" in js, (
        "clicked trigger value must be read from the rendered DOM attribute"
    )
    assert "getElementById" not in js, (
        "must not key on a build-time element id (duplicated across foreach copies)"
    )
    assert "{value}" not in js and "{trigger_id}" not in js, (
        "JS source must not contain build-time f-string placeholders that bake the"
        " Var placeholder name across foreach copies"
    )
    assert "=== '" not in js, (
        "trigger value comparison must be against a runtime DOM read, never a"
        " baked string literal (the foreach-bug signature `=== '{value}'`)"
    )
    assert "dataset.value = '" not in js, (
        "root value assignment must use the runtime DOM read, never a baked"
        " string literal"
    )
    assert "window.__tabsGlobalHandlersAttached" in js, (
        "delegated listener must be attached exactly once per page"
    )


def test_trigger_does_not_dispatch_internal_highlight_js() -> None:
    """Triggers rendered from rx.foreach share a single create() result, so no
    per-trigger call_script may be injected (it would run identically for every
    copy and bake the Var placeholder for the value)."""
    trigger = tabs.trigger("Home", value="home")
    assert _extract_on_click_js(trigger) == [], (
        "tabs.trigger must not emit its own highlight call_script on click"
    )
    on_mount = _extract_event_js(trigger, "on_mount", needle="addEventListener")
    assert on_mount == [], "tabs.trigger must not emit its own highlight on_mount"


def test_trigger_does_not_auto_generate_id_when_not_provided() -> None:
    """Auto-generating an id in create() bakes one id shared by every foreach
    copy (invalid HTML + getElementById resolves to the first copy). Triggers
    must leave the id unset when the user does not supply one; an explicit id
    must be preserved verbatim."""
    default_trigger = tabs.trigger("Home", value="home")
    assert getattr(default_trigger, "id", None) is None, (
        "triggers without an explicit id must not get a build-time auto id"
    )
    explicit_trigger = tabs.trigger("Home", value="home", id="custom-id")
    assert getattr(explicit_trigger, "id", None) == "custom-id"


def test_distinct_trigger_instances_do_not_share_an_id() -> None:
    """Two separately-created triggers (the static-control case) must keep their
    own ids and never accidentally share an auto-generated one."""
    a = tabs.trigger("A", value="a", id="x")
    b = tabs.trigger("B", value="b", id="y")
    assert getattr(a, "id", None) != getattr(b, "id", None)
    assert getattr(a, "id", None) == "x"
    assert getattr(b, "id", None) == "y"


_NUM_FOREACH_GROUPS = 3
_FOREACH_TRIGGER_VALUES = ("overview", "analytics", "reports")


def _build_foreach_like_tree(num_groups: int) -> dict[str, Any]:
    """Mirror the canonical broken-usage shape: one tabs.root per data item, each
    with the same set of tab triggers + content panels, so each item renders its
    own independently-switchable group (simulating
    rx.foreach(state.items, lambda item: tabs.root(tabs.list(...), ...)))."""
    triggers = ["overview", "analytics", "reports"]
    roots = [
        tabs.root(
            tabs.list(*(tabs.trigger(t, value=t) for t in triggers)),
            *(tabs.content(t, value=t) for t in triggers),
            default_value=triggers[0],
        )
        for _ in range(num_groups)
    ]
    return {
        "slot": None,
        "value": None,
        "id": None,
        "active": None,
        "children": [_dom_tree(r) for r in roots],
    }


def test_foreach_like_roots_are_independently_switchable() -> None:
    r"""The headline failure: tabs built from a data list. After mount, each group
    highlights only its own default trigger, and clicking a trigger inside one
    group activates/deactivates triggers only within that group -- never routing
    the click to another group (which the shared baked-id ``getElementById``
    lookup did) and never setting the root value to a Var-placeholder literal that
    matches no trigger."""
    dom = _build_foreach_like_tree(_NUM_FOREACH_GROUPS)
    _simulate_mount(dom)
    roots = [c for c in dom["children"] if c.get("slot") == "tabs"]
    assert len(roots) == _NUM_FOREACH_GROUPS
    for root in roots:
        triggers = _all_triggers(root)
        assert len(triggers) == len(_FOREACH_TRIGGER_VALUES)
        assert [t["active"] for t in triggers] == ["true", "false", "false"], (
            "each group highlights only its own default trigger after mount"
        )
    before = {
        i: (root["value"], [t["active"] for t in _all_triggers(root)])
        for i, root in enumerate(roots)
    }
    # Click root[1]'s "analytics" trigger.
    _simulate_click(roots[1], _all_triggers(roots[1])[1], with_guard=True)
    assert roots[1]["value"] == "analytics"
    assert [t["active"] for t in _all_triggers(roots[1])] == ["false", "true", "false"]
    # The other groups must be entirely untouched.
    for i in (0, 2):
        after = (roots[i]["value"], [t["active"] for t in _all_triggers(roots[i])])
        assert after == before[i], (
            f"group[{i}] was disturbed by a click in group[1]; the shared baked-id"
            f" bug would route the click to the wrong group: {after} != {before[i]}"
        )


def test_root_on_mount_preserves_user_supplied_handler() -> None:
    """The internal global handler must coexist with user-supplied on_mount on
    the root (merged, not replaced)."""
    user_marker = "console_log_marker_xyz"
    comp = tabs.root(
        tabs.list(tabs.trigger("Home", value="home")),
        tabs.content("p", value="home"),
        default_value="home",
        on_mount=rx.call_script(user_marker),
    )
    js_blocks = _extract_event_js(comp, "on_mount")
    assert len(js_blocks) >= 1
    assert any("addEventListener" in b for b in js_blocks), (
        "internal delegated listener must still be attached"
    )
    assert any(user_marker in b for b in js_blocks), (
        "user-supplied on_mount must be preserved alongside the internal handler"
    )


def test_trigger_preserves_user_supplied_on_click() -> None:
    """User-supplied on_click on a trigger must pass through untouched now that
    the highlight JS is no longer injected per-trigger."""
    user_marker = "user_click_marker_xyz"
    trigger = tabs.trigger(
        "Home",
        value="home",
        on_click=rx.call_script(user_marker),
    )
    js_blocks = _extract_event_js(trigger, "on_click")
    assert any(user_marker in b for b in js_blocks), (
        "user on_click must pass through to the rendered trigger"
    )
    assert all("querySelectorAll" not in b for b in js_blocks), (
        "no internal highlight JS may be injected into trigger on_click"
    )


def test_global_handlers_js_module_constant_has_guard() -> None:
    """Guard the shipped JS constant directly: it must contain the nested-scope
    guard and the runtime data-value read, and must never contain a build-time
    id lookup, an f-string interpolation placeholder, or a baked string-literal
    value comparison/assignment (the foreach-bug signatures)."""
    assert GUARD_SUBSTRING in GLOBAL_HANDLERS_JS
    assert "getAttribute('data-value')" in GLOBAL_HANDLERS_JS
    assert "document.addEventListener('click'" in GLOBAL_HANDLERS_JS
    assert "getElementById" not in GLOBAL_HANDLERS_JS
    assert "{value}" not in GLOBAL_HANDLERS_JS
    assert "{trigger_id}" not in GLOBAL_HANDLERS_JS
    assert "=== '" not in GLOBAL_HANDLERS_JS
    assert "dataset.value = '" not in GLOBAL_HANDLERS_JS


def test_guard_preserves_nested_highlight_after_outer_click() -> None:
    nested = _build_nested_tree(default_inner="profile")
    dom = _dom_tree(nested)
    _simulate_mount(dom)
    outer_home = _find_by_id(dom, "outer-home")
    inner_prof = _find_by_id(dom, "inner-prof")
    inner_sec = _find_by_id(dom, "inner-sec")
    assert outer_home is not None
    assert inner_prof is not None
    assert inner_sec is not None
    assert inner_prof["active"] == "true"
    assert inner_sec["active"] == "false"
    _simulate_click(dom, outer_home, with_guard=True)
    assert outer_home["active"] == "true"
    outer_settings = _find_by_id(dom, "outer-settings")
    assert outer_settings is not None
    assert outer_settings["active"] == "false"
    assert inner_prof["active"] == "true", (
        "outer click must not clobber inner highlight"
    )
    assert inner_sec["active"] == "false"
    inner_root = _closest(inner_prof, "tabs", _index_parents(dom))
    assert inner_root is not None
    assert inner_root["value"] == "profile", (
        "outer click must not change inner root value"
    )


def test_nested_inner_group_remains_independently_switchable_with_guard() -> None:
    nested = _build_nested_tree(default_inner="profile")
    dom = _dom_tree(nested)
    _simulate_mount(dom)
    outer_settings = _find_by_id(dom, "outer-settings")
    assert outer_settings is not None
    _simulate_click(dom, outer_settings, with_guard=True)
    inner_sec = _find_by_id(dom, "inner-sec")
    inner_prof = _find_by_id(dom, "inner-prof")
    assert inner_sec is not None
    assert inner_prof is not None
    assert inner_prof["active"] == "true"
    _simulate_click(dom, inner_sec, with_guard=True)
    assert inner_sec["active"] == "true"
    assert inner_prof["active"] == "false"
    outer_root = _closest(outer_settings, "tabs", _index_parents(dom))
    assert outer_root is not None
    assert outer_root["value"] == "settings"


def test_flat_demo_guard_is_noop_for_outer_only_group() -> None:
    import importlib

    for label, (module_path, fn_name) in DEMO_MODULES.items():
        mod = importlib.import_module(module_path)
        comp = getattr(mod, fn_name)()
        dom = _dom_tree(comp)
        _simulate_mount(dom)
        triggers = _all_triggers(dom)
        # Demo triggers are not given explicit ids; snapshot per-trigger state by
        # the trigger's rendered data-value (unique within a flat tabs group)
        # rather than by id (which would be None for every demo trigger and
        # collapse the snapshot to a single key).
        values = [t["value"] for t in triggers]
        assert len(set(values)) == len(values), (
            f"{label}: demo triggers must have distinct values within one group"
        )
        for trigger in triggers:
            _simulate_click(dom, trigger, with_guard=True)
            expected = {
                t["value"]: ("true" if t["value"] == trigger["value"] else "false")
                for t in triggers
            }
            snapshot_after = {t["value"]: t["active"] for t in triggers}
            assert snapshot_after == expected, (
                f"{label}: click {trigger['value']} did not yield a single active trigger"
            )
            assert trigger["active"] == "true"
