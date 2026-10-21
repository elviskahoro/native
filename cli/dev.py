import argparse
import os
import subprocess
from pathlib import Path

import questionary
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

DOCS_DIR = Path("docs")
MIN_PATH_PARTS = 2


def build_index() -> dict[str, list[str]]:
    """Builds:
    {
        "getting-started": ["introduction", "installation"],
        "components": ["button", "input"]
    }.
    """
    sections: dict[str, list[str]] = {}

    for file in DOCS_DIR.glob("**/*.md"):
        rel = file.relative_to(DOCS_DIR)
        parts = rel.with_suffix("").parts

        if len(parts) < MIN_PATH_PARTS:
            continue

        section = parts[0].replace("_", "-")
        page = parts[1].replace("_", "-")

        sections.setdefault(section, []).append(page)

    for pages in sections.values():
        pages.sort()

    return sections


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dev",
        description="Run the docs site with a specific set of pages loaded.",
        epilog=(
            "Examples:\n"
            "  uv run dev                            interactive picker\n"
            "  uv run dev button input               load pages by name\n"
            "  uv run dev components/button          load by full path\n"
            "  uv run dev --section components       load a whole section\n"
            "  uv run dev --section components auth  load multiple sections\n"
            "  uv run dev prod                       run full site, prod mode\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "pages",
        nargs="*",
        help="page names (e.g. 'button') or full paths (e.g. 'components/button')",
    )
    parser.add_argument(
        "--section",
        "-s",
        nargs="+",
        default=[],
        metavar="SECTION",
        help="load every page in the given section(s)",
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="run in prod mode (loads the full site)",
    )

    return parser


def resolve_pages(
    names: list[str],
    section_names: list[str],
    sections: dict[str, list[str]],
) -> list[str] | None:
    """Resolves bare page names ('button'), full paths ('components/button'),
    and --section names into a deduped list of full 'section/page' paths.

    Returns None (and prints errors) if anything couldn't be resolved.
    """
    name_to_paths: dict[str, list[str]] = {}
    for section, pages in sections.items():
        for page in pages:
            name_to_paths.setdefault(page, []).append(f"{section}/{page}")

    resolved = []
    seen = set()
    errors = []

    for name in names:
        if "/" in name:
            section, _, page = name.partition("/")
            if page in sections.get(section, []):
                path = name
            else:
                errors.append(f"page not found: '{name}'")
                continue
        else:
            matches = name_to_paths.get(name)
            if not matches:
                errors.append(f"page not found: '{name}'")
                continue
            if len(matches) > 1:
                errors.append(
                    f"'{name}' is ambiguous (matches: {', '.join(matches)}) "
                    f"— use the full path, e.g. '{matches[0]}'",
                )
                continue
            path = matches[0]

        if path not in seen:
            seen.add(path)
            resolved.append(path)

    for section in section_names:
        if section not in sections:
            errors.append(f"section not found: '{section}'")
            continue
        for page in sections[section]:
            path = f"{section}/{page}"
            if path not in seen:
                seen.add(path)
                resolved.append(path)

    if errors:
        for e in errors:
            print(f"Error: {e}")
        return None

    if not resolved:
        return None

    return resolved


def select_env() -> str | None:
    env = questionary.select(
        "Run mode:",
        choices=["dev", "prod"],
    ).ask()

    if env is None:
        return None

    return env


def select_pages_fuzzy(sections: dict[str, list[str]]) -> list[str] | None:
    """Fuzzy search + multi-select over all pages."""
    choices = []

    for section, pages in sections.items():
        for page in pages:
            path = f"{section}/{page}"
            choices.append(Choice(value=path, name=f"  {path}"))

    result = inquirer.fuzzy(
        message=(
            "Search pages (type to filter, tab to select multiple, enter to confirm):"
        ),
        choices=choices,
        multiselect=True,
        max_height="70%",
        instruction="(type a page or section/page path)",
    ).execute()

    if not result:
        return None

    pages = []
    seen = set()

    for item in result:
        if item not in seen:
            seen.add(item)
            pages.append(item)

    return pages


def run_reflex(env: str, pages: list[str] | None) -> str | None:
    """Runs Reflex and prints correct URLs ONLY after the actual port is known."""
    if env == "dev":
        os.environ["BURIDAN_DEV_MODE"] = "true"

        if pages:
            os.environ["BURIDAN_DEV_PAGES"] = ",".join(pages)
        else:
            os.environ.pop("BURIDAN_DEV_PAGES", None)
    else:
        os.environ.pop("BURIDAN_DEV_MODE", None)
        os.environ.pop("BURIDAN_DEV_PAGES", None)

    cmd = ["uv", "run", "reflex", "run", "--env", env]

    process = subprocess.Popen(  # noqa: S603  # fixed argv, env validated upstream
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    port = None

    if process.stdout is None:
        msg = "reflex subprocess has no stdout pipe"
        raise RuntimeError(msg)

    for line in process.stdout:
        print(line, end="")

        # Detect actual runtime port from Reflex output (only once)
        if port is None and "App running at:" in line:
            try:
                port = line.split("http://localhost:")[1].split("/")[0]

                # Print correct clickable URLs ONLY when server is ready
                if pages:
                    base_url = f"http://localhost:{port}/docs"

                    print("\nLoading specified URLs:")
                    for page in pages:
                        print(f"{base_url}/{page}")

            except IndexError:
                pass

    return port


def main() -> None:
    sections = build_index()

    parser = build_arg_parser()
    args = parser.parse_args()

    # ---------------- CLI FAST PATH: PROD ----------------
    # `uv run dev prod` or `uv run dev --prod`
    if args.prod or (args.pages and args.pages[0] == "prod"):
        print("Launching full site (prod mode)...")
        run_reflex("prod", pages=None)
        return

    requested_pages = list(args.pages)
    # allow (and ignore) an optional literal "dev" prefix, e.g. `dev.py dev button`
    if requested_pages and requested_pages[0] == "dev":
        requested_pages = requested_pages[1:]

    # ---------------- CLI FAST PATH: PAGES GIVEN DIRECTLY ----------------
    if requested_pages or args.section:
        resolved_pages = resolve_pages(requested_pages, args.section, sections)
        if resolved_pages is None:
            return

        print(f"Running reflex in dev with {len(resolved_pages)} page(s):")
        for page in resolved_pages:
            print(f"  {page}")

        run_reflex("dev", resolved_pages)
        return

    # ---------------- INTERACTIVE FLOW (no args given) ----------------
    env = select_env()
    if env is None:
        print("Exiting")
        return

    if env == "prod":
        print("Launching full site (prod mode)...")
        run_reflex(env, pages=None)
        return

    selected_pages = select_pages_fuzzy(sections)
    if selected_pages is None:
        print("Exiting")
        return

    confirm = questionary.confirm(
        f"Run reflex in {env} with {len(selected_pages)} pages?",
    ).ask()

    if not confirm:
        print("Cancelled")
        return

    run_reflex(env, selected_pages)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting")
