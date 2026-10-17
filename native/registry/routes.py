from pathlib import Path
from typing import Any

from native.engine import constants
from native.engine.utils import parse_frontmatter


# --- Method: Generate doc routes/urls ---
def generate_doc_routes(section_folder: str, base_path: str) -> list[dict]:
    """Generates routes for a documentation section by recursively reading
    frontmatter from markdown files.

    Args:
        section_folder: The folder name inside 'docs/' (e.g., 'getting_started').
        base_path: The base URL path for the routes (e.g., 'docs/getting-started/').

    Returns:
        A list of route dictionaries, sorted by the 'order' in metadata.
    """
    routes = []
    docs_path = f"{constants.DOCS_BASE_DIR}/{section_folder}"

    md_files = [str(p) for p in Path(docs_path).rglob("*.md")]

    if not md_files:
        print(f"Warning: No markdown files found in '{docs_path}'")
        return []

    for file_path in md_files:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            continue

        metadata, _ = parse_frontmatter(content)

        if not metadata or "title" not in metadata:
            continue

        # Create a URL slug from the file path relative to the section folder.
        relative_path = Path(file_path).relative_to(docs_path).as_posix()
        path_slug = relative_path.replace(".md", "").replace("_", "-")

        route_info = {
            "title": metadata["title"],
            "description": metadata["description"],
            "url": f"{base_path}{path_slug}",  # Will include docs/ prefix
            "order": metadata.get("order", 0),
        }

        routes.append(route_info)

    routes.sort(key=lambda x: x["order"])

    return routes


DOC_SECTIONS = [
    (
        "getting_started",
        "docs/getting-started/",
        "",
        [{"title": "llms.txt", "url": "llms.txt", "order": "5"}],
    ),
    ("utilities", "docs/utilities/", "title", []),
    ("resources", "docs/resources/", "title", []),
    ("components", "docs/components/", "title", []),
    ("charts", "docs/charts/", "title", []),
]


def build_all_routes() -> dict[str, list[dict[str, Any]]]:
    result = {}

    for section, base_path, sort_key, extras in DOC_SECTIONS:
        routes = generate_doc_routes(section, base_path)
        routes.extend(extras)
        routes.sort(key=lambda x: x.get(sort_key, ""))

        result[section] = routes

    return result


ALL_ROUTES = build_all_routes()

GET_STARTED_URLS = ALL_ROUTES["getting_started"]
RESOURCES_URLS = ALL_ROUTES["resources"]
BASE_UI_COMPONENTS = ALL_ROUTES["components"]
CHARTS_URLS = ALL_ROUTES["charts"]
UTILITIES = ALL_ROUTES["utilities"]

if __name__ == "__main__":
    print(ALL_ROUTES)
