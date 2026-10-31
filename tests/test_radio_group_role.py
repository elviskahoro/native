"""Regression tests for ``radio_group.root``'s ARIA ``role`` attribute.

``radio_group.root`` renders a native ``<fieldset>`` and is documented
(``docs/components/radio_group.md``) to render ``<fieldset role="radiogroup">``
with ``role`` defaulting to ``"radiogroup"``. Because Reflex's bare ``Fieldset``
element (``Element``-derived, not ``BaseHTML``) declares no ``role`` prop,
passing ``role="radiogroup"`` as a normal keyword arg is silently folded into
Emotion's ``css``/``style`` object — an invalid CSS property the browser
discards — so the rendered ``<fieldset>`` carries no ``role`` attribute at all,
breaking the documented ARIA radiogroup semantics for assistive technology. The
failure is invisible in normal use (the component still renders), so these
tests guard the routing: ``role`` reaches the DOM as an attribute (and not as a
stray Emotion CSS rule), it is overridable via ``custom_attrs`` and defaults
back to ``"radiogroup"`` otherwise, and the shared ``custom_attrs`` channel
does not clobber ``data-slot``.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable

import pytest
import reflex as rx

from components.ui.radio_group import radio_group


def _literal(v: object) -> object:
    """Return the underlying literal of a Reflex ``Var`` (or the value itself
    for plain ``str``\\s), so assertions do not depend on the wrapper type."""
    return getattr(v, "_var_value", v)


def _root_custom_attrs(comp: rx.Component) -> dict[str, object]:
    return dict(getattr(comp, "custom_attrs", {}) or {})


def _rendered_props(comp: rx.Component) -> list[str]:
    """The flat list of ``render()["props"]`` entries Reflex serializes for the
    element (the same channel ``tests/test_dialog.py`` and ``tests/test_menu.py``
    inspect). A real DOM attribute appears here as ``"key":value`` while an
    attribute folded into Emotion css appears as a ``css:{ ... }`` entry."""
    props = comp.render()["props"]
    return list(props) if isinstance(props, Iterable) else []


def _has_prop_entry(props: list[str], key: str) -> bool:
    """True iff a rendered prop entry is emitted for ``key``. The fieldset
    serializes some keys quoted (``"data-slot"``) and some bare (``role``),
    so match either leading form."""
    prefixes = (f"{key}:", f'"{key}":')
    return any(p.startswith(prefixes) for p in props if isinstance(p, str))


def _prop_entry(props: list[str], key: str) -> str | None:
    for p in props:
        if not isinstance(p, str):
            continue
        if p.startswith((f"{key}:", f'"{key}":')):
            return p
    return None


def test_root_emits_radiogroup_role_as_dom_attribute() -> None:
    """``role="radiogroup"`` must be emitted as a real DOM attribute on the
    ``<fieldset>`` (present in the rendered props), not folded into Emotion's
    ``css`` object. Before the fix the only rendered prop entry carrying the
    role was ``css:({ ["role"] : "radiogroup" })`` and the ``<fieldset>`` had no
    ``role`` attribute at all — the documented ARIA radiogroup semantics were
    silently lost because ``Fieldset`` declares no ``role`` prop."""
    root = radio_group.root(radio_group.item(name="plan", value="free"))
    props = _rendered_props(root)
    assert _has_prop_entry(props, "role"), (
        f"role must be a rendered DOM attribute; got props {props}"
    )
    assert "radiogroup" in (_prop_entry(props, "role") or ""), (
        f"emitted role entry must carry the radiogroup value; got {props}"
    )


def test_root_role_not_swallowed_into_emotion_css() -> None:
    """No Emotion ``css`` entry may survive on the rendered props. The pre-fix
    failure mode was ``role`` appearing as a key of the rendered ``css`` object
    (an invalid CSS rule the browser discards); before the fix
    ``_render().props.keys() == ['className', 'css', 'data-slot']`` with no
    ``role`` attribute."""
    root = radio_group.root(radio_group.item(name="plan", value="free"))
    props = _rendered_props(root)
    assert not _has_prop_entry(props, "css"), (
        f"role leaked into a rendered Emotion css entry: {props}"
    )
    assert _prop_entry(props, "css") is None


def test_root_role_overridable_via_custom_attrs() -> None:
    """A caller may override the default ``role`` by passing ``custom_attrs``
    with a ``role`` key; that value must win on the rendered DOM attribute
    (the fix uses ``dict.setdefault``). Matches the documented ``role`` prop
    being settable rather than hard-coded by the component."""
    root = radio_group.root(
        radio_group.item(name="plan", value="free"),
        custom_attrs={"role": "group"},
    )
    assert _literal(_root_custom_attrs(root).get("role")) == "group"
    assert "group" in (_prop_entry(_rendered_props(root), "role") or "")


def test_root_role_overridable_via_kwarg() -> None:
    """A caller may override the default ``role`` by passing the ``role``
    keyword argument directly (the API table at ``docs/components/radio_group.md``
    lists ``role`` as a settable prop, forwarding extra HTML props to the
    ``<fieldset>``). The kwarg must reach the DOM as the rendered ``role``
    attribute instead of being silently folded into Emotion's ``css`` object
    (the pre-fix failure mode for the override path — ``Fieldset`` declares no
    ``role`` prop, so the kwarg leaked into a stray ``css`` entry while the
    default ``"radiogroup"`` won on the DOM)."""
    root = radio_group.root(
        radio_group.item(name="plan", value="free"),
        role="group",
    )
    assert _literal(_root_custom_attrs(root).get("role")) == "group"
    props = _rendered_props(root)
    assert "group" in (_prop_entry(props, "role") or ""), (
        f"role kwarg must reach the DOM; got {props}"
    )
    assert not _has_prop_entry(props, "css"), (
        f"role kwarg leaked into a rendered Emotion css entry: {props}"
    )


def test_root_custom_attrs_without_role_keeps_default_role() -> None:
    """Passing unrelated ``custom_attrs`` (no ``role`` key) must not disable the
    default ``role="radiogroup"``; both the caller's attributes and the
    default role must coexist on the DOM (the ``setdefault`` interaction)."""
    root = radio_group.root(
        radio_group.item(name="plan", value="free"),
        custom_attrs={"aria-label": "Plan"},
    )
    attrs = _root_custom_attrs(root)
    assert _literal(attrs.get("role")) == "radiogroup"
    assert _literal(attrs.get("aria-label")) == "Plan"


def test_root_data_slot_still_emitted_as_custom_attr() -> None:
    """Regression: ``data-slot="radio-group"`` must still be emitted as a DOM
    attribute. It shares the ``custom_attrs`` channel that the role fix now
    writes into, so guard against the fix clobbering it."""
    root = radio_group.root(radio_group.item(name="plan", value="free"))
    props = _rendered_props(root)
    assert _has_prop_entry(props, "data-slot"), f"data-slot missing from {props}"
    assert _literal(_root_custom_attrs(root).get("data-slot")) == "radio-group"


DEMO_MODULES = [
    ("native.lib.components.radio_group_description", "radio_group_description"),
    ("native.lib.components.radio_group_choice_card", "radio_group_choice_card"),
    ("native.lib.components.radio_group_fieldset", "radio_group_fieldset"),
    ("native.lib.components.radio_group_disabled", "radio_group_disabled"),
    ("native.lib.components.radio_group_invalid", "radio_group_invalid"),
]


@pytest.mark.parametrize(
    ("module_path", "fn_name"),
    DEMO_MODULES,
    ids=[m[1] for m in DEMO_MODULES],
)  # pyright: ignore[reportUntypedFunctionDecorator]
def test_in_repo_demos_build(module_path: str, fn_name: str) -> None:
    """Every shipped radio-group demo must still construct cleanly after the
    role fix. The ``radio_group_fieldset`` and ``radio_group_disabled`` demos
    pass ``disabled=True``/fieldset semantics that previously masked the missing
    ``role`` and must not regress now that ``role`` reaches the DOM."""
    mod = importlib.import_module(module_path)
    comp = getattr(mod, fn_name)()
    assert isinstance(comp, rx.Component), (
        f"{fn_name} did not return an rx.Component: {type(comp).__name__}"
    )
