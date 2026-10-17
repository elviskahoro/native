import functools
from collections.abc import Callable
from typing import Any

from reflex.components.component import Component
from reflex_components_core.el import div


def masonry_card(
    func: Callable[..., Any] | None = None,
    *,
    label: str = "General",
) -> Callable[..., Component]:
    if func is None:
        return functools.partial(masonry_card, label=label)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Component:
        inner_component = func(*args, **kwargs)

        return div(
            inner_component,
            class_name="break-inside-avoid w-full [&>*]:shadow-lg [&>*]:border-t-[0.85px] [&>*]:border-input/80",
        )

    return wrapper
