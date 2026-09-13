"""
StaticChessBoard / LightChessBoard — Ultra-lightweight static chessboard widget.

Designed specifically for displaying chess positions (diagrams, thumbnails, puzzle lists,
opening trees, move history previews) with minimal memory footprint and zero interaction overhead.

Key features:
- QPainter-based direct rendering using MERIFONT.TTF glyphs.
- Shared global glyph pixmap cache across all instances of matching square size.
- Lazy font loading (registered once globally).
- No timers, no event filters, no drag/drop, no animation overhead.
- Supports FEN strings, chess.Board objects, custom themes, highlights, and offline pixmap rendering.
"""

import os
from typing import Optional, Dict, Union, Tuple
import chess

from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtCore import Qt, QRectF, QSize
from .models import PreviewConfig, BoardShape
from PyQt5.QtGui import (
    QPainter,
    QColor,
    QFont,
    QFontDatabase,
    QPainterPath,
    QBrush,
    QPixmap,
    QImage,
)

# ---------------------------------------------------------------------------
# Global font & pixmap caching for minimal memory footprint
# ---------------------------------------------------------------------------

_CACHED_FONT_FAMILY: Optional[str] = None

# Piece character mapping for MERIFONT.TTF (Merida font)
_PIECE_CHARS: Dict[Tuple[chess.PieceType, chess.Color], str] = {
    (chess.PAWN, chess.WHITE): "p",
    (chess.KNIGHT, chess.WHITE): "n",
    (chess.BISHOP, chess.WHITE): "b",
    (chess.ROOK, chess.WHITE): "r",
    (chess.QUEEN, chess.WHITE): "q",
    (chess.KING, chess.WHITE): "k",
    (chess.PAWN, chess.BLACK): "o",
    (chess.KNIGHT, chess.BLACK): "m",
    (chess.BISHOP, chess.BLACK): "v",
    (chess.ROOK, chess.BLACK): "t",
    (chess.QUEEN, chess.BLACK): "w",
    (chess.KING, chess.BLACK): "l",
}

# Shared cache across all instances: (font_family, int(sq_size)) -> Dict[(piece_type, color), QPixmap]
_GLOBAL_PIXMAP_CACHE: Dict[
    Tuple[str, int], Dict[Tuple[chess.PieceType, chess.Color], QPixmap]
] = {}


