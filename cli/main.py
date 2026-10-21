import argparse
import ast
import json
import re
import shutil
import sys
from pathlib import Path

from cli.preset_codec import decode_seed
from cli.scrollbar_css import SCROLLBAR_CSS
from cli.shimmer_css import SHIMMER_CSS
from cli.tailwind_config import TAILWIND_CONFIG_SNIPPET
from native.registry.colors import COLOR_THEMES
from native.registry.components import COMPONENT_REGISTRY
from native.registry.fonts import FONT_REGISTRY
from native.registry.radii import RADII_OPTIONS
from native.registry.styles import STYLE_REGISTRY
from native.registry.themes import BASE_THEMES

# ── utilities bundle injected by `buridan init` ───────────────────────────────
# Order matters — each block is appended in sequence.
UTILITIES_BUNDLE = [
    ("shimmer", SHIMMER_CSS),
    ("scrollbar", SCROLLBAR_CSS),
]

# Sentinel comments used to detect whether a utility is already present.
UTILITY_SENTINELS = {
    "shimmer": "/* ── Shimmer utility",
    "scrollbar": "/* ── Scrollbar utilities",
}


# ── theme rebuilding ──────────────────────────────────────────────────────────


VERSIONED_PATH_PARTS = 4


def flatten_vars(obj: dict) -> dict:
    out = {}
    for k, v in obj.items():
        key = "--radius" if k == "radius" else f"--{k}"
        out[key] = v
    return out


def _apply_color_theme(theme: dict[str, str], color_id: str, *, dark: bool) -> None:
    """Apply color theme variables to theme dict, filtering out chart colors."""
    color = next((c for c in COLOR_THEMES if c["id"] == color_id), None)
    if color:
        source = color["dark"] if dark else color["light"]
        theme.update(
            {
                k: v
                for k, v in flatten_vars(source).items()
                if not k.startswith("--chart-")
            },
        )


def _apply_chart_theme(theme: dict[str, str], chart_id: str, *, dark: bool) -> None:
    """Apply chart color variables to theme dict."""
    chart = next((c for c in COLOR_THEMES if c["id"] == chart_id), None)
    if chart:
        source = chart["dark"] if dark else chart["light"]
        theme.update(
            {k: v for k, v in flatten_vars(source).items() if k.startswith("--chart-")},
        )


def _apply_style_theme(theme: dict[str, str], style_id: str) -> None:
    """Apply style registry variables to theme dict."""
    style = next((s for s in STYLE_REGISTRY if s["id"] == style_id), None)
    if style and isinstance(style["vars"], dict):
        theme.update(style["vars"])


def _apply_font_theme(theme: dict[str, str], font_id: str) -> None:
    """Apply font registry variables to theme dict."""
    font = next((f for f in FONT_REGISTRY if f["id"] == font_id), None)
    if font and isinstance(font["vars"], dict):
        theme.update(font["vars"])


def rebuild_theme(config: dict) -> dict:
    base_id = config.get("baseId")
    color_id = config.get("colorId")
    chart_id = config.get("chartId")
    style_id = config.get("styleId")
    font_id = config.get("fontId")
    radius = config.get("radius")
    dark = config.get("darkMode", False)

    base = next((b for b in BASE_THEMES if b["id"] == base_id), None)
    if not base:
        return {}

    theme = {**flatten_vars(base["dark"] if dark else base["light"])}

    if color_id:
        _apply_color_theme(theme, color_id, dark=dark)
    if chart_id:
        _apply_chart_theme(theme, chart_id, dark=dark)
    if style_id:
        _apply_style_theme(theme, style_id)
    if font_id:
        _apply_font_theme(theme, font_id)

    if radius:
        theme["--radius"] = radius

    return theme


def format_css(config: dict) -> str:
    return "\n".join(f"    {k}: {v};" for k, v in config.items() if k.startswith("--"))


def generate_theme_css(seed: str) -> str:
    decoded = decode_seed(
        seed,
        base_themes=BASE_THEMES,
        color_themes=COLOR_THEMES,
        style_registry=STYLE_REGISTRY,
        radii_options=RADII_OPTIONS,
        font_registry=FONT_REGISTRY,
    )
    if not decoded:
        return ""

    def build(*, dark: bool) -> str:
        return format_css(rebuild_theme({**decoded, "darkMode": dark}))

    return f":root {{\n{build(dark=False)}\n}}\n\n.dark {{\n{build(dark=True)}\n}}"


