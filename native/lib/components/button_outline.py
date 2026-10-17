from reflex.components.component import Component

from components.ui.button import button


def button_outline() -> Component:
    return button("Outline", variant="outline")
