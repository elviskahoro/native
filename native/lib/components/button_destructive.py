from reflex.components.component import Component

from components.ui.button import button


def button_destructive() -> Component:
    return button("Destructive", variant="destructive")
