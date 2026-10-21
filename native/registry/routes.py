# Re-export route constants from templates.routes for backward compatibility
from native.templates.routes import (
    ALL_ROUTES,
    BASE_UI_COMPONENTS,
    CHARTS_URLS,
    DOC_SECTIONS,
    GET_STARTED_URLS,
    RESOURCES_URLS,
    UTILITIES,
    build_all_routes,
    generate_doc_routes,
)

__all__ = [
    "ALL_ROUTES",
    "BASE_UI_COMPONENTS",
    "CHARTS_URLS",
    "DOC_SECTIONS",
    "GET_STARTED_URLS",
    "RESOURCES_URLS",
    "UTILITIES",
    "build_all_routes",
    "generate_doc_routes",
]

if __name__ == "__main__":
    print(ALL_ROUTES)
