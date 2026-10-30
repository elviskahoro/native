"""Regression coverage for the ``FieldSeparator`` crash when children are passed.

``FieldSeparator.create`` in ``components/ui/field.py`` built the overlaid
content span by directly instantiating the element class
(``elements.Span(*children, ...)``) instead of calling ``elements.Span.create``
(the ``.create`` classmethod). In the pinned ``reflex==0.10.0`` dependency,
``Component.__init__`` accepts only keyword arguments, so passing positional
children raised ``TypeError: Component.__init__() takes 1 positional argument
but 2 were given`` — crashing the documented ``field.separator("Or continue
with")`` usage while the childless ``field.separator()`` form succeeded
(because the broken branch is gated behind ``if children``).

These tests pin the contracts the fix restored so the direct-instantiation
outlier cannot slip back in:

1. ``field.separator("...")`` forwards children into a nested ``<span>`` built
   via ``.create`` (a real ``elements.Span`` carrying ``data-slot`` and the
   documented classes).
2. ``field.separator()`` (no children) keeps its contentless shape — no content
   span is synthesized.
3. The divider rule is always rendered as the first child, with or without
   content, so the visual divider is never lost.

See the bug report ("Field separator with label text crashes at render time").
"""

from __future__ import annotations

from typing import Any

from reflex_components_core.el import elements

from components.ui.field import field


def _content_span(separator: Any) -> elements.Span:
    """Return the overlaid content ``<span>`` child of a built separator."""
    spans = [
        c
        for c in separator.children
        if (getattr(c, "custom_attrs", None) or {}).get("data-slot")
        == "field-separator-content"
    ]
    assert spans, (
        "Separator with content must contain a child carrying "
        f"data-slot='field-separator-content'; got {list(separator.children)!r}"
    )
    assert len(spans) == 1, (
        f"Exactly one content span expected; got {len(spans)}: {spans!r}"
    )
    span = spans[0]
    # Asserting ``elements.Span`` here pins the ``.create`` classmethod path:
    # the buggy form ``elements.Span(*children, ...)`` raises ``TypeError``
    # before ever producing an instance, so this would fail first.
    assert isinstance(span, elements.Span), (
        f"Content slot must be an elements.Span; "
        f"got {type(span).__module__}.{type(span).__name__}"
    )
    return span


def _divider_rule(separator: Any) -> elements.Div:
    """Return the divider rule (the sibling ``separator`` element)."""
    rules = [
        c
        for c in separator.children
        if (getattr(c, "custom_attrs", None) or {}).get("data-slot") == "separator"
    ]
    assert rules, (
        f"Separator must contain the divider rule (data-slot='separator'); "
        f"got {list(separator.children)!r}"
    )
    assert len(rules) == 1, (
        f"Exactly one divider rule expected; got {len(rules)}: {rules!r}"
    )
    return rules[0]


def _bare_text(bare: Any) -> str:
    """Extract the literal string carried by a reflex ``Bare`` child."""
    value = getattr(getattr(bare, "contents", None), "_var_value", None)
    assert value is not None, f"Bare child has no literal contents; got {bare!r}"
    return str(value)


def test_separator_with_children_forwards_into_content_span() -> None:
    comp = field.separator("or")
    assert (comp.custom_attrs or {}).get("data-slot") == "field-separator"
    assert (comp.custom_attrs or {}).get("data-content") == "true"

    span = _content_span(comp)
    assert (span.custom_attrs or {}).get("data-slot") == "field-separator-content"
    rendered = str(getattr(span, "class_name", ""))
    for expected in (
        "relative",
        "mx-auto",
        "block",
        "w-fit",
        "bg-background",
        "px-2",
        "text-muted-foreground",
    ):
        assert expected in rendered, (
            f"Content span must keep the documented class {expected!r}; "
            f"got {rendered!r}"
        )

    bare_children = [c for c in span.children if type(c).__name__ == "Bare"]
    assert len(bare_children) == 1, (
        f"Expected the forwarded child in the content span; got {list(span.children)!r}"
    )
    assert _bare_text(bare_children[0]) == "or"


def test_separator_without_children_has_no_content_span() -> None:
    comp = field.separator()
    assert (comp.custom_attrs or {}).get("data-content") == "false"
    spans = [
        c
        for c in comp.children
        if (getattr(c, "custom_attrs", None) or {}).get("data-slot")
        == "field-separator-content"
    ]
    assert spans == [], (
        f"Childless separator must not synthesize an empty content span; got {spans!r}"
    )


def test_separator_always_renders_divider_rule_first() -> None:
    with_content = field.separator("or")
    assert with_content.children[0] is _divider_rule(with_content), (
        "The divider rule must be the first child so the visual divider renders "
        "behind the overlaid text."
    )

    without_content = field.separator()
    assert len(without_content.children) == 1
    assert without_content.children[0] is _divider_rule(without_content)