# ── component copying ─────────────────────────────────────────────────────────


def get_source_root() -> Path | None:
    source_root = Path(__file__).parent.parent
    if (source_root / "components").exists():
        return source_root
    try:
        import components

        return Path(components.__file__).parent.parent
    except (ImportError, AttributeError):
        return None


def parse_component_spec(spec: str) -> tuple[str, str | None]:
    """Parse component spec like 'button@1.0.0' into ('button', '1.0.0')."""
    if "@" in spec:
        name, version = spec.split("@", 1)
        return name.lower(), version
    return spec.lower(), None


def parse_version_key(version_str: str) -> list[int]:
    """Helper to sort versions semantically (e.g. '2.0.0' > '1.0.0' > '1')."""
    return [int(x) for x in re.findall(r"\d+", version_str)]


def get_latest_version(component_name: str, registry: dict) -> str | None:
    """Find the latest registered version of a component."""
    target = component_name.lower()
    versions = []

    for key in registry:
        if key.startswith(f"{target}@"):
            version = key.split("@", 1)[1]
            versions.append(version)

    if not versions:
        if target in registry:
            return target
        return None

    versions.sort(key=parse_version_key)
    return f"{target}@{versions[-1]}"


def resolve_dependencies(
    component_names: list[str],
    registry: dict,
) -> tuple[list[str], dict[str, str]]:
    """Resolve a list of top-level component specs (with optional @version)
    plus their transitive dependencies into a file list and a name->version
    map suitable for the manifest.

    Components are deduped by NAME, not by name+version — two different
    versions of the same component are never both queued for copy. If the
    same component is reachable at two different versions (e.g. pinned
    explicitly on the command line, but also pulled in unpinned by another
    component's dependencies), the version resolved from an explicit
    top-level request always wins; a conflict pulled in purely via
    dependencies is resolved by first-come and a warning is printed.
    """
    required_files: set[str] = set()
    resolved: dict[str, str] = {}  # component name -> chosen registry key
    order: list[str] = []  # first-resolved order, for a stable installed_map
    warned: set[str] = set()

    def resolve_key(spec: str) -> str | None:
        key = spec.lower()
        if "@" in key:
            return key if key in registry else None
        return get_latest_version(key, registry)

    def claim(name: str, key: str) -> bool:
        """Register `name` as resolved to `key`. Returns True if this call
        actually claimed it (False if already claimed by something else).
        """
        if name in resolved:
            if resolved[name] != key and name not in warned:
                _, existing_version = parse_component_spec(resolved[name])
                _, new_version = parse_component_spec(key)
                print(
                    f"Warning: '{name}' requested at both "
                    f"{existing_version or 'latest'} and {new_version or 'latest'}; "
                    f"keeping {existing_version or 'latest'}.",
                )
                warned.add(name)
            return False
        resolved[name] = key
        order.append(name)
        return True

    def add_files_and_deps(key: str) -> None:
        entry = registry[key]
        for f in entry["files"]:
            required_files.add(f)
        for dep in entry.get("dependencies", []):
            add(dep)

    def add(spec: str) -> None:
        key = resolve_key(spec)
        if not key:
            print(f"Warning: Component '{spec}' not found in registry.")
            return
        name, _ = parse_component_spec(key)
        if not claim(name, key):
            return
        add_files_and_deps(key)

    # First pass: claim every explicitly-requested component up front, so a
    # pinned version always wins over whatever a dependency graph resolves
    # to later, regardless of command-line order.
    explicit_names: list[str] = []
    for spec in component_names:
        key = resolve_key(spec)
        if not key:
            print(f"Warning: Component '{spec}' not found in registry.")
            continue
        name, _ = parse_component_spec(key)
        claim(name, key)
        explicit_names.append(name)

    # Second pass: pull in files + dependencies for each explicit component,
    # using resolved[name] — the version that actually won the claim above —
    # not whichever key that particular spec happened to resolve to.
    for name in dict.fromkeys(explicit_names):  # dedupe, keep first-seen order
        add_files_and_deps(resolved[name])

    installed_map = {
        name: (parse_component_spec(resolved[name])[1] or "latest") for name in order
    }
    return sorted(required_files), installed_map