def _resolve_default_font_path() -> str:
    """Find MERIFONT.TTF relative to the package location."""
    candidate_paths = [
        os.path.join(os.path.dirname(__file__), "..", "experiments", "MERIFONT.TTF"),
        os.path.join(os.path.dirname(__file__), "MERIFONT.TTF"),
        os.path.join(os.path.dirname(__file__), "experiments", "MERIFONT.TTF"),
        os.path.abspath(os.path.join(os.getcwd(), "experiments", "MERIFONT.TTF")),
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            return os.path.abspath(path)
    return ""


def _get_or_load_font(font_path: Optional[str] = None) -> str:
    """Load the TTF font once and cache the family name."""
    global _CACHED_FONT_FAMILY
    if _CACHED_FONT_FAMILY is not None and not font_path:
        return _CACHED_FONT_FAMILY

    target_path = font_path or _resolve_default_font_path()
    if target_path and os.path.exists(target_path):
        font_id = QFontDatabase.addApplicationFont(target_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                if not font_path:
                    _CACHED_FONT_FAMILY = families[0]
                return families[0]

    return "Arial"


def _make_glyph_path(char: str, font: QFont, sq_size: float) -> QPainterPath:
    """Return a QPainterPath of *char* centered within a sq_size × sq_size cell."""
    raw = QPainterPath()
    raw.addText(0, 0, font, char)
    br = raw.boundingRect()
    dx = sq_size / 2.0 - (br.x() + br.width() / 2.0)
    dy = sq_size / 2.0 - (br.y() + br.height() / 2.0)
    centered = QPainterPath()
    centered.addText(dx, dy, font, char)
    return centered


def _get_cached_pixmaps(
    font_family: str, sq_size: int
) -> Dict[Tuple[chess.PieceType, chess.Color], QPixmap]:
    """Retrieve or build the 12 piece pixmaps for a given square size."""
    if sq_size < 1:
        return {}

    cache_key = (font_family, sq_size)
    if cache_key in _GLOBAL_PIXMAP_CACHE:
        return _GLOBAL_PIXMAP_CACHE[cache_key]

    cache: Dict[Tuple[chess.PieceType, chess.Color], QPixmap] = {}
    font = QFont(font_family)
    font.setPixelSize(max(1, int(sq_size * 0.85)))

    for (p_type, p_color), char in _PIECE_CHARS.items():
        path = _make_glyph_path(char, font, float(sq_size))

        pixmap = QPixmap(sq_size, sq_size)
        pixmap.fill(Qt.transparent)

        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        if p_color == chess.WHITE:
            polys = path.toSubpathPolygons()
            if polys:
                outer = max(
                    polys,
                    key=lambda poly: (
                        poly.boundingRect().width() * poly.boundingRect().height()
                    ),
                )
                outer_path = QPainterPath()
                outer_path.addPolygon(outer)
                p.fillPath(outer_path, QBrush(QColor("#ffffff")))
            p.fillPath(path, QBrush(QColor("#000000")))
        else:
            p.fillPath(path, QBrush(QColor("#000000")))

        p.end()
        cache[(p_type, p_color)] = pixmap

    _GLOBAL_PIXMAP_CACHE[cache_key] = cache
    return cache


def _parse_color(
    c: Union[QColor, str, Tuple[int, int, int], Tuple[int, int, int, int]],
) -> QColor:
    """Parse color into a QColor instance."""
    if isinstance(c, QColor):
        return c
    if isinstance(c, (tuple, list)):
        return QColor(*c)
    if isinstance(c, str):
        if c.startswith("rgba"):
            nums = c[5:-1].split(",")
            return QColor(
                int(nums[0]), int(nums[1]), int(nums[2]), int(float(nums[3]) * 255)
            )
        if c.startswith("rgb"):
            nums = c[4:-1].split(",")
            return QColor(int(nums[0]), int(nums[1]), int(nums[2]))
        return QColor(c)
    return QColor("#ffffff")


# ---------------------------------------------------------------------------
# StaticChessBoard Widget
# ---------------------------------------------------------------------------


class StaticChessBoard(QWidget):
    """
    Lightweight, non-interactive chessboard widget for displaying static positions.

    Ideal for:
    - Thumbnails in puzzle or game lists
    - Static diagrams in documentation or analysis
    - Opening explorer tree previews
    - Highly scalable grid views with low memory footprint
    """

    def __init__(
        self,
        position: Union[str, chess.Board, None] = None,
        size: Optional[Union[int, Tuple[int, int]]] = None,
        square_size: Optional[float] = None,
        orientation: chess.Color = chess.WHITE,
        light_color: Union[QColor, str] = "#f0d9b5",
        dark_color: Union[QColor, str] = "#b58863",
        show_coordinates: bool = False,
        font_file: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        # Disable interactive mouse tracking to minimize event overhead
        self.setAttribute(Qt.WA_StaticContents, True)
        self.setMouseTracking(False)

        # Board position
        self._board: chess.Board = chess.Board()
        if position is not None:
            self.set_position(position)

        # Display settings
        self._orientation: chess.Color = orientation
        self._light_color: QColor = _parse_color(light_color)
        self._dark_color: QColor = _parse_color(dark_color)
        self._show_coordinates: bool = show_coordinates
        self._highlights: Dict[chess.Square, QColor] = {}
        self._last_move: Optional[chess.Move] = None
        self._last_move_color: QColor = QColor(255, 255, 0, 100)
        self._preview: Optional[PreviewConfig] = None

        # Font configuration
        self._font_family: str = _get_or_load_font(font_file)

        # Size policy
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        # Sizing
        if square_size is not None:
            self.set_square_size(square_size)
        elif size is not None:
            self.set_board_size(size)
        else:
            self.setMinimumSize(64, 64)

    # -----------------------------------------------------------------------
    # Properties & Getters / Setters
    # -----------------------------------------------------------------------

    @property
    def fen(self) -> str:
        return self._board.fen()

    @fen.setter
    def fen(self, value: str) -> None:
        self.set_fen(value)

    @property
    def board(self) -> chess.Board:
        return self._board

    @board.setter
    def board(self, value: chess.Board) -> None:
        self.set_board(value)

    @property
    def orientation(self) -> chess.Color:
        return self._orientation

    @orientation.setter
    def orientation(self, value: chess.Color) -> None:
        self.set_orientation(value)

    def set_fen(self, fen: str) -> None:
        """Set board position from a FEN string."""
        self._board = chess.Board(fen)
        self.update()

    def get_fen(self) -> str:
        """Get current FEN string."""
        return self._board.fen()

    def set_board(self, board: chess.Board) -> None:
        """Set board position from a chess.Board instance (creates a lightweight copy)."""
        self._board = board.copy(stack=False)
        self.update()

    def get_board(self) -> chess.Board:
        """Get the current chess.Board."""
        return self._board

    def set_position(self, position: Union[str, chess.Board]) -> None:
        """Set position from either a FEN string or a chess.Board instance."""
        if isinstance(position, str):
            self.set_fen(position)
        elif isinstance(position, chess.Board):
            self.set_board(position)
        else:
            raise TypeError(f"Expected str or chess.Board, got {type(position)}")

    def set_orientation(self, orientation: chess.Color) -> None:
        """Set board orientation (chess.WHITE or chess.BLACK)."""
        if self._orientation != orientation:
            self._orientation = orientation
            self.update()

    def flip(self) -> None:
        """Toggle board orientation between White and Black."""
        self.set_orientation(not self._orientation)

    def set_theme(
        self,
        light_color: Union[QColor, str],
        dark_color: Union[QColor, str],
    ) -> None:
        """Set the light and dark square colors."""
        self._light_color = _parse_color(light_color)
        self._dark_color = _parse_color(dark_color)
        self.update()

    def set_coordinates(self, show: bool) -> None:
        """Toggle coordinate rank/file display."""
        if self._show_coordinates != show:
            self._show_coordinates = show
            self.update()

    def set_highlight(
        self, square: Union[chess.Square, str], color: Union[QColor, str]
    ) -> None:
        """Add or update a highlighted square."""
        sq = chess.parse_square(square) if isinstance(square, str) else square
        self._highlights[sq] = _parse_color(color)
        self.update()

    def clear_highlights(self) -> None:
        """Clear all custom square highlights."""
        if self._highlights:
            self._highlights.clear()
            self.update()

    def set_last_move(
        self,
        move: Optional[Union[chess.Move, str]],
        color: Optional[Union[QColor, str]] = None,
    ) -> None:
        """Set or clear a last-move highlight."""
        if isinstance(move, str):
            self._last_move = chess.Move.from_uci(move)
        else:
            self._last_move = move

        if color is not None:
            self._last_move_color = _parse_color(color)
        self.update()

    def set_preview(
        self,
        fen: str,
        last_move: Optional[Union[chess.Move, str]] = None,
        shapes: Optional[list] = None,
        opacity: float = 0.80,
        dim_board: bool = False,
    ):
        """Set a temporary ghost/preview position without altering the real game state."""
        parsed_last_move = None
        if isinstance(last_move, str):
            parsed_last_move = chess.Move.from_uci(last_move)
        elif isinstance(last_move, chess.Move):
            parsed_last_move = last_move

        parsed_shapes = []
        if shapes:
            for s in shapes:
                if isinstance(s, dict):
                    s_copy = s.copy()
                    if "orig" in s_copy and isinstance(s_copy["orig"], str):
                        s_copy["orig"] = chess.parse_square(s_copy["orig"])
                    if "dest" in s_copy and isinstance(s_copy["dest"], str):
                        s_copy["dest"] = chess.parse_square(s_copy["dest"])
                    parsed_shapes.append(BoardShape(**s_copy))
                elif isinstance(s, BoardShape):
                    parsed_shapes.append(s)

        self._preview = PreviewConfig(
            fen=fen,
            last_move=parsed_last_move,
            shapes=parsed_shapes,
            opacity=opacity,
            dim_board=dim_board,
        )
        self.update()

    def clear_preview(self):
        """Clear the preview position and return to the real game state immediately."""
        if self._preview is not None:
            self._preview = None
            self.update()

    @property
    def is_previewing(self) -> bool:
        """Returns True if a temporary preview is currently active."""
        return self._preview is not None

    def set_board_size(self, size: Union[int, Tuple[int, int]]) -> None:
        """Set fixed board dimensions in pixels."""
        if isinstance(size, (int, float)):
            s = int(size)
            self.setFixedSize(s, s)
        elif isinstance(size, (tuple, list)) and len(size) == 2:
            self.setFixedSize(int(size[0]), int(size[1]))

    def set_square_size(self, sq_size: float) -> None:
        """Set fixed board dimensions based on individual square size."""
        total = int(round(sq_size * 8))
        self.setFixedSize(total, total)

    # -----------------------------------------------------------------------
    # Size hints for responsive layouts
    # -----------------------------------------------------------------------

    def sizeHint(self) -> QSize:
        return QSize(240, 240)

    def minimumSizeHint(self) -> QSize:
        return QSize(64, 64)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        return w

    # -----------------------------------------------------------------------
    # Painting
    # -----------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        self._paint_board(painter, self.width(), self.height())
        painter.end()

    def _paint_board(self, painter: QPainter, width: int, height: int) -> None:
        """Core rendering logic, usable by paintEvent and offline pixmap rendering."""
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        board_size = min(width, height)
        if board_size <= 0:
            return

        sq_size = board_size / 8.0
        offset_x = (width - board_size) / 2.0
        offset_y = (height - board_size) / 2.0

        int_sq = max(1, int(round(sq_size)))
        pixmaps = _get_cached_pixmaps(self._font_family, int_sq)

        # 1. Squares
        for rank in range(8):
            for file in range(8):
                if self._orientation == chess.WHITE:
                    col = file
                    row = 7 - rank
                else:
                    col = 7 - file
                    row = rank

                x = offset_x + col * sq_size
                y = offset_y + row * sq_size
                is_light = (file + rank) % 2 != 0
                color = self._light_color if is_light else self._dark_color
                painter.fillRect(QRectF(x, y, sq_size, sq_size), color)

        # 2. Dimming & Highlights
        if self._preview is not None:
            if self._preview.dim_board:
                painter.fillRect(
                    QRectF(offset_x, offset_y, board_size, board_size),
                    QColor(0, 0, 0, 25),
                )

            if self._preview.last_move is not None:
                for sq in (
                    self._preview.last_move.from_square,
                    self._preview.last_move.to_square,
                ):
                    col, row = self._square_to_col_row(sq)
                    painter.fillRect(
                        QRectF(
                            offset_x + col * sq_size,
                            offset_y + row * sq_size,
                            sq_size,
                            sq_size,
                        ),
                        self._last_move_color,
                    )
        else:
            if self._last_move is not None:
                for sq in (self._last_move.from_square, self._last_move.to_square):
                    col, row = self._square_to_col_row(sq)
                    painter.fillRect(
                        QRectF(
                            offset_x + col * sq_size,
                            offset_y + row * sq_size,
                            sq_size,
                            sq_size,
                        ),
                        self._last_move_color,
                    )

            for sq, h_color in self._highlights.items():
                col, row = self._square_to_col_row(sq)
                painter.fillRect(
                    QRectF(
                        offset_x + col * sq_size,
                        offset_y + row * sq_size,
                        sq_size,
                        sq_size,
                    ),
                    h_color,
                )

        # 3. Pieces (iterate occupied squares of preview board or real board)
        active_board = (
            chess.Board(self._preview.fen) if self._preview is not None else self._board
        )
        if self._preview is not None:
            painter.save()
            painter.setOpacity(self._preview.opacity)

        for sq, piece in active_board.piece_map().items():
            col, row = self._square_to_col_row(sq)
            pix = pixmaps.get((piece.piece_type, piece.color))
            if pix is not None and not pix.isNull():
                dest_rect = QRectF(
                    offset_x + col * sq_size, offset_y + row * sq_size, sq_size, sq_size
                )
                painter.drawPixmap(dest_rect.toRect(), pix)

        if self._preview is not None:
            painter.restore()

        # 4. Optional coordinates
        if self._show_coordinates and sq_size >= 16:
            self._draw_coordinates(painter, offset_x, offset_y, sq_size)

    def _square_to_col_row(self, square: chess.Square) -> Tuple[int, int]:
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        if self._orientation == chess.WHITE:
            return file, 7 - rank
        return 7 - file, rank

    def _draw_coordinates(
        self, painter: QPainter, offset_x: float, offset_y: float, sq_size: float
    ) -> None:
        """Draw minimal rank/file coordinates inside corner squares."""
        coord_font = QFont("Arial", max(7, int(sq_size * 0.16)), QFont.Bold)
        painter.setFont(coord_font)

        files = ["a", "b", "c", "d", "e", "f", "g", "h"]
        ranks = ["1", "2", "3", "4", "5", "6", "7", "8"]
        if self._orientation == chess.BLACK:
            files.reverse()
            ranks.reverse()

        margin = max(2.0, sq_size * 0.04)

        for col, f_char in enumerate(files):
            is_light = (col + (0 if self._orientation == chess.WHITE else 7)) % 2 != 0
            text_color = self._dark_color if is_light else self._light_color
            painter.setPen(text_color)
            r = QRectF(
                offset_x + col * sq_size,
                offset_y + 7 * sq_size,
                sq_size - margin,
                sq_size - margin,
            )
            painter.drawText(r, Qt.AlignRight | Qt.AlignBottom, f_char)

        for row, r_char in enumerate(reversed(ranks)):
            is_light = (row) % 2 != 0
            text_color = self._dark_color if is_light else self._light_color
            painter.setPen(text_color)
            r = QRectF(
                offset_x + margin,
                offset_y + row * sq_size + margin,
                sq_size,
                sq_size,
            )
            painter.drawText(r, Qt.AlignLeft | Qt.AlignTop, r_char)

    # -----------------------------------------------------------------------
    # Headless / Offline Rendering
    # -----------------------------------------------------------------------

    def render_to_pixmap(
        self, width: int = 400, height: Optional[int] = None
    ) -> QPixmap:
        """Render the current board position directly into a standalone QPixmap."""
        h = width if height is None else height
        pixmap = QPixmap(width, h)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        self._paint_board(p, width, h)
        p.end()
        return pixmap

    def render_to_image(self, width: int = 400, height: Optional[int] = None) -> QImage:
        """Render the current board position directly into a QImage."""
        return self.render_to_pixmap(width, height).toImage()


# Alias for intuitive discovery
LightChessBoard = StaticChessBoard
