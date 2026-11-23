from __future__ import annotations

import struct
import zlib

from depgraph.glyphs import GLYPHS
from depgraph.graph import Graph

Color = tuple[int, int, int]
Box = tuple[int, int, int, int]

ZERO = 0
GLYPH_WIDTH = 5
GLYPH_HEIGHT = 7
SCALE = 2
LETTER_GAP = 1
PAD = 8
GAP_X = 40
GAP_Y = 28
MARGIN = 16
TOP_BIT = 16
PAPER: Color = (255, 255, 255)
INK: Color = (24, 58, 66)
EDGE: Color = (32, 112, 118)
FILL: Color = (232, 244, 244)
BIT_DEPTH = 8
COLOR_RGB = 2
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def render_png(graph: Graph) -> bytes:
    boxes = _boxes(graph)
    width, height = _canvas_size(boxes)
    rows = _blank(width, height)
    _edges(rows, graph, boxes)
    for name, box in boxes.items():
        _box(rows, name, box)
    return _encode(rows)


def _boxes(graph: Graph) -> dict[str, Box]:
    columns = _columns(graph)
    boxes: dict[str, Box] = {}
    left = MARGIN
    for column in columns:
        top = MARGIN
        widest = ZERO
        for name in column:
            box = (left, top, *_size(name))
            boxes[name] = box
            top += box[3] + GAP_Y
            if box[2] > widest:
                widest = box[2]
        left += widest + GAP_X
    return boxes


def _columns(graph: Graph) -> list[list[str]]:
    rank = {graph.order[0]: ZERO}
    for node in graph.order:
        _rank_children(node, graph.adjacency, rank)
    last = max(rank.values())
    columns: list[list[str]] = [[] for _ in range(last + 1)]
    for node in graph.order:
        columns[rank[node]].append(node)
    return columns


def _rank_children(
    node: str,
    adjacency: dict[str, tuple[str, ...]],
    rank: dict[str, int],
) -> None:
    for dep in adjacency.get(node, ()):
        if dep in rank:
            continue
        rank[dep] = rank[node] + 1


def _size(name: str) -> tuple[int, int]:
    letters = len(name) * (GLYPH_WIDTH + LETTER_GAP) * SCALE
    return (letters + PAD * 2, GLYPH_HEIGHT * SCALE + PAD * 2)


def _canvas_size(boxes: dict[str, Box]) -> tuple[int, int]:
    right = MARGIN
    bottom = MARGIN
    for _name, (left, top, width, height) in boxes.items():
        edge = left + width + MARGIN
        floor = top + height + MARGIN
        if edge > right:
            right = edge
        if floor > bottom:
            bottom = floor
    return right, bottom


def _blank(width: int, height: int) -> list[bytearray]:
    row = bytearray(PAPER * width)
    return [bytearray(row) for _ in range(height)]


def _edges(
    rows: list[bytearray],
    graph: Graph,
    boxes: dict[str, Box],
) -> None:
    for node, deps in graph.adjacency.items():
        start = _center(boxes[node])
        for dep in deps:
            finish = _center(boxes[dep])
            _line(rows, start, finish, EDGE)


def _box(rows: list[bytearray], name: str, box: Box) -> None:
    left, top, width, height = box
    _rect(rows, left, top, width, height, FILL)
    _frame(rows, left, top, width, height, INK)
    _text(rows, left + PAD, top + PAD, name)


def _center(box: Box) -> tuple[int, int]:
    left, top, width, height = box
    return left + width // 2, top + height // 2


def _text(rows: list[bytearray], x: int, y: int, name: str) -> None:
    cursor = x
    step = (GLYPH_WIDTH + LETTER_GAP) * SCALE
    for char in name.upper():
        glyph = GLYPHS.get(char)
        if glyph is not None:
            _glyph(rows, cursor, y, glyph)
        cursor += step


def _glyph(
    rows: list[bytearray],
    x: int,
    y: int,
    glyph: tuple[int, ...],
) -> None:
    for row_index, bits in enumerate(glyph):
        mask = TOP_BIT
        for column in range(GLYPH_WIDTH):
            if bits & mask:
                _stamp(rows, x + column * SCALE, y + row_index * SCALE)
            mask >>= 1


def _stamp(rows: list[bytearray], x: int, y: int) -> None:
    for dy in range(SCALE):
        for dx in range(SCALE):
            _dot(rows, x + dx, y + dy, INK)


def _rect(
    rows: list[bytearray],
    left: int,
    top: int,
    width: int,
    height: int,
    color: Color,
) -> None:
    for y in range(top, top + height):
        for x in range(left, left + width):
            _dot(rows, x, y, color)


def _frame(
    rows: list[bytearray],
    left: int,
    top: int,
    width: int,
    height: int,
    color: Color,
) -> None:
    right = left + width - 1
    bottom = top + height - 1
    _line(rows, (left, top), (right, top), color)
    _line(rows, (left, bottom), (right, bottom), color)
    _line(rows, (left, top), (left, bottom), color)
    _line(rows, (right, top), (right, bottom), color)


def _line(
    rows: list[bytearray],
    start: tuple[int, int],
    finish: tuple[int, int],
    color: Color,
) -> None:
    x0, y0 = start
    x1, y1 = finish
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        _dot(rows, x0, y0, color)
        if x0 == x1 and y0 == y1:
            return
        doubled = err + err
        if doubled >= dy:
            err += dy
            x0 += sx
        if doubled <= dx:
            err += dx
            y0 += sy


def _dot(rows: list[bytearray], x: int, y: int, color: Color) -> None:
    if y < ZERO or x < ZERO:
        return
    if y >= len(rows) or x >= len(rows[ZERO]) // 3:
        return
    offset = x * 3
    rows[y][offset:offset + 3] = bytes(color)


def _encode(rows: list[bytearray]) -> bytes:
    raw = bytearray()
    for row in rows:
        raw.append(ZERO)
        raw.extend(row)
    height = len(rows)
    width = len(rows[ZERO]) // 3
    chunks = (
        _chunk(b"IHDR", _header(width, height)),
        _chunk(b"IDAT", zlib.compress(bytes(raw))),
        _chunk(b"IEND", b""),
    )
    return PNG_SIGNATURE + b"".join(chunks)


def _header(width: int, height: int) -> bytes:
    return struct.pack(
        ">IIBBBBB",
        width,
        height,
        BIT_DEPTH,
        COLOR_RGB,
        ZERO,
        ZERO,
        ZERO,
    )


def _chunk(tag: bytes, data: bytes) -> bytes:
    body = tag + data
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + body + struct.pack(">I", crc)
