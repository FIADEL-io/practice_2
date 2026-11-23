from __future__ import annotations

from pathlib import Path

from depgraph.graph import Graph
from depgraph.raster import render_png

PLANTUML_SUFFIX = ".puml"


def to_plantuml(graph: Graph) -> str:
    lines = ["@startuml", "left to right direction"]
    for node in graph.order:
        deps = graph.adjacency[node]
        if not deps:
            lines.append(f'"{_label(node)}"')
            continue
        for dep in deps:
            lines.append(f'"{_label(node)}" --> "{_label(dep)}"')
    lines.append("@enduml")
    return "\n".join(lines)


def save_diagram(graph: Graph, image_name: str) -> tuple[str, str]:
    image = Path(image_name)
    source = image.with_suffix(PLANTUML_SUFFIX)
    source.write_text(to_plantuml(graph) + "\n", encoding="utf-8")
    image.write_bytes(render_png(graph))
    return str(source), str(image)


def _label(name: str) -> str:
    return name.replace('"', "'")
