from reflex.components.component import Component

from components.ui.button import button


def button_link() -> Component:
    return button("Link", variant="link")