def load_manifest(target_root: Path) -> dict:
    """Load components.json, tolerating a missing or corrupt file.
    Always returns a dict with at least 'components' and 'theme' keys.
    """
    manifest_path = target_root / "components.json"
    manifest: dict = {}

    if manifest_path.exists():
        try:
            loaded = json.loads(manifest_path.read_text())
            if isinstance(loaded, dict):
                manifest = loaded
            else:
                print(
                    "Warning: components.json content was not a JSON object; recreating it.",
                )
        except (json.JSONDecodeError, OSError):
            print("Warning: components.json was unreadable; recreating it.")

    manifest.setdefault("components", {})
    manifest.setdefault("theme", {})
    return manifest


def save_manifest(target_root: Path, manifest: dict) -> None:
    manifest_path = target_root / "components.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))


def update_manifest(target_root: Path, installed_map: dict[str, str]) -> None:
    """Merge newly installed components into components.json without
    touching the theme section.
    """
    manifest = load_manifest(target_root)
    manifest["components"].update(installed_map)
    save_manifest(target_root, manifest)
    print("• Updated manifest: components.json")


def update_manifest_theme(target_root: Path, preset: str, config: dict) -> None:
    """Record the currently-applied theme preset in components.json without
    touching the components section.
    """
    manifest = load_manifest(target_root)

    theme_data = {
        "preset": preset,
        "baseId": config.get("baseId"),
        "colorId": config.get("colorId"),
        "chartId": config.get("chartId"),
        "styleId": config.get("styleId"),
        "fontId": config.get("fontId"),
        "radius": config.get("radius"),
    }
    # Drop unset fields rather than writing nulls — keeps the file readable
    # and makes it obvious which parts of the preset were actually specified.
    manifest["theme"] = {k: v for k, v in theme_data.items() if v is not None}

    save_manifest(target_root, manifest)
    print("• Updated manifest: components.json (theme)")


BLOCK_SOURCE_PREFIX = "native/lib/blocks/"


def remap_dest(rel: str) -> str:
    """Remap block source paths to blocks/ in the user's project root,
    and flatten versioned component subdirectories.

    Example: components/ui/button/v1.py -> components/ui/button.py
    """
    path = Path(rel)
    # Detect versioned components like components/ui/button/v1.py
    if (
        len(path.parts) >= VERSIONED_PATH_PARTS
        and path.parts[0] == "components"
        and re.match(r"^v\d+(?:_\d+)*$", path.stem)
    ):
        return str(Path(path.parent.parent) / f"{path.parent.name}.py")

    if rel.startswith(BLOCK_SOURCE_PREFIX):
        return "blocks/" + Path(rel).name
    return rel


def add_components_to_project(
    component_names: list[str],
    target_root: Path | None = None,
) -> bool:
    if target_root is None:
        target_root = Path.cwd()

    if not (target_root / "rxconfig.py").exists():
        print(
            "Error: rxconfig.py not found. Please run this command in a Reflex project root.",
        )
        return False

    source_root = get_source_root()
    if not source_root:
        print("Error: Could not locate Buridan source components.")
        return False

    files, installed_map = resolve_dependencies(component_names, COMPONENT_REGISTRY)
    if not files:
        print("No files to copy.")
        return False

    for rel in files:
        src = source_root / rel
        dest = target_root / remap_dest(rel)

        if not src.exists():
            print(f"Warning: Source file {src} does not exist.")
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)

        current = dest.parent
        while current != target_root:
            init = current / "__init__.py"
            if not init.exists():
                init.touch()
            if current.name in ("components", "blocks"):
                break
            current = current.parent

        shutil.copy2(src, dest)
        print(f"✓ Added {remap_dest(rel)}")

    update_manifest(target_root, installed_map)
    return True


def _find_rx_config_node(tree: ast.AST) -> ast.Call | None:
    """Find the rx.Config() or rx.config() call node in the AST."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        call = node.value
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr.lower() == "config"
            and getattr(call.func.value, "id", "") == "rx"
        ):
            return call
    return None


def _inject_plugins_into_existing(
    lines: list[str],
    snippet: str,
    call: ast.Call,
) -> bool:
    """Inject plugins into an rx.Config call that already has plugins kwarg."""
    end = call.end_lineno if call.end_lineno is not None else call.lineno
    for i in range(call.lineno - 1, end):
        if "plugins=" in lines[i]:
            lines[i] = lines[i].replace(
                "plugins=[",
                f"plugins=[\n{snippet},",
            )
            return True
    return False


def _inject_plugins_into_new(
    lines: list[str],
    snippet: str,
    call: ast.Call,
) -> bool:
    """Add plugins kwarg to an rx.Config call that doesn't have one."""
    end = call.end_lineno if call.end_lineno is not None else call.lineno
    for i in range(call.lineno - 1, end):
        if "Config(" in lines[i] or "config(" in lines[i]:
            indent = " " * (len(lines[i]) - len(lines[i].lstrip()))
            lines[i] = lines[i].replace(
                "(",
                f"(\n{indent}    plugins=[\n{snippet}\n{indent}    ],",
            )
            return True
    return False


