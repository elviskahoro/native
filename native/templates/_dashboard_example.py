from reflex.components.component import Component
from reflex_components_core.el import div, h3, p

from components.ui.badge import badge
from native.templates._dashboard import dashboard_demo
from native.templates.dashboard_introspect import load_dashboard_example


def _dependency_group(names: list[str]) -> Component:
    if not names:
        return div()
    return div(
        div(
            *[
                badge(
                    name,
                    class_name="rounded-none",
                )
                for name in names
            ],
            class_name="flex flex-wrap gap-1.5 mt-2",
        ),
        class_name="flex flex-col",
    )


def dashboard_example(
    dashboard_id: str,
    *,
    title: str,
    description: str = "",
) -> Component:
    """dashboard_id="dashboard_01" -> reads native/lib/dashboards/dashboard_01.py,
    renders it via dashboard_demo, and adds a metadata panel next to it
    (title/description/dependency badges), pulled straight from that file's
    source + imports.
    """
    example = load_dashboard_example(dashboard_id)
    component = example["component_fn"]()
    deps = example["dependencies"]

    return div(
        div(
            div(
                h3(title, class_name="text-base font-semibold"),
                p(description, class_name="text-sm text-muted-foreground mt-1"),
            ),
            div(
                h3("Dependencies", class_name="text-base font-semibold"),
                div(
                    _dependency_group(deps["components"]),
                    _dependency_group(deps["blocks"]),
                    class_name="flex flex-row items-center gap-2",
                ),
                class_name="hidden lg:block",
            ),
            class_name="grid grid-cols-1 lg:grid-cols-2",
        ),
        div(
            dashboard_demo(component, example["source"]),
        ),
        class_name="w-full flex flex-col gap-6",
    )
