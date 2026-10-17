from reflex import Component

from components.ui.button import button


def button_secondary() -> Component:
    return button("Secondary", variant="secondary")
