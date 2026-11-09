"""The message component."""

from typing import Literal

import reflex as rx
from reflex.components.component import ComponentNamespace

from ..core.core import CoreComponent, PropValue

MessageAlign = Literal["start", "end"]


class ClassNames:
    """Class names."""

    GROUP = "flex min-w-0 flex-col gap-2"

    ROOT = (
        "group/message relative flex w-full min-w-0 gap-2 text-sm "
        "data-[align=end]:flex-row-reverse"
    )

    AVATAR = (
        "flex w-fit min-w-8 shrink-0 items-center justify-center "
        "self-end overflow-hidden rounded-full bg-muted "
        "group-has-data-[slot=message-footer]/message:-translate-y-8"
    )

    CONTENT = (
        "flex w-full min-w-0 flex-col gap-2.5 break-words "
        "group-data-[align=end]/message:*:data-slot:self-end"
    )

    HEADER = (
        "flex max-w-full min-w-0 items-center px-3 text-xs font-medium "
        "text-muted-foreground "
        "group-has-data-[variant=ghost]/message:px-0"
    )

    FOOTER = (
        "flex max-w-full min-w-0 items-center px-3 text-xs font-medium "
        "text-muted-foreground "
        "group-has-data-[variant=ghost]/message:px-0 "
        "group-data-[align=end]/message:justify-end"
    )


class NativeMessageGroup(CoreComponent):
    """Native message group."""

    @classmethod
    def create(cls, *children: PropValue, **props: PropValue) -> rx.Component:
        """Create the native message group."""
        props["data-slot"] = "message-group"
        cls.set_class_name(ClassNames.GROUP, props)
        return rx.el.div(*children, **props)


class NativeMessageRoot(CoreComponent):
    """Native message root."""

    @classmethod
    def create(cls, *children: PropValue, **props: PropValue) -> rx.Component:
        """Create the native message root."""
        align = props.pop("align", "start")
        props["data-slot"] = "message"
        props["data-align"] = align
        cls.set_class_name(ClassNames.ROOT, props)
        return rx.el.div(*children, **props)


class NativeMessageAvatar(CoreComponent):
    """Native message avatar."""

    @classmethod
    def create(cls, *children: PropValue, **props: PropValue) -> rx.Component:
        """Create the native message avatar."""
        props["data-slot"] = "message-avatar"
        cls.set_class_name(ClassNames.AVATAR, props)
        return rx.el.div(*children, **props)


class NativeMessageContent(CoreComponent):
    """Native message content."""

    @classmethod
    def create(cls, *children: PropValue, **props: PropValue) -> rx.Component:
        """Create the native message content."""
        props["data-slot"] = "message-content"
        cls.set_class_name(ClassNames.CONTENT, props)
        return rx.el.div(*children, **props)


class NativeMessageHeader(CoreComponent):
    """Native message header."""

    @classmethod
    def create(cls, *children: PropValue, **props: PropValue) -> rx.Component:
        """Create the native message header."""
        props["data-slot"] = "message-header"
        cls.set_class_name(ClassNames.HEADER, props)
        return rx.el.div(*children, **props)


class NativeMessageFooter(CoreComponent):
    """Native message footer."""

    @classmethod
    def create(cls, *children: PropValue, **props: PropValue) -> rx.Component:
        """Create the native message footer."""
        props["data-slot"] = "message-footer"
        cls.set_class_name(ClassNames.FOOTER, props)
        return rx.el.div(*children, **props)


class Message(ComponentNamespace):
    """Message."""

    group = staticmethod(NativeMessageGroup.create)
    root = staticmethod(NativeMessageRoot.create)
    avatar = staticmethod(NativeMessageAvatar.create)
    content = staticmethod(NativeMessageContent.create)
    header = staticmethod(NativeMessageHeader.create)
    footer = staticmethod(NativeMessageFooter.create)
    class_names = ClassNames


message = Message()
