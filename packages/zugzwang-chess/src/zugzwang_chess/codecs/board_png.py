"""Deterministic PNG board renderer (design §14.4, FR-056).

Renders a FEN into immutable, byte-reproducible PNG bytes. Every render
carries complete metadata: renderer version, theme, orientation, coordinate
labels, square size, font identity and the hash of the source state.

The renderer never depends on network or on wall-clock time. For the same
(fen, spec, font file) triple on the same machine the bytes are identical.
"""

from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from zugzwang_core.domain.canonical import hash_canonical

RENDERER_ID = "chess.board-png"
RENDERER_VERSION = "0.1.0"

DEFAULT_FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)

_PIECE_GLYPHS = {
    "K": "\u2654",
    "Q": "\u2655",
    "R": "\u2656",
    "B": "\u2657",
    "N": "\u2658",
    "P": "\u2659",
    "k": "\u265a",
    "q": "\u265b",
    "r": "\u265c",
    "b": "\u265d",
    "n": "\u265e",
    "p": "\u265f",
}

_SQUARE_LIGHT = (240, 217, 181)
_SQUARE_DARK = (181, 136, 99)
_LABEL_BG = (255, 255, 255)
_LABEL_FG = (60, 60, 60)
_WHITE_FILL = (255, 255, 255)
_WHITE_OUTLINE = (20, 20, 20)
_BLACK_FILL = (30, 30, 30)
_BLACK_OUTLINE = (235, 235, 235)


@dataclass(frozen=True, slots=True)
class BoardRenderSpec:
    """Controlled visual variables (MM-001 axes)."""

    theme: str = "default"
    orientation: Literal["white", "black"] = "white"
    coordinates: bool = True
    square_size_px: int = 60
    font_path: str = ""

    def with_orientation(self, value: Literal["white", "black"]) -> BoardRenderSpec:
        return replace(self, orientation=value)


@dataclass(frozen=True, slots=True)
class BoardPng:
    """Rendered PNG plus complete provenance metadata."""

    bytes: bytes
    mime: str = "image/png"
    width: int = 0
    height: int = 0
    content_sha256: str = ""
    metadata: dict[str, Any] = field(default_factory=lambda: {})

    def base64(self) -> str:
        return base64.b64encode(self.bytes).decode("ascii")

    def data_url(self) -> str:
        return f"data:{self.mime};base64,{self.base64()}"


def _default_font_path() -> str:
    for candidate in DEFAULT_FONT_PATHS:
        if Path(candidate).is_file():
            return candidate
    return ""


def _font_sha256(font_path: str) -> str:
    if not font_path:
        return ""
    return hashlib.sha256(Path(font_path).read_bytes()).hexdigest()


def _state_hash(fen: str) -> str:
    board_part, rest = [*fen.split(" ", 1), ""][:2]
    return hash_canonical({"board": board_part, "rest": rest})


def piece_symbols(fen: str) -> dict[str, str]:
    """Map square name (e.g. 'e4') to piece symbol, '.' for empty."""
    board_part = fen.split(" ")[0]
    symbols: dict[str, str] = {}
    file_idx = 0
    rank = 7
    for char in board_part:
        if char == "/":
            file_idx = 0
            rank -= 1
        elif char.isdigit():
            file_idx += int(char)
        else:
            square = f"{chr(ord('a') + file_idx)}{rank + 1}"
            symbols[square] = char
            file_idx += 1
    return symbols


def render_board_png(fen: str, spec: BoardRenderSpec | None = None) -> BoardPng:
    """Render ``fen`` into a deterministic PNG with full metadata."""
    from PIL import Image, ImageDraw, ImageFont

    spec = spec or BoardRenderSpec()
    if spec.square_size_px < 20 or spec.square_size_px > 400:
        raise ValueError("square_size_px must be between 20 and 400")
    font_path = spec.font_path or _default_font_path()
    font = ImageFont.truetype(font_path, int(spec.square_size_px * 0.72)) if font_path else None

    board_size = 8 * spec.square_size_px
    if spec.coordinates:
        board_size += 2 * spec.square_size_px

    image = Image.new("RGB", (board_size, board_size), "white")
    draw = ImageDraw.Draw(image)
    offset = spec.square_size_px if spec.coordinates else 0

    for rank in range(8):
        for file in range(8):
            display_rank = 7 - rank if spec.orientation == "white" else rank
            display_file = file if spec.orientation == "white" else 7 - file
            light = (display_rank + display_file) % 2 == 0
            fill = _SQUARE_LIGHT if light else _SQUARE_DARK
            x0 = offset + file * spec.square_size_px
            y0 = offset + rank * spec.square_size_px
            draw.rectangle(
                [x0, y0, x0 + spec.square_size_px - 1, y0 + spec.square_size_px - 1],
                fill=fill,
            )

    symbols = piece_symbols(fen)
    for square, symbol in symbols.items():
        if symbol == ".":
            continue
        file = ord(square[0]) - ord("a")
        rank = int(square[1]) - 1
        display_rank = 7 - rank if spec.orientation == "white" else rank
        display_file = file if spec.orientation == "white" else 7 - file
        center_x = offset + display_file * spec.square_size_px + spec.square_size_px // 2
        center_y = offset + display_rank * spec.square_size_px + spec.square_size_px // 2
        if font is not None:
            glyph = _PIECE_GLYPHS[symbol]
            anchor = "mm"
            outline_width = max(1, spec.square_size_px // 30)
            draw.text(
                (center_x, center_y),
                glyph,
                font=font,
                fill=_WHITE_FILL if symbol.isupper() else _BLACK_FILL,
                anchor=anchor,
                stroke_width=outline_width,
                stroke_fill=_WHITE_OUTLINE if symbol.isupper() else _BLACK_OUTLINE,
            )
        else:
            draw.text((center_x, center_y), symbol, fill="black", anchor="mm")

    if spec.coordinates:
        small = int(spec.square_size_px * 0.42)
        label_font = ImageFont.truetype(font_path, small) if font_path else None
        files = "abcdefgh"
        for index in range(8):
            display_index = index if spec.orientation == "white" else 7 - index
            label = files[display_index]
            x = offset + index * spec.square_size_px + spec.square_size_px // 2
            y = offset - spec.square_size_px // 2
            draw.text((x, y), label, font=label_font, fill=_LABEL_FG, anchor="mm")
            rank_label = str(8 - index if spec.orientation == "white" else index + 1)
            x_left = spec.square_size_px // 2
            y_row = offset + index * spec.square_size_px + spec.square_size_px // 2
            draw.text((x_left, y_row), rank_label, font=label_font, fill=_LABEL_FG, anchor="mm")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=9)
    payload = buffer.getvalue()
    content_sha256 = hashlib.sha256(payload).hexdigest()
    metadata: dict[str, Any] = {
        "renderer_id": RENDERER_ID,
        "renderer_version": RENDERER_VERSION,
        "theme": spec.theme,
        "orientation": spec.orientation,
        "coordinates": spec.coordinates,
        "square_size_px": spec.square_size_px,
        "width": image.width,
        "height": image.height,
        "font_path": font_path,
        "font_sha256": _font_sha256(font_path),
        "source_state_hash": _state_hash(fen),
        "source_fen_board": fen.split(" ")[0],
    }
    return BoardPng(
        bytes=payload,
        width=image.width,
        height=image.height,
        content_sha256=content_sha256,
        metadata=metadata,
    )
