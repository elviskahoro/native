from reflex import Component

from components.ui.textarea import textarea


def textarea_basic_demo() -> Component:
    return textarea(placeholder="Type your message here.", class_name="max-w-xs")