def _cleanup_duplicate_plugins(content: str) -> str:
    """Remove duplicate TailwindV4Plugin references after injection."""
    content = content.replace("rx.plugins.TailwindV4Plugin(),", "")
    content = content.replace("rx.plugins.TailwindV4Plugin()", "")
    return content.replace(",,", ",")


def patch_rxconfig(config_path: Path) -> None:
    """Inject TailwindV4 plugin into rxconfig.py if not already present."""
    content = config_path.read_text()

    if "var(--background)" in content:
        print("• rxconfig.py already contains Buridan UI theme tokens.")
        return

    try:
        tree = ast.parse(content)
        snippet = TAILWIND_CONFIG_SNIPPET.strip().rstrip(",")
        lines = content.splitlines()
        modified = False

        call = _find_rx_config_node(tree)
        if call:
            plugins_kw = next((kw for kw in call.keywords if kw.arg == "plugins"), None)
            if plugins_kw:
                modified = _inject_plugins_into_existing(lines, snippet, call)
            else:
                modified = _inject_plugins_into_new(lines, snippet, call)

            if modified:
                content = "\n".join(lines)
                content = _cleanup_duplicate_plugins(content)

        if not modified:
            if "rx.Config(" in content:
                content = content.replace(
                    "rx.Config(",
                    f"rx.Config(\n    plugins=[\n{snippet}\n    ],",
                )
                modified = True
            elif "rx.config(" in content:
                content = content.replace(
                    "rx.config(",
                    f"rx.config(\n    plugins=[\n{snippet}\n    ],",
                )
                modified = True

        if modified:
            import_stmt = "from reflex.plugins.shared_tailwind import TailwindConfig"
            if import_stmt not in content:
                content = f"{import_stmt}\n{content}"
            config_path.write_text(content)
            print("✓ Updated rxconfig.py with Buridan UI Tailwind config.")
        else:
            print(
                "Warning: Could not automatically update rxconfig.py. Please configure manually.",
            )

    except (SyntaxError, OSError) as e:
        print(f"Warning: Could not parse rxconfig.py ({e}). Please configure manually.")


# ── commands ──────────────────────────────────────────────────────────────────


def cmd_init() -> None:
    root = Path.cwd()

    if not (root / "rxconfig.py").exists():
        print(
            "Error: rxconfig.py not found. Please run this command in a Reflex project root.",
        )
        sys.exit(1)

    assets_dir = root / "assets"
    assets_dir.mkdir(exist_ok=True)
    css_path = assets_dir / "globals.css"

    if not css_path.exists():
        css_path.write_text("")
        print(f"✓ Created {css_path.relative_to(root)}")
    else:
        print(f"• Found {css_path.relative_to(root)}")

    current_css = css_path.read_text()
    added = []

    for name, css in UTILITIES_BUNDLE:
        sentinel = UTILITY_SENTINELS[name]
        if sentinel in current_css:
            print(f"• {name} utility already present in globals.css — skipping.")
        else:
            current_css += f"\n{css}"
            added.append(name)

    if added:
        css_path.write_text(current_css)
        for name in added:
            print(f"✓ Added {name} utility to globals.css")

    patch_rxconfig(root / "rxconfig.py")

    print("\n✓ Buridan UI initialized successfully.")
    print("\nNext steps:")
    print("  1. Add globals.css to your app stylesheets:")
    print('     app = rx.App(stylesheets=["globals.css"])')
    print("  2. Apply a theme:")
    print("     buridan apply --preset b0")
    print("  3. Add components:")
    print("     buridan add button")


def _find_theme_block_end(lines: list[str], start_line: int) -> int:
    """Find the end line of a CSS block starting at start_line (handles brace tracking)."""
    brace_depth = 0
    in_block = False
    for i, line in enumerate(lines[start_line:], start_line):
        brace_depth += line.count("{") - line.count("}")
        if brace_depth > 0:
            in_block = True
        if in_block and brace_depth == 0:
            return i
    return start_line


