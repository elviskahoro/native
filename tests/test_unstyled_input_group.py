"""``unstyled`` regression tests for InputGroup components bypassing set_class_name."""

from __future__ import annotations

import pytest
from reflex.components.component import Component

from components.ui.input_group import (
    ClassNames,
    InputGroupButton,
    InputGroupInput,
    InputGroupTextarea,
)

CASES = [
    (InputGroupButton, "shadow-none"),
    (InputGroupInput, ClassNames.CONTROL_INPUT.split()[0]),
    (InputGroupTextarea, ClassNames.CONTROL_TEXTAREA.split()[0]),
]


def _class_name(component: Component) -> str:
    return str(getattr(component, "class_name", ""))


@pytest.mark.parametrize(("cls", "default"), CASES)
def test_defaults_merged(cls: type, default: str) -> None:
    out = _class_name(cls.create(class_name="user-x"))
    assert default in out
    assert "user-x" in out


@pytest.mark.parametrize(("cls", "default"), CASES)
def test_unstyled_strips_defaults(cls: type, default: str) -> None:
    out = _class_name(cls.create(class_name="user-x", unstyled=True))
    assert "user-x" in out
    assert default not in out
