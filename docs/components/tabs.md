---
title: "Tabs"
description: "A set of layered sections of content—known as tab panels—that are displayed one at a time."
order: 0
---

--INTRO([Tabs, A set of layered sections of content—known as tab panels—that are displayed one at a time.])--

--USAGE(tabs)--

--SOURCE(tabs)--

# Examples

# Basic

--DEMO(tabs_basic)--

# Line

Use the `variant="line"` prop on `tabs.list` for a line style.

--DEMO(tabs_line)--

# Vertical

Use `orientation="vertical"` for vertical tabs.

--DEMO(tabs_vertical)--

# Disabled

Use `disabled=True` to disable a tab.

--DEMO(tabs_disabled)--

# Icons

--DEMO(tabs_icons)--

# API Reference

## tabs.root

The main container component that initializes your tab instance, holds the active state configuration on the client, and dictates the layout orientation.

```python
tabs.root(
    tabs.list(
        tabs.trigger("Overview", value="overview"),
        tabs.trigger("Analytics", value="analytics"),
    ),
    tabs.content(
        "Overview panel data",
        value="overview"
    ),
    default_value="overview",
)
```

| Prop            | Type                                | Default        |
| --------------- | ----------------------------------- | -------------- |
| `default_value` | `str`                               | `""`           |
| `orientation`   | `Literal["horizontal", "vertical"]` | `"horizontal"` |
| `class_name`    | `str`                               | `""`           |

## tabs.list

Groups the trigger navigation buttons together and controls the visual theme style.

```python
tabs.list(
    tabs.trigger("Tab 1", value="tab1"),
    tabs.trigger("Tab 2", value="tab2"),
    variant="line",
)
```

| Prop         | Type                         | Default     |
| ------------ | ---------------------------- | ----------- |
| `variant`    | `Literal["default", "line"]` | `"default"` |
| `class_name` | `str`                        | `""`        |

## tabs.trigger

The clickable button elements used to switch active states. Active-tab highlight is driven by a single delegated click listener that `tabs.root` attaches on mount, so user-supplied `on_click` / `on_mount` handlers are passed through untouched.

```python
tabs.trigger(
    "Analytics",
    value="analytics",
    on_click=rx.console_log("Switched tabs!")
)
```

| Prop         | Type                                      | Default               |
| ------------ | ----------------------------------------- | --------------------- |
| `value`      | `str`                                     | _Required_            |
| `class_name` | `str`                                     | `""`                  |
| `id`         | `str`                                     | _None_                |
| `disabled`   | `bool`                                    | `False`               |
| `on_click`   | `Union[EventHandler, list[EventHandler]]` | `None`                |
| `on_mount`   | `Union[EventHandler, list[EventHandler]]` | `None`                |

## tabs.content

The structural panel containing content mapped to a specific tab trigger value. Visibility is driven by the same delegated click/mount listener that `tabs.root` attaches: it compares the root's rendered `data-value` with the panel's rendered `data-value` and sets `data-active`, with the panel's static `hidden` default overridden by the static `data-[active=true]:block` variant.

```python
tabs.content(
    "Your dashboard analytics modules go here.",
    value="analytics",
)
```

| Prop         | Type  | Default    |
| ------------ | ----- | ---------- |
| `value`      | `str` | _Required_ |
| `class_name` | `str` | `""`       |
