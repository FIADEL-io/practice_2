import unittest

from depgraph.diagram import to_plantuml
from depgraph.graph import build_graph
from depgraph.raster import PNG_SIGNATURE, render_png


class DiagramTests(unittest.TestCase):

    def test_plantuml_keeps_edges_and_cycle(self) -> None:
        described = {"A": ("B",), "B": ("A",)}
        graph = build_graph("A", lambda node: list(described[node]), "")
        text = to_plantuml(graph)
        self.assertIn("@startuml", text)
        self.assertIn('"A" --> "B"', text)
        self.assertIn('"B" --> "A"', text)
        self.assertTrue(text.strip().endswith("@enduml"))

    def test_png_has_signature(self) -> None:
        graph = build_graph("A", lambda _node: ["B"], "")
        image = render_png(graph)
        self.assertTrue(image.startswith(PNG_SIGNATURE))


if __name__ == "__main__":
    unittest.main()
