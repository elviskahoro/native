"""Regression coverage for chart tooltip color swatches.

Recharts 3.10.1 sorts tooltip rows alphabetically by data key
(``Tooltip`` resolves ``defaultTooltipProps.itemSorter = 'name'`` and
``DefaultTooltipContent`` runs ``lodashLikeSortBy`` before mapping rows).
``chart_tooltip_content`` used to paint each row's ``::before`` swatch by DOM
position via ``nth-child(i)`` paired with ``--chart-{chart_colors[i-1]}``, which
only matched when the alphabetical row order happened to equal the
``chart_colors`` order. In every chart whose alphabetically-first series is not
the ``--chart-1`` series the swatch was paired with the wrong series' color
(e.g. ``bar_chart_03`` rendered Cycling's value with Running's swatch).

The fix stops mapping swatches by DOM position altogether. Recharts already
inlines each tooltip row's own series color as ``style="color: entry.color"``
on the ``<li class="recharts-tooltip-item">`` (Bar -> ``fill``, Line ->
``stroke``, Area -> ``getLegendItemColor(stroke, fill)``). ``chart_tooltip`` no
longer pins ``item_style.color`` to ``currentColor`` (which previously
overrode ``entry.color``), and the swatch now uses ``bg-current`` so each row
picks up its own series color regardless of how recharts sorts the rows. The
tooltip text stays muted-foreground / foreground as before via explicit
overrides on the name / value / unit / separator spans.

These tests pin the contracts the fix restored; see the chart tooltip bug and
``components/chart/chart_tooltip.py``.
"""

from typing import Any

import reflex as rx

from components.chart.chart_tooltip import chart_tooltip, chart_tooltip_content


def _props(comp: rx.Component) -> list[str]:
    rendered = comp.render()
    return rendered["props"]


def _prop(comp: rx.Component, prefix: str) -> str:
    matches = [p for p in _props(comp) if p.startswith(prefix)]
    assert matches, f"no prop starting with {prefix!r}"
    return matches[0]


def test_chart_tooltip_does_not_pin_item_color() -> None:
    """item_style must not set ``color`` so recharts applies ``entry.color``."""
    item_style = _prop(chart_tooltip(), "itemStyle")
    assert '"color"' not in item_style, (
        "item_style must not override color; recharts inlines each row's own "
        "series color (entry.color) on the <li>, which the swatch reads via "
        "currentColor"
    )


def test_chart_tooltip_item_style_overrides_still_merge() -> None:
    merged = _prop(
        chart_tooltip(item_style={"display": "grid", "color": "rgb(0 0 0)"}),
        "itemStyle",
    )
    assert '["display"] : "grid"' in merged
    assert '["color"] : "rgb(0 0 0)"' in merged


def test_square_swatch_is_order_independent() -> None:
    result = chart_tooltip_content([1, 2], "square")
    assert "[&_.recharts-tooltip-item:before]:!bg-current" in result
    assert "[&_.recharts-tooltip-item:before]:!h-3" in result
    assert "[&_.recharts-tooltip-item:before]:!rounded-[3px]" in result


def test_line_swatch_is_order_independent() -> None:
    result = chart_tooltip_content([1, 2, 3], "line")
    assert "[&_.recharts-tooltip-item:before]:!bg-current" in result
    assert "[&_.recharts-tooltip-item:before]:!h-0.5" in result
    assert "[&_.recharts-tooltip-item:before]:!rounded-full" in result


def test_no_positional_nth_child_mapping_remains() -> None:
    """The buggy positional nth-child + var(--chart-n) mapping must be gone."""
    for swatch in ("square", "line"):
        result = chart_tooltip_content([1, 2, 3], swatch)  # type: ignore[arg-type]
        assert "nth-child" not in result, (
            f"tooltip {swatch} swatch must not map by DOM position; got nth-child"
        )
        assert "var(--chart-" not in result, (
            f"tooltip {swatch} swatch must not reference --chart-n by position"
        )


def test_border_swatch_uses_first_chart_color_for_label() -> None:
    result = chart_tooltip_content([3, 2], "border")
    assert "[&_.recharts-tooltip-label]:!border-[var(--chart-3)]" in result
    assert "recharts-tooltip-item:before" not in result
    assert "var(--chart-3)" in result


def test_tooltip_text_colors_preserve_design() -> None:
    """Name stays muted; value/unit/separator stay foreground (not series-colored)."""
    result = chart_tooltip_content([1, 2], "square")
    assert "[&_.recharts-tooltip-item-name]:!text-muted-foreground" in result
    assert "[&_.recharts-tooltip-item-value]:!text-foreground" in result
    assert "[&_.recharts-tooltip-item-unit]:!text-foreground" in result
    assert "[&_.recharts-tooltip-item-separator]:!text-foreground" in result


_AFFECTED_BLOCKS: list[tuple[str, str]] = [
    ("native.lib.blocks.bar_chart_03", "bar_chart_03"),
    ("native.lib.blocks.bar_chart_01", "bar_chart_01"),
    ("native.lib.blocks.line_chart_02", "line_chart_02"),
    ("native.lib.blocks.line_chart_03", "line_chart_03"),
    ("native.lib.blocks.line_chart_04", "line_chart_04"),
    ("native.lib.charts.area.v6", "area_chart_with_legend"),
    ("native.lib.charts.area.v7", "area_chart_with_axis"),
]


def _import_callable(module: str, attr: str) -> Any:
    mod = __import__(module, fromlist=[attr])
    return getattr(mod, attr)


def _chart_container_class_name(comp: rx.Component) -> str:
    for prop in comp.render()["props"]:
        if isinstance(prop, str) and prop.startswith("className"):
            return prop
    return ""


def test_affected_blocks_use_order_independent_swatch() -> None:
    """Every previously-affected block renders bg-current and no nth-child."""
    for module, attr in _AFFECTED_BLOCKS:
        comp = _import_callable(module, attr)()
        class_name = _chart_container_class_name(comp)
        assert "bg-current" in class_name, (
            f"{module}.{attr} tooltip swatch is not order-independent "
            "(missing bg-current)"
        )
        assert "nth-child" not in class_name, (
            f"{module}.{attr} still maps swatches by DOM position (nth-child)"
        )


def test_area_v5_swatch_is_order_independent() -> None:
    """area/v5 declares mobile(chart-2) before desktop(chart-1).

    A pure ``itemSorter=null`` fix would regress it (its chart_colors=[1,2]
    matches alphabetical order, not declaration order). The order-independent
    swatch keeps it correct.
    """
    from native.lib.charts.area.v5 import area_chart_dynamic

    class_name = _chart_container_class_name(area_chart_dynamic())
    assert "bg-current" in class_name
    assert "nth-child" not in class_name
