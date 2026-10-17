import reflex as rx

from components.ui.tabs import tabs


def tabs_vertical() -> rx.Component:
    return rx.el.div(
        tabs.root(
            tabs.list(
                tabs.trigger("Account", value="account"),
                tabs.trigger("Password", value="password"),
                tabs.trigger("Notifications", value="notifications"),
            ),
            default_value="account",
            orientation="vertical",
        ),
        class_name="flex justify-center text-sm",
    )
