from reflex import Component

from components.ui.button import button


def button_ghost() -> Component:
    return button("Ghost", variant="ghost")
