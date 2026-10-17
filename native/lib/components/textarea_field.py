from reflex.components.component import Component

from components.ui.field import field
from components.ui.textarea import textarea


def textarea_field() -> Component:
    return field.root(
        field.label(
            "Message",
            html_for="textarea-message",
        ),
        field.description(
            "Enter your message below.",
        ),
        textarea(
            id="textarea-message",
            placeholder="Type your message here.",
        ),
        class_name="max-w-xs",
    )
