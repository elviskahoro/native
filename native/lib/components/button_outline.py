from reflex import Component

from components.ui.button import button


def button_outline() -> Component:
    return button("Outline", variant="outline")
