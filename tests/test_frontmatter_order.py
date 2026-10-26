import pytest

from native.core.utils import parse_frontmatter


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("5", 5), ("0", 0), ("-1", -1), ("'7'", 7)],
)
def test_order_is_coerced_to_int(raw: str, expected: int) -> None:
    metadata, _ = parse_frontmatter(f"---\norder: {raw}\n---\nbody")
    assert metadata["order"] == expected


@pytest.mark.parametrize("raw", ["", "abc", "5.0"])
def test_invalid_order_is_omitted(raw: str) -> None:
    metadata, _ = parse_frontmatter(f"---\ntitle: x\norder: {raw}\n---\nbody")
    assert "order" not in metadata
    assert metadata["title"] == "x"


def test_mixed_orders_sort_without_type_error() -> None:
    docs = ["order: 2", "order: abc", "order: 1", "title: none"]
    orders = [
        parse_frontmatter(f"---\n{d}\n---\n")[0].get("order", 999) for d in docs
    ]
    assert sorted(orders) == [1, 2, 999, 999]
