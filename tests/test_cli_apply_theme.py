from cli.main import (
    THEME_END_SENTINEL,
    THEME_START_SENTINEL,
    find_legacy_theme_pair,
    splice_theme_block,
)

THEME = ":root {\n  --a: 1;\n}\n\n.dark {\n  --a: 2;\n}"


def test_empty_file_gets_managed_block():
    out = splice_theme_block("", THEME)
    assert out.startswith(THEME_START_SENTINEL)
    assert THEME_END_SENTINEL in out


def test_reapply_preserves_prefix_and_suffix():
    first = '@import "x.css";\n\n' + splice_theme_block('', THEME)
    first += "\n.custom { color: red; }\n"
    out = splice_theme_block(first, THEME.replace("1", "9"))
    assert out.startswith('@import "x.css";')
    assert ".custom { color: red; }" in out
    assert out.count(THEME_START_SENTINEL) == 1
    assert "--a: 9" in out and "--a: 1" not in out


def test_legacy_pair_replaced_prefix_kept():
    legacy = "html { margin: 0; }\n\n" + THEME + "\n\n.u { x: y; }\n"
    out = splice_theme_block(legacy, THEME.replace("1", "9"))
    assert "html { margin: 0; }" in out and ".u { x: y; }" in out
    assert "--a: 1" not in out


def test_user_root_survives():
    css = ":root { --mine: 1; }\n"
    out = splice_theme_block(css, THEME)
    assert ":root { --mine: 1; }" in out


def test_nested_root_not_matched():
    css = "@media (x) {\n  :root {\n    --a: 1;\n  }\n  .dark {\n    --a: 2;\n  }\n}\n"
    assert find_legacy_theme_pair(css.splitlines()) is None
    out = splice_theme_block(css, THEME)
    assert out.count("{") == out.count("}")
    assert "@media (x)" in out


def test_fallback_keeps_imports_first():
    css = '@charset "utf-8";\n@import url("a.css");\nbody { margin: 0; }\n'
    out = splice_theme_block(css, THEME)
    assert out.index("@import") < out.index(THEME_START_SENTINEL)
    assert out.index(THEME_END_SENTINEL) < out.index("body {")
