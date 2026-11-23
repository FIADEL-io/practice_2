from __future__ import annotations

import argparse
import sys

from depgraph.cargo_manifest import CargoError
from depgraph.config import AppConfig, ConfigError, load_config
from depgraph.constants import EXIT_CONFIG, EXIT_OK
from depgraph.dependencies import format_dependencies, load_direct_dependencies
from depgraph.diagram import save_diagram
from depgraph.graph import (
    GraphError,
    format_graph,
    format_load_order,
    load_order,
)
from depgraph.resolve import build_cargo_graph, build_test_graph


def main(argv: list[str] | None = None) -> int:
    _use_utf8()
    args = _parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"ошибка конфигурации: {error}", file=sys.stderr)
        return EXIT_CONFIG
    print(format_parameters(config))
    if config.test_repository_mode:
        return _print_graph(
            lambda: build_test_graph(config),
            config.graph_image_name,
        )
    try:
        dependencies = load_direct_dependencies(config)
    except CargoError as error:
        print(f"ошибка зависимостей: {error}", file=sys.stderr)
        return EXIT_CONFIG
    print("прямые зависимости:")
    rendered = format_dependencies(dependencies)
    if rendered != "":
        print(rendered)
    return _print_graph(
        lambda: build_cargo_graph(config, dependencies),
        config.graph_image_name,
    )


def _print_graph(load, image_name: str) -> int:
    try:
        graph = load()
    except (GraphError, CargoError) as error:
        print(f"ошибка графа: {error}", file=sys.stderr)
        return EXIT_CONFIG
    print(format_graph(graph))
    print(format_load_order(load_order(graph)))
    try:
        source, image = save_diagram(graph, image_name)
    except OSError as error:
        print(f"ошибка графа: {error}", file=sys.stderr)
        return EXIT_CONFIG
    print(f"plantuml: {source}")
    print(f"изображение: {image}")
    return EXIT_OK


def format_parameters(config: AppConfig) -> str:
    lines = [f"{key}: {value}" for key, value in config.as_pairs()]
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="depgraph",
        description=(
            "Визуализация графа зависимостей Cargo. "
            "Этап 5 сохраняет граф в PlantUML и PNG."
        ),
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Путь к YAML-файлу с параметрами.",
    )
    return parser.parse_args(argv)


def _use_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            continue
