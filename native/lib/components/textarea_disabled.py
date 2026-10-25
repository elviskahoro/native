from reflex.components.component import Component

from components.ui.field import field
from components.ui.textarea import textarea


def textarea_disabled() -> Component:
    return field.root(
        field.label(
            "Message",
            html_for="textarea-disabled",
        ),
        textarea(
            id="textarea-disabled",
            placeholder="Type your message here.",
            disabled=True,
        ),
        **{"data-disabled": True},
        class_name="max-w-xs",
    )
