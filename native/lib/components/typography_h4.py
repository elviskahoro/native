import reflex as rx


def header_4() -> rx.Component:
    return rx.el.h4(
        "Far over the misty mountains cold.",
        class_name="scroll-m-20 text-xl font-semibold tracking-tight",
    )