def _find_dark_theme_end(lines: list[str], start_after_line: int) -> int:
    """Find the end of .dark { } block starting search after start_after_line."""
    rest = lines[start_after_line + 1 :]
    for j, ln in enumerate(rest):
        if ln.strip().startswith(".dark {"):
            bd = 0
            for k, dl in enumerate(
                lines[start_after_line + 1 + j :],
                start_after_line + 1 + j,
            ):
                bd += dl.count("{") - dl.count("}")
                if bd == 0 and k > start_after_line + 1 + j:
                    return k
            break
    return start_after_line


def _replace_theme_blocks(css_path: Path, theme_css: str) -> None:
    """Replace :root and .dark theme blocks in globals.css, preserving other content."""
    if not css_path.exists():
        css_path.write_text(theme_css)
        return

    current = css_path.read_text()
    if ":root {" not in current:
        css_path.write_text(theme_css + "\n\n" + current)
        return

    lines = current.splitlines()
    start_line = next(
        (i for i, ln in enumerate(lines) if ln.strip().startswith(":root {")),
        None,
    )

    if start_line is None:
        css_path.write_text(theme_css + "\n\n" + current)
        return

    end_line = _find_theme_block_end(lines, start_line)
    end_line = _find_dark_theme_end(lines, end_line)

    after = "\n".join(lines[end_line + 1 :]).lstrip("\n")
    new_css = theme_css + ("\n\n" + after if after else "")
    css_path.write_text(new_css)


def cmd_apply(preset: str) -> None:
    root = Path.cwd()

    if not (root / "rxconfig.py").exists():
        print("Error: rxconfig.py not found. Please run this in a Reflex project root.")
        sys.exit(1)

    config = decode_seed(
        preset,
        base_themes=BASE_THEMES,
        color_themes=COLOR_THEMES,
        style_registry=STYLE_REGISTRY,
        radii_options=RADII_OPTIONS,
        font_registry=FONT_REGISTRY,
    )
    if not config:
        print(
            f"Error: Invalid preset ID '{preset}'. Get a valid preset from https://buridan.reflex.run/create",
            file=sys.stderr,
        )
        sys.exit(1)

    assets_dir = root / "assets"
    assets_dir.mkdir(exist_ok=True)
    css_path = assets_dir / "globals.css"

    theme_css = generate_theme_css(preset)
    _replace_theme_blocks(css_path, theme_css)

    print(f"✓ Applied preset '{preset}' to globals.css")

    update_manifest_theme(root, preset, config)

    print("\nNext steps:")
    print("  Add globals.css to your app stylesheets if you haven't already:")
    print('  app = rx.App(stylesheets=["globals.css"])')


def cmd_create() -> None:
    """Open the Buridan UI theme builder in the browser."""
    import webbrowser

    url = "https://buridan.reflex.run/create"
    print(f"Opening theme builder: {url}")
    webbrowser.open(url)


def cmd_add(component_names: list[str]) -> None:
    """Add one or more components and their dependencies to the project."""
    css_path = Path.cwd() / "assets" / "globals.css"
    if not css_path.exists() or ":root {" not in css_path.read_text():
        print("⚠  Warning: No theme detected in assets/globals.css.")
        print(
            "   Components use CSS variables that require a theme to render correctly.",
        )
        print("   Run 'buridan apply --preset b0' to apply a default theme.\n")

    if not add_components_to_project(component_names):
        sys.exit(1)


def cmd_list() -> None:
    """List all available components."""
    skip = {"core", "hugeicon"}
    names = sorted(n for n in COMPONENT_REGISTRY if n not in skip)
    print(f"Available components ({len(names)}):\n")
    for name in names:
        print(f"  {name}")


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="buridan",
        description="Buridan UI — CLI for Reflex component library",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Initialize Buridan UI utilities in a Reflex project")
    sub.add_parser("create", help="Open the Buridan UI theme builder in your browser")

    apply_p = sub.add_parser(
        "apply",
        help="Apply a theme preset (from buridan.reflex.run/create)",
    )
    apply_p.add_argument(
        "--preset",
        required=True,
        help="Preset ID e.g. b0 or b1000",
    )

    add_p = sub.add_parser("add", help="Add components to your project")
    add_p.add_argument("components", nargs="+", help="Component name(s) to add")

    sub.add_parser("list", help="List all available components")

    args = parser.parse_args()

    if args.command == "create":
        cmd_create()
    elif args.command == "init":
        cmd_init()
    elif args.command == "apply":
        cmd_apply(args.preset)
    elif args.command == "add":
        cmd_add(args.components)
    elif args.command == "list":
        cmd_list()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
