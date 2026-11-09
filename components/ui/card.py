"""The card component."""

from reflex.components.component import Component, ComponentNamespace
from reflex.vars.base import Var
from reflex_components_core.el import Div

from ..core.core import CoreComponent, PropValue


class ClassNames:
    """Class names."""

    ROOT = (
        "group/card flex flex-col gap-(--card-gap) overflow-hidden rounded-xl bg-card "
        "py-(--card-padding) text-sm text-card-foreground ring-1 ring-foreground/10 "
        "has-data-[slot=card-footer]:pb-0 "
        "has-[>img:first-child]:pt-0 "
        "*:[img:first-child]:rounded-t-xl *:[img:last-child]:rounded-b-xl"
    )

    HEADER = (
        "group/card-header @container/card-header grid auto-rows-min items-start gap-1 "
        "rounded-t-xl px-(--card-padding) "
        "has-data-[slot=card-action]:grid-cols-[1fr_auto] "
        "has-data-[slot=card-description]:grid-rows-[auto_auto] "
        "[.border-b]:pb-(--card-padding)"
    )

    TITLE = (
        "cn-font-heading text-base leading-snug font-medium "
        "group-data-[size=sm]/card:text-sm"
    )

    DESCRIPTION = "text-sm text-muted-foreground"

    ACTION = "col-start-2 row-span-2 row-start-1 self-start justify-self-end"

    CONTENT = "px-(--card-padding)"

    FOOTER = (
        "flex items-center rounded-b-xl border-t border-input "
        "bg-muted/50 p-(--card-padding)"
    )


class CardRoot(Div, CoreComponent):
    """Card root."""

    size: Var[str]

    @classmethod
    def create(cls, *children: PropValue, **props: PropValue) -> Component:
        """Create the card root."""
        props["data-slot"] = "card"
        if "size" in props:
            props["data-size"] = props.pop("size")
        cls.set_class_name(ClassNames.ROOT, props)
        return super().create(*children, **props)


class CardHeader(Div, CoreComponent):
    """Card header."""

    @classmethod
    def create(cls, *children: PropValue, **props: PropValue) -> Component:
        """Create the card header."""
        props["data-slot"] = "card-header"
        cls.set_class_name(ClassNames.HEADER, props)
        return super().create(*children, **props)


class CardTitle(Div, CoreComponent):
    """Card title."""

    @classmethod
    def create(cls, *children: PropValue, **props: PropValue) -> Component:
        """Create the card title."""
        props["data-slot"] = "card-title"
        cls.set_class_name(ClassNames.TITLE, props)
        return super().create(*children, **props)


class CardDescription(Div, CoreComponent):
    """Card description."""

    @classmethod
    def create(cls, *children: PropValue, **props: PropValue) -> Component:
        """Create the card description."""
        props["data-slot"] = "card-description"
        cls.set_class_name(ClassNames.DESCRIPTION, props)
        return super().create(*children, **props)


class CardAction(Div, CoreComponent):
    """Card action."""

    @classmethod
    def create(cls, *children: PropValue, **props: PropValue) -> Component:
        """Create the card action."""
        props["data-slot"] = "card-action"
        cls.set_class_name(ClassNames.ACTION, props)
        return super().create(*children, **props)


class CardContent(Div, CoreComponent):
    """Card content."""

    @classmethod
    def create(cls, *children: PropValue, **props: PropValue) -> Component:
        """Create the card content."""
        props["data-slot"] = "card-content"
        cls.set_class_name(ClassNames.CONTENT, props)
        return super().create(*children, **props)


class CardFooter(Div, CoreComponent):
    """Card footer."""

    @classmethod
    def create(cls, *children: PropValue, **props: PropValue) -> Component:
        """Create the card footer."""
        props["data-slot"] = "card-footer"
        cls.set_class_name(ClassNames.FOOTER, props)
        return super().create(*children, **props)


class Card(ComponentNamespace):
    """Card."""

    root = staticmethod(CardRoot.create)
    header = staticmethod(CardHeader.create)
    title = staticmethod(CardTitle.create)
    description = staticmethod(CardDescription.create)
    action = staticmethod(CardAction.create)
    content = staticmethod(CardContent.create)
    footer = staticmethod(CardFooter.create)
    class_names = ClassNames


card = Card()
