import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bootstrap import ROOT
from depgraph.cli import main
from depgraph.constants import EXIT_CONFIG, EXIT_OK
from depgraph.graph import Graph


class CliTests(unittest.TestCase):

    def setUp(self) -> None:
        self._previous = os.getcwd()
        self._folder = tempfile.TemporaryDirectory()
        os.chdir(self._folder.name)

    def tearDown(self) -> None:
        os.chdir(self._previous)
        self._folder.cleanup()

    def test_prints_parameters_as_key_value(self) -> None:
        stdout = io.StringIO()
        path = str(ROOT / "config.yaml")
        deps = [("serde_core", "=1.0.229"), ("serde_derive", "1")]
        graph = Graph(
            {
                "serde": ("serde_core", "serde_derive"),
                "serde_core": (),
                "serde_derive": (),
            },
            ("serde", "serde_core", "serde_derive"),
            (),
        )
        with patch(
            "depgraph.cli.load_direct_dependencies",
            return_value=deps,
        ):
            with patch(
                "depgraph.cli.build_cargo_graph",
                return_value=graph,
            ):
                with contextlib.redirect_stdout(stdout):
                    code = main(["--config", path])
        lines = stdout.getvalue().splitlines()
        self.assertEqual(code, EXIT_OK)
        self.assertIn("прямые зависимости:", lines)
        self.assertIn("serde_core =1.0.229", lines)
        self.assertIn("serde_derive 1", lines)
        self.assertIn("package_name: serde", lines)
        self.assertIn("test_repository_mode: false", lines)
        self.assertIn("graph_image_name: serde.png", lines)
        self.assertIn("filter_substring: ", lines)
        self.assertIn("граф зависимостей:", lines)
        self.assertIn("serde -> serde_core, serde_derive", lines)
        self.assertLess(lines.index("serde_core"), lines.index("serde"))
        self.assertLess(lines.index("serde_derive"), lines.index("serde"))

    def test_prints_resolved_test_repository(self) -> None:
        stdout = io.StringIO()
        path = str(ROOT / "examples" / "test_repository.yaml")
        with contextlib.redirect_stdout(stdout):
            code = main(["--config", path])
        text = stdout.getvalue()
        self.assertEqual(code, EXIT_OK)
        self.assertIn("package_name: A", text)
        self.assertIn("test_repository_mode: true", text)
        self.assertIn("graph.txt", text)

    def test_cycle_example_prints_cycle(self) -> None:
        stdout = io.StringIO()
        path = str(ROOT / "examples" / "test_cycle.yaml")
        with contextlib.redirect_stdout(stdout):
            code = main(["--config", path])
        text = stdout.getvalue()
        self.assertEqual(code, EXIT_OK)
        self.assertIn("цикл: A -> B -> C -> A", text)
        self.assertIn("порядок загрузки:\nC\nB\nA", text)

    def test_diamond_prints_dependencies_before_package(self) -> None:
        stdout = io.StringIO()
        path = str(ROOT / "examples" / "test_order.yaml")
        with contextlib.redirect_stdout(stdout):
            code = main(["--config", path])
        text = stdout.getvalue()
        self.assertEqual(code, EXIT_OK)
        self.assertIn("порядок загрузки:\nD\nB\nC\nA", text)
        self.assertTrue(Path("order.png").is_file())
        source = Path("order.puml").read_text(encoding="utf-8")
        self.assertIn("@startuml", source)

    def test_filter_example_omits_filtered_package(self) -> None:
        stdout = io.StringIO()
        path = str(ROOT / "examples" / "test_filter.yaml")
        with contextlib.redirect_stdout(stdout):
            code = main(["--config", path])
        text = stdout.getvalue()
        self.assertEqual(code, EXIT_OK)
        self.assertIn("порядок загрузки:\nD\nB\nA", text)
        self.assertNotIn("\nC\n", text)

    def test_three_packages_write_diagrams(self) -> None:
        expected = {
            "serde": "SERDE",
            "tokio": "TOKIO",
            "regex": "REGEX",
        }
        for image, package in expected.items():
            path = ROOT / "examples" / "viz" / f"{image}.yaml"
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--config", str(path)])
            source = Path(f"{image}.puml").read_text(encoding="utf-8")
            self.assertEqual(code, EXIT_OK)
            self.assertTrue(Path(f"{image}.png").is_file())
            self.assertIn(f'"{package}"', source)

    def test_config_error_goes_to_stderr(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        path = str(ROOT / "examples" / "errors" / "bad_url.yaml")
        with contextlib.redirect_stdout(stdout):
            with contextlib.redirect_stderr(stderr):
                code = main(["--config", path])
        self.assertEqual(code, EXIT_CONFIG)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("ошибка конфигурации", stderr.getvalue())
        self.assertIn("repository", stderr.getvalue())

    def test_missing_file_is_config_error(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(["--config", "no-such-config.yaml"])
        self.assertEqual(code, EXIT_CONFIG)
        self.assertIn("не найден", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
