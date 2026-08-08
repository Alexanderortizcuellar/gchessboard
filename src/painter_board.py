"""
PainterChessBoard — QPainter + MERIFONT.TTF chessboard implementation.

Architecture:
    QWidget
        └── QPainter  (paintEvent)
                ├── board squares + highlights
                ├── shapes (arrows, circles, crosses)
                ├── pieces  (cached QPixmap from MERIFONT.TTF)
                ├── animated piece
                ├── dragged piece
                └── coordinates

Rendering pipeline:
    MERIFONT.TTF → QFont → glyph path → rasterize once → QPixmap cache
    During repaint: QPainter.drawPixmap() from cache (no re-rasterize).

Piece cache is regenerated only on:
    • initial setup
    • square-size change (window resize)
    • font change

This module is architecturally independent from the QGraphicsView/SVG implementation.
It shares the same BoardState / models from src.models and exposes an identical
public API so that callers can swap BoardView ↔ PainterChessBoard without rewriting
application code.
"""

import os
import math
import chess
from typing import Optional, Dict, List

from PyQt5.QtWidgets import QWidget, QApplication, QDialog
from PyQt5.QtCore import (
    Qt,
    QRectF,
    QPointF,
    QTimer,
    pyqtSignal,
    QVariantAnimation,
    QEasingCurve,
)
from PyQt5.QtGui import (
    QPainter,
    QColor,
    QFont,
    QFontDatabase,
    QPainterPath,
    QBrush,
    QPen,
    QPixmap,
    QRadialGradient,
)

from .models import BoardState, BoardHighlight, BoardShape, AnimationConfig


# ---------------------------------------------------------------------------
# Piece pixmap cache
# ---------------------------------------------------------------------------

# Merida font character mapping (same as vector_chessboard.py / painter_chessboard.py)
_PIECE_CHARS: Dict = {
    (chess.PAWN,   chess.WHITE): 'p',
    (chess.KNIGHT, chess.WHITE): 'n',
    (chess.BISHOP, chess.WHITE): 'b',
    (chess.ROOK,   chess.WHITE): 'r',
    (chess.QUEEN,  chess.WHITE): 'q',
    (chess.KING,   chess.WHITE): 'k',
    (chess.PAWN,   chess.BLACK): 'o',
    (chess.KNIGHT, chess.BLACK): 'm',
    (chess.BISHOP, chess.BLACK): 'v',
    (chess.ROOK,   chess.BLACK): 't',
    (chess.QUEEN,  chess.BLACK): 'w',
    (chess.KING,   chess.BLACK): 'l',
}


def _load_font(font_path: str) -> str:
    """Load a font file and return its family name (falls back to 'Arial')."""
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return families[0]
    return "Arial"


def _make_glyph_path(char: str, font: QFont, sq_size: float) -> QPainterPath:
    """Return a QPainterPath of *char* centered within a sq_size×sq_size cell."""
    raw = QPainterPath()
    raw.addText(0, 0, font, char)
    br = raw.boundingRect()
    dx = sq_size / 2.0 - (br.x() + br.width()  / 2.0)
    dy = sq_size / 2.0 - (br.y() + br.height() / 2.0)
    centered = QPainterPath()
    centered.addText(dx, dy, font, char)
    return centered


def _build_pixmap_cache(font_family: str, sq_size: float) -> Dict:
    """
    Rasterize all 12 chess piece glyphs into QPixmaps.

    White pieces: outer contour filled white, then black glyph drawn on top
                  (because Merida white glyphs are hollow outlines).
    Black pieces: filled solid black.
    """
    cache: Dict = {}
    font = QFont(font_family)
    font.setPixelSize(max(1, int(sq_size * 0.85)))

    sz = int(sq_size)
    if sz < 1:
        return cache

    for (p_type, p_color), char in _PIECE_CHARS.items():
        path = _make_glyph_path(char, font, sq_size)

        pixmap = QPixmap(sz, sz)
        pixmap.fill(Qt.transparent)

        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        if p_color == chess.WHITE:
            # Extract the largest sub-polygon (outer contour) and fill white
            polys = path.toSubpathPolygons()
            if polys:
                outer = max(polys, key=lambda poly: (
                    poly.boundingRect().width() * poly.boundingRect().height()
                ))
                outer_path = QPainterPath()
                outer_path.addPolygon(outer)
                p.fillPath(outer_path, QBrush(QColor("#ffffff")))
            # Draw the full glyph (outlines + inner details) in black on top
            p.fillPath(path, QBrush(QColor("#000000")))
        else:
            p.fillPath(path, QBrush(QColor("#000000")))

        p.end()
        cache[(p_type, p_color)] = pixmap

    return cache


# ---------------------------------------------------------------------------
# Helper: parse color strings (same logic as scene.py)
# ---------------------------------------------------------------------------

def _parse_color(color_str: str) -> QColor:
    if color_str.startswith("rgba"):
        content = color_str[color_str.find("(") + 1: color_str.find(")")]
        parts = [p.strip() for p in content.split(",")]
        if len(parts) == 4:
            r, g, b = map(int, parts[:3])
            a = int(float(parts[3]) * 255)
            return QColor(r, g, b, a)
    return QColor(color_str)


# ---------------------------------------------------------------------------
# PainterChessBoard — the widget
# ---------------------------------------------------------------------------

class PainterChessBoard(QWidget):
    """
    QPainter-based chessboard widget.

    Drop-in replacement for BoardView (QGraphicsView) with identical public API:
        .set(**kwargs)
        .set_fen(fen)
        .flip_orientation()
        .move_piece(move)
        .set_view_only(enabled)
        .setpiece_at(square, piece, color)
        .set_piece_at(square, piece, color)   # alias
        .set_state(state)

    Signals:
        moveMade(chess.Move)
        pieceDropped(chess.Move)
        squareClicked(chess.Square)
        fenChanged(str)
        selectionChanged(Optional[chess.Square])
    """

    moveMade       = pyqtSignal(chess.Move)
    pieceDropped   = pyqtSignal(chess.Move)
    squareClicked  = pyqtSignal(chess.Square)
    fenChanged     = pyqtSignal(str)
    selectionChanged = pyqtSignal(object)

    # Path to MERIFONT.TTF (relative to this file's directory)
    _DEFAULT_FONT_FILE = os.path.join(
        os.path.dirname(__file__), "..", "experiments", "MERIFONT.TTF"
    )

    def __init__(self, font_file: str = None, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 160)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        # --- Board state (shared data model) ---
        self._state = BoardState()
        self._square_size: float = 60.0

        # --- Font / piece pixmap cache ---
        font_path = font_file or self._DEFAULT_FONT_FILE
        self._font_family: str = _load_font(font_path)
        self._pixmap_cache: Dict = {}
        self._cache_sq_size: int = 0

        # --- Interaction state ---
        self._drag_square: Optional[chess.Square] = None
        self._drag_pos: Optional[QPointF] = None
        self._drag_start_pos_widget: Optional[QPointF] = None  # for editable off-board
        self._click_origin: Optional[chess.Square] = None
        self._suppress_anim_square: Optional[chess.Square] = None

        # Shape drawing via right-click
        self._is_drawing_shape: bool = False
        self._right_click_start_square: Optional[chess.Square] = None
        self._current_draw_target_square: Optional[chess.Square] = None

        # --- Animation ---
        self._anim: Optional[QVariantAnimation] = None
        self._anim_progress: float = 0.0
        self._anim_piece: Optional[chess.Piece] = None
        self._anim_from_sq: Optional[chess.Square] = None
        self._anim_to_sq: Optional[chess.Square] = None

    # -----------------------------------------------------------------------
    # Public API  (identical to BoardView)
    # -----------------------------------------------------------------------

    def set(self, **kwargs):
        """Unified configuration method — mirrors BoardView.set()."""
        for key, value in kwargs.items():
            if key == "fen":
                old_fen = self._state.fen
                self._state.fen = value
                if old_fen != value:
                    # Trigger animation before _handle_fen_change clears state.
                    # Skip if the destination square was just dragged there
                    # (_suppress_anim_square is set by mouseReleaseEvent).
                    if (
                        self._state.animation.enabled
                        and not self._state.editable
                        and old_fen is not None
                    ):
                        self._try_start_move_animation(
                            chess.Board(old_fen), chess.Board(value)
                        )
                    self._handle_fen_change()
            elif key == "orientation":
                self._state.orientation = value
            elif key == "viewOnly":
                self._state.view_only = value
            elif key == "lastMove":
                self._state.last_move = value
            elif key == "selected":
                self._state.selected = value
            elif key == "editable":
                self._state.editable = value
            elif key == "drawShapes":
                self._state.draw_shapes = value
            elif key == "customHighlights" and isinstance(value, dict):
                self._state.custom_highlights = {}
                for sq, col in value.items():
                    parsed_sq = chess.parse_square(sq) if isinstance(sq, str) else sq
                    if isinstance(col, str):
                        self._state.custom_highlights[parsed_sq] = BoardHighlight(color=col, square=parsed_sq)
                    elif isinstance(col, BoardHighlight):
                        self._state.custom_highlights[parsed_sq] = col
                    elif isinstance(col, dict):
                        parsed_color = col.get("color", "rgba(255, 0, 0, 0.5)")
                        self._state.custom_highlights[parsed_sq] = BoardHighlight(color=parsed_color, square=parsed_sq)
            elif key == "shapes" and isinstance(value, list):
                parsed_shapes = []
                for s in value:
                    if isinstance(s, dict):
                        s_copy = s.copy()
                        if "orig" in s_copy and isinstance(s_copy["orig"], str):
                            s_copy["orig"] = chess.parse_square(s_copy["orig"])
                        if "dest" in s_copy and isinstance(s_copy["dest"], str):
                            s_copy["dest"] = chess.parse_square(s_copy["dest"])
                        parsed_shapes.append(BoardShape(**s_copy))
                    elif isinstance(s, BoardShape):
                        parsed_shapes.append(s)
                self._state.shapes = parsed_shapes
            elif key == "theme" and isinstance(value, dict):
                new_theme = self._state.theme.copy()
                new_theme.update(value)
                self._state.theme = new_theme
            elif key == "movable" and isinstance(value, dict):
                for mkey, mvalue in value.items():
                    if hasattr(self._state.movable, mkey):
                        setattr(self._state.movable, mkey, mvalue)
            elif key == "premovable" and isinstance(value, dict):
                for pkey, pvalue in value.items():
                    if hasattr(self._state.premovable, pkey):
                        setattr(self._state.premovable, pkey, pvalue)
            elif key == "animation" and isinstance(value, dict):
                for akey, avalue in value.items():
                    if hasattr(self._state.animation, akey):
                        setattr(self._state.animation, akey, avalue)
            elif hasattr(self._state, key):
                setattr(self._state, key, value)

        self.update()

    def set_fen(self, fen: str):
        self.set(fen=fen)
        self.fenChanged.emit(fen)

    def set_state(self, state: BoardState):
        self._state = state
        self.update()
        self.fenChanged.emit(self._state.fen)

    def move_piece(self, move: chess.Move):
        board = chess.Board(self._state.fen)
        if move in board.legal_moves:
            piece = board.piece_at(move.from_square)
            board.push(move)
            self._state.fen = board.fen()
            self._state.last_move = move
            self._state.shapes.clear()
            self._state.custom_highlights.clear()
            anim_cfg = self._state.animation
            if anim_cfg.enabled and not self._state.editable:
                self._start_animation(move.from_square, move.to_square, piece)
            self.update()
            self.moveMade.emit(move)

    def flip_orientation(self):
        self._state.orientation = (
            chess.BLACK if self._state.orientation == chess.WHITE else chess.WHITE
        )
        self.update()

    def set_view_only(self, enabled: bool):
        self._state.view_only = enabled

    def setpiece_at(
        self,
        square: chess.Square,
        piece: Optional[chess.Piece],
        color: Optional[chess.Color] = None,
    ):
        """Sets a piece at a given square. Accepts chess.Piece, symbol str, PieceType int, or None."""
        if piece is None:
            p_obj = None
        elif isinstance(piece, chess.Piece):
            p_obj = piece
        elif isinstance(piece, str):
            p_obj = chess.Piece.from_symbol(piece)
        elif isinstance(piece, int):
            if color is None:
                color = chess.WHITE
            p_obj = chess.Piece(piece, color)
        else:
            p_obj = piece

        board = chess.Board(self._state.fen)
        board.set_piece_at(square, p_obj)
        self.set(fen=board.fen())

    def set_piece_at(
        self,
        square: chess.Square,
        piece: Optional[chess.Piece],
        color: Optional[chess.Color] = None,
    ):
        """Alias for setpiece_at."""
        self.setpiece_at(square, piece, color)

    def set_font_file(self, font_path: str):
        """Replace the chess font and invalidate the pixmap cache."""
        self._font_family = _load_font(font_path)
        self._cache_sq_size = 0
        self._pixmap_cache.clear()
        self.update()

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _get_pixmap(self, piece: chess.Piece) -> Optional[QPixmap]:
        sq = int(self._square_size)
        if sq != self._cache_sq_size or not self._pixmap_cache:
            self._pixmap_cache = _build_pixmap_cache(self._font_family, self._square_size)
            self._cache_sq_size = sq
        return self._pixmap_cache.get((piece.piece_type, piece.color))

    def _square_to_col_row(self, square: chess.Square):
        """Return (col, row) pixel grid coords for *square* given current orientation."""
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        if self._state.orientation == chess.WHITE:
            col = file
            row = 7 - rank
        else:
            col = 7 - file
            row = rank
        return col, row

    def _square_to_point(self, square: chess.Square) -> QPointF:
        col, row = self._square_to_col_row(square)
        return QPointF(col * self._square_size, row * self._square_size)

    def _point_to_square(self, pos: QPointF) -> Optional[chess.Square]:
        sq_size = self._square_size
        if sq_size <= 0:
            return None
        col = int(pos.x() // sq_size)
        row = int(pos.y() // sq_size)
        if not (0 <= col < 8 and 0 <= row < 8):
            return None
        if self._state.orientation == chess.WHITE:
            file = col
            rank = 7 - row
        else:
            file = 7 - col
            rank = row
        return chess.square(file, rank)

    def get_square_at(self, pos) -> Optional[chess.Square]:
        """Accept QPoint or QPointF."""
        return self._point_to_square(QPointF(pos))

    def get_visual_board(self) -> chess.Board:
        """Returns the board predicted by the current premove queue."""
        if self._state.editable:
            return chess.Board(self._state.fen)
        board = chess.Board(self._state.fen)
        color = self._state.movable.color

        if color is None:
            if self._state.last_sent_premove:
                if self._state.last_sent_premove in board.legal_moves:
                    board.push(self._state.last_sent_premove)
            for pm in self._state.premoves:
                if pm in board.legal_moves:
                    board.push(pm)
                else:
                    break
            return board

        if self._state.last_sent_premove:
            if self._state.last_sent_premove in board.legal_moves:
                board.push(self._state.last_sent_premove)

        for pm in self._state.premoves:
            board.turn = color
            if pm in board.legal_moves:
                board.push(pm)
            else:
                break

        board.turn = color
        return board

    def _prune_premoves(self):
        if self._state.editable:
            return
        board = chess.Board(self._state.fen)
        color = self._state.movable.color
        if color is None:
            return
        if self._state.last_sent_premove:
            if self._state.last_sent_premove in board.legal_moves:
                board.push(self._state.last_sent_premove)
        valid_queue = []
        for pm in self._state.premoves:
            board.turn = color
            if pm in board.legal_moves:
                board.push(pm)
                valid_queue.append(pm)
            else:
                break
        self._state.premoves = valid_queue

    def _handle_fen_change(self, shapes_passed=False, highlights_passed=False):
        if not shapes_passed:
            self._state.shapes.clear()
        if not highlights_passed:
            self._state.custom_highlights.clear()
        if self._state.editable:
            self._state.last_sent_premove = None
            return
        board = chess.Board(self._state.fen)
        is_our_turn = (
            self._state.movable.color is None
            or board.turn == self._state.movable.color
        )
        if self._state.premoves and is_our_turn:
            premove = self._state.premoves.pop(0)
            if premove in board.legal_moves:
                self._state.last_sent_premove = premove
                QTimer.singleShot(0, lambda: self.moveMade.emit(premove))
            else:
                self._state.premoves.clear()
                self._state.last_sent_premove = None
                self.update()
        else:
            self._state.last_sent_premove = None

    def _can_move_piece(self, square: chess.Square, board: chess.Board) -> bool:
        if self._state.movable.free:
            return True
        piece = board.piece_at(square)
        if piece:
            if (
                self._state.movable.color is None
                or piece.color == self._state.movable.color
            ):
                return True
        return False

    def _is_move_valid(self, move: chess.Move, board: chess.Board) -> bool:
        if self._state.movable.free:
            return True
        if self._state.movable.dests and not self._state.premoves:
            if move.from_square in self._state.movable.dests:
                return move.to_square in self._state.movable.dests[move.from_square]
        return move in board.legal_moves

    def _create_move(
        self, from_sq: chess.Square, to_sq: chess.Square, board: chess.Board
    ) -> chess.Move:
        move = chess.Move(from_sq, to_sq)
        piece = board.piece_at(from_sq)
        if piece and piece.piece_type == chess.PAWN:
            if (chess.square_rank(to_sq) == 7 and piece.color == chess.WHITE) or (
                chess.square_rank(to_sq) == 0 and piece.color == chess.BLACK
            ):
                move.promotion = self._ask_promotion(piece.color)
        return move

    def _ask_promotion(self, color: chess.Color) -> chess.PieceType:
        """Show promotion dialog. Falls back to QUEEN if dialog unavailable."""
        try:
            from .promotion import PromotionDialog
            result_holder = [chess.QUEEN]
            dialog = PromotionDialog(color, self)
            dialog.pieceSelected.connect(lambda t: result_holder.__setitem__(0, t))
            dialog.exec_()
            return result_holder[0]
        except Exception:
            return chess.QUEEN

    # -----------------------------------------------------------------------
    # Animation
    # -----------------------------------------------------------------------

    def _start_animation(
        self,
        from_sq: chess.Square,
        to_sq: chess.Square,
        piece: chess.Piece,
    ):
        if self._anim:
            self._anim.stop()
            self._anim = None

        self._anim_piece = piece
        self._anim_from_sq = from_sq
        self._anim_to_sq = to_sq
        self._anim_progress = 0.0

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(self._state.animation.duration)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.valueChanged.connect(self._on_anim_value)
        anim.finished.connect(self._on_anim_finished)
        anim.start()
        self._anim = anim

    def _on_anim_value(self, value):
        self._anim_progress = float(value)
        self.update()

    def _on_anim_finished(self):
        self._anim = None
        self._anim_piece = None
        self._anim_from_sq = None
        self._anim_to_sq = None
        self._anim_progress = 0.0
        self.update()

    def _try_start_move_animation(
        self, old_board: chess.Board, new_board: chess.Board
    ):
        """Detect the moved piece and start animation between old and new FEN."""
        disappeared, appeared = [], []
        for sq in chess.SQUARES:
            p_old = old_board.piece_at(sq)
            p_new = new_board.piece_at(sq)
            if p_old != p_new:
                if p_old is not None and (p_new is None or p_new.color != p_old.color):
                    disappeared.append((sq, p_old))
                if p_new is not None and (p_old is None or p_old.color != p_new.color):
                    appeared.append((sq, p_new))

        from_sq = to_sq = piece = None
        for d_sq, d_piece in disappeared:
            for a_sq, a_piece in appeared:
                if d_piece.piece_type == a_piece.piece_type and d_piece.color == a_piece.color:
                    from_sq, to_sq, piece = d_sq, a_sq, a_piece
                    break
            if from_sq is not None:
                break

        if from_sq is not None and to_sq is not None and piece is not None:
            if to_sq == self._suppress_anim_square:
                # Piece was just dragged here — no animation needed
                self._suppress_anim_square = None
                return
            self._suppress_anim_square = None
            self._start_animation(from_sq, to_sq, piece)

    # -----------------------------------------------------------------------
    # paintEvent — main rendering method
    # -----------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        sq = self._square_size
        if sq <= 0:
            return

        # Ensure pixmap cache is ready
        if int(sq) != self._cache_sq_size or not self._pixmap_cache:
            self._pixmap_cache = _build_pixmap_cache(self._font_family, sq)
            self._cache_sq_size = int(sq)

        theme = self._state.theme
        light_color = _parse_color(theme.get("light", "#dee3e6"))
        dark_color  = _parse_color(theme.get("dark",  "#8ca2ad"))

        visual_board = self.get_visual_board()
        true_board = chess.Board(self._state.fen)

        # 1. Draw squares
        self._draw_squares(painter, sq, light_color, dark_color)

        # 2. Highlights (last move, selected, custom)
        self._draw_highlights(painter, sq, theme, true_board, visual_board)

        # 3. Shapes (arrows, circles, crosses)
        self._draw_shapes(painter, sq)

        # 4. Static pieces
        self._draw_pieces(painter, sq, visual_board)

        # 5. Animated piece
        self._draw_animated_piece(painter, sq)

        # 6. Dragged piece
        self._draw_dragged_piece(painter, sq, visual_board)

        # 7. Coordinates
        self._draw_coordinates(painter, sq, light_color, dark_color)

    # -----------------------------------------------------------------------
    # Draw helpers
    # -----------------------------------------------------------------------

    def _draw_squares(self, painter, sq, light_color, dark_color):
        for rank in range(8):
            for file in range(8):
                if self._state.orientation == chess.WHITE:
                    sq_file = file
                    sq_rank = 7 - rank
                else:
                    sq_file = 7 - file
                    sq_rank = rank
                is_light = (sq_file + sq_rank) % 2 != 0
                color = light_color if is_light else dark_color
                painter.fillRect(QRectF(file * sq, rank * sq, sq, sq), color)

    def _draw_highlights(self, painter, sq, theme, true_board, visual_board):
        last_move_color = _parse_color(theme.get("lastMove", "rgba(255,255,0,0.5)"))
        selected_color  = _parse_color(theme.get("selected",  "rgba(0,0,255,0.4)"))
        premove_color   = _parse_color(theme.get("premove",   "rgba(20,100,200,0.5)"))
        check_color     = _parse_color(theme.get("check",     "rgba(255,0,0,0.8)"))

        # Last move
        if self._state.last_move:
            for s in (self._state.last_move.from_square, self._state.last_move.to_square):
                self._fill_square(painter, s, sq, last_move_color)

        # Selected square
        if self._state.selected is not None:
            self._fill_square(painter, self._state.selected, sq, selected_color)

        # Premove squares
        for pm in self._state.premoves:
            self._fill_square(painter, pm.from_square, sq, premove_color)
            self._fill_square(painter, pm.to_square,   sq, premove_color)

        # Check highlight (radial gradient)
        if not self._state.editable and true_board.is_check():
            king_sq = true_board.king(true_board.turn)
            if king_sq is not None:
                col, row = self._square_to_col_row(king_sq)
                cx = col * sq + sq / 2.0
                cy = row * sq + sq / 2.0
                grad = QRadialGradient(cx, cy, sq / 2.0)
                c1 = QColor(check_color)
                c2 = QColor(check_color); c2.setAlpha(c1.alpha() // 2)
                c3 = QColor(check_color); c3.setAlpha(0)
                grad.setColorAt(0.0, c1)
                grad.setColorAt(0.5, c2)
                grad.setColorAt(1.0, c3)
                painter.fillRect(
                    QRectF(col * sq, row * sq, sq, sq), QBrush(grad)
                )

        # Custom highlights
        for square, hl in self._state.custom_highlights.items():
            self._fill_square(painter, square, sq, _parse_color(hl.color), z_adjust=-0.5)

        # Legal-move indicators
        if (
            self._state.selected is not None
            and not self._state.view_only
            and not self._state.editable
        ):
            is_premove = (
                len(self._state.premoves) > 0
                or (
                    self._state.movable.color is not None
                    and true_board.turn != self._state.movable.color
                )
            )
            if not (is_premove and not self._state.premovable.showDests):
                if (
                    not is_premove
                    and self._state.movable.dests
                    and self._state.selected in self._state.movable.dests
                ):
                    dests = self._state.movable.dests[self._state.selected]
                else:
                    dests = [
                        m.to_square
                        for m in visual_board.legal_moves
                        if m.from_square == self._state.selected
                    ]

                dot_color = (
                    premove_color if is_premove else QColor(0, 0, 0, 60)
                )
                for dest in dests:
                    is_capture = visual_board.piece_at(dest) is not None
                    self._draw_legal_indicator(painter, dest, sq, is_capture, dot_color)

    def _fill_square(self, painter, square, sq_size, color, z_adjust=0):
        col, row = self._square_to_col_row(square)
        painter.fillRect(
            QRectF(col * sq_size, row * sq_size, sq_size, sq_size), color
        )

    def _draw_legal_indicator(self, painter, square, sq_size, is_capture, color):
        col, row = self._square_to_col_row(square)
        x = col * sq_size
        y = row * sq_size

        if is_capture:
            # Hollow ring
            pen_w = sq_size * 0.08
            margin = sq_size * 0.05
            painter.save()
            pen = QPen(color)
            pen.setWidthF(pen_w)
            painter.setPen(pen)
            painter.setBrush(QBrush(Qt.NoBrush))
            painter.drawEllipse(
                QRectF(
                    x + margin + pen_w / 2,
                    y + margin + pen_w / 2,
                    sq_size - 2 * margin - pen_w,
                    sq_size - 2 * margin - pen_w,
                )
            )
            painter.restore()
        else:
            # Small filled dot
            radius = sq_size * 0.15
            cx = x + sq_size / 2.0
            cy = y + sq_size / 2.0
            painter.save()
            painter.setPen(QPen(Qt.NoPen))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))
            painter.restore()

    def _draw_shapes(self, painter, sq):
        shapes = list(self._state.shapes)
        if self._state.preview_shape:
            shapes.append(self._state.preview_shape)

        for shape in shapes:
            color = _parse_color(shape.color)
            pen = QPen(color)
            pen.setWidthF(shape.width)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)

            if shape.type == "circle":
                col, row = self._square_to_col_row(shape.orig)
                diameter = sq * 0.8
                margin = (sq - diameter) / 2
                painter.save()
                painter.setPen(pen)
                painter.setBrush(QBrush(Qt.transparent))
                painter.drawEllipse(
                    QRectF(col * sq + margin, row * sq + margin, diameter, diameter)
                )
                painter.restore()

            elif shape.type == "cross":
                col, row = self._square_to_col_row(shape.orig)
                m = sq * 0.2
                x0, y0 = col * sq, row * sq
                path = QPainterPath()
                path.moveTo(x0 + m, y0 + m)
                path.lineTo(x0 + sq - m, y0 + sq - m)
                path.moveTo(x0 + sq - m, y0 + m)
                path.lineTo(x0 + m, y0 + sq - m)
                painter.save()
                painter.setPen(pen)
                painter.drawPath(path)
                painter.restore()

            elif shape.type == "arrow" and shape.dest is not None:
                p1 = self._square_to_point(shape.orig) + QPointF(sq / 2, sq / 2)
                p2 = self._square_to_point(shape.dest)  + QPointF(sq / 2, sq / 2)

                dx = p2.x() - p1.x()
                dy = p2.y() - p1.y()
                length = math.hypot(dx, dy)
                if length == 0:
                    continue

                ux, uy = dx / length, dy / length
                start_margin = sq * 0.3
                end_margin   = sq * 0.35
                if length > (start_margin + end_margin):
                    start_pt = p1 + QPointF(ux * start_margin, uy * start_margin)
                    end_pt   = p2 - QPointF(ux * end_margin,   uy * end_margin)
                else:
                    start_pt = p1 + QPointF(ux * length * 0.1, uy * length * 0.1)
                    end_pt   = p2 - QPointF(ux * length * 0.2, uy * length * 0.2)

                arrow_size = max(12.0, shape.width * 3.0)
                wing_w = arrow_size * 0.6
                base_pt  = end_pt - QPointF(ux * arrow_size, uy * arrow_size)
                wing_pt1 = base_pt + QPointF(-uy * wing_w,  ux * wing_w)
                wing_pt2 = base_pt - QPointF(-uy * wing_w,  ux * wing_w)

                path = QPainterPath()
                path.moveTo(start_pt)
                path.lineTo(base_pt)
                path.moveTo(wing_pt1)
                path.lineTo(end_pt)
                path.lineTo(wing_pt2)
                path.closeSubpath()

                painter.save()
                painter.setPen(pen)
                painter.setBrush(QBrush(color))
                painter.drawPath(path)
                painter.restore()

    def _draw_pieces(self, painter, sq, visual_board: chess.Board):
        """Draw all static pieces (skip drag square and animation destination)."""
        for square in chess.SQUARES:
            if square == self._drag_square:
                continue
            if self._anim_piece is not None and square == self._anim_to_sq:
                continue
            piece = visual_board.piece_at(square)
            if piece:
                pixmap = self._get_pixmap(piece)
                if pixmap:
                    col, row = self._square_to_col_row(square)
                    painter.drawPixmap(int(col * sq), int(row * sq), pixmap)

    def _draw_animated_piece(self, painter, sq):
        if self._anim_piece is None or self._anim_from_sq is None or self._anim_to_sq is None:
            return
        p_from = self._square_to_point(self._anim_from_sq)
        p_to   = self._square_to_point(self._anim_to_sq)
        t = self._anim_progress
        cx = p_from.x() + (p_to.x() - p_from.x()) * t
        cy = p_from.y() + (p_to.y() - p_from.y()) * t
        pixmap = self._get_pixmap(self._anim_piece)
        if pixmap:
            painter.drawPixmap(int(cx), int(cy), pixmap)

    def _draw_dragged_piece(self, painter, sq, visual_board: chess.Board):
        if self._drag_square is None or self._drag_pos is None:
            return
        piece = visual_board.piece_at(self._drag_square)
        if piece:
            pixmap = self._get_pixmap(piece)
            if pixmap:
                x = self._drag_pos.x() - sq / 2
                y = self._drag_pos.y() - sq / 2
                # Clamp within board
                x = max(0.0, min(x, sq * 8 - sq))
                y = max(0.0, min(y, sq * 8 - sq))
                painter.drawPixmap(int(x), int(y), pixmap)

    def _draw_coordinates(self, painter, sq, light_color, dark_color):
        font_size = max(1, int(sq * 0.16))
        font = QFont("Arial", font_size, QFont.Bold)
        painter.setFont(font)
        pad = max(2.0, sq * 0.04)
        box = sq * 0.45

        orientation = self._state.orientation

        for i in range(8):
            # File label (bottom-right of bottom row square)
            file_idx = i if orientation == chess.WHITE else 7 - i
            file_char = chess.FILE_NAMES[file_idx]
            sq_rank_for_file = 0 if orientation == chess.WHITE else 7
            is_light = (file_idx + sq_rank_for_file) % 2 != 0
            painter.setPen(dark_color if is_light else light_color)
            painter.drawText(
                QRectF(i * sq + sq - box - pad, 7 * sq + sq - box - pad, box, box),
                Qt.AlignRight | Qt.AlignBottom,
                file_char,
            )

            # Rank label (top-left of left-column square)
            rank_idx = 7 - i if orientation == chess.WHITE else i
            rank_char = chess.RANK_NAMES[rank_idx]
            sq_file_for_rank = 0 if orientation == chess.WHITE else 7
            is_light = (sq_file_for_rank + rank_idx) % 2 != 0
            painter.setPen(dark_color if is_light else light_color)
            painter.drawText(
                QRectF(pad, i * sq + pad, box, box),
                Qt.AlignLeft | Qt.AlignTop,
                rank_char,
            )

    # -----------------------------------------------------------------------
    # Mouse events
    # -----------------------------------------------------------------------

    def mousePressEvent(self, event):
        if self._state.view_only:
            return

        pos = QPointF(event.pos())
        square = self._point_to_square(pos)

        # --- Right-click ---
        if event.button() == Qt.RightButton:
            if not self._state.draw_shapes:
                # Clear premoves and selection
                self._state.premoves.clear()
                self._state.selected = None
                self._click_origin = None
                self._suppress_anim_square = None
                self.update()
                return
            else:
                self._right_click_start_square = square
                self._is_drawing_shape = True
                self._current_draw_target_square = square
                if square is not None:
                    self._state.preview_shape = BoardShape(
                        type="circle",
                        orig=square,
                        color="rgba(21, 128, 61, 0.6)",
                        width=4.0,
                    )
                    self.update()
                event.accept()
                return

        # --- Left-click ---
        if event.button() == Qt.LeftButton:
            # Clear shapes on left-click
            if self._state.shapes or self._state.custom_highlights:
                self._state.shapes.clear()
                self._state.custom_highlights.clear()
                self.update()

            if square is not None:
                self.squareClicked.emit(square)

            if self._state.editable:
                if square is not None:
                    piece = chess.Board(self._state.fen).piece_at(square)
                    if piece:
                        self._drag_square = square
                        self._drag_pos = pos
                        self._drag_start_pos_widget = pos
                        self.update()
            else:
                visual_board = self.get_visual_board()
                true_board = chess.Board(self._state.fen)
                is_our_turn = (
                    self._state.movable.color is None
                    or true_board.turn == self._state.movable.color
                )
                can_select = (square is not None) and self._can_move_piece(square, visual_board)

                if self._click_origin is not None:
                    if square == self._click_origin:
                        # Re-click on origin — start drag
                        if can_select:
                            self._drag_square = square
                            self._drag_pos = pos
                    else:
                        # Attempt move
                        if square is not None:
                            move = self._create_move(self._click_origin, square, visual_board)
                            if is_our_turn and not self._state.premoves:
                                if self._is_move_valid(move, visual_board):
                                    old_board = chess.Board(self._state.fen)
                                    self._suppress_anim_square = move.to_square
                                    anim_cfg = self._state.animation
                                    if anim_cfg.enabled:
                                        piece = old_board.piece_at(move.from_square)
                                        if piece and move.to_square != self._suppress_anim_square:
                                            self._start_animation(move.from_square, move.to_square, piece)
                                    self.moveMade.emit(move)
                                    self._click_origin = None
                                    self._state.selected = None
                                else:
                                    if can_select:
                                        self._click_origin = square
                                        self._state.selected = square
                                        self._drag_square = square
                                        self._drag_pos = pos
                                    else:
                                        self._click_origin = None
                                        self._state.selected = None
                            else:
                                if self._state.premovable.enabled:
                                    if move in visual_board.legal_moves:
                                        self._state.premoves.append(move)
                                        self._click_origin = None
                                        self._state.selected = None
                                    else:
                                        if can_select:
                                            self._click_origin = square
                                            self._state.selected = square
                                            self._drag_square = square
                                            self._drag_pos = pos
                                        else:
                                            self._click_origin = None
                                            self._state.selected = None
                                else:
                                    self._click_origin = None
                                    self._state.selected = None
                        else:
                            self._click_origin = None
                            self._state.selected = None
                else:
                    if can_select and square is not None:
                        self._click_origin = square
                        self._state.selected = square
                        self._drag_square = square
                        self._drag_pos = pos

                self.selectionChanged.emit(self._state.selected)
                self.update()

    def mouseMoveEvent(self, event):
        pos = QPointF(event.pos())

        if self._drag_square is not None:
            self._drag_pos = pos
            self.update()
            return

        if self._is_drawing_shape:
            current_sq = self._point_to_square(pos)
            if current_sq != self._current_draw_target_square:
                self._current_draw_target_square = current_sq
                if current_sq is not None and self._right_click_start_square is not None:
                    if current_sq == self._right_click_start_square:
                        self._state.preview_shape = BoardShape(
                            type="circle",
                            orig=self._right_click_start_square,
                            color="rgba(21, 128, 61, 0.6)",
                            width=4.0,
                        )
                    else:
                        self._state.preview_shape = BoardShape(
                            type="arrow",
                            orig=self._right_click_start_square,
                            dest=current_sq,
                            color="rgba(21, 128, 61, 0.6)",
                            width=4.0,
                        )
                else:
                    self._state.preview_shape = None
                self.update()

    def mouseReleaseEvent(self, event):
        # --- Right-click shape drawing ---
        if event.button() == Qt.RightButton and self._is_drawing_shape:
            self._is_drawing_shape = False
            self._state.preview_shape = None

            end_square = self._point_to_square(QPointF(event.pos()))
            if self._right_click_start_square is not None and end_square is not None:
                if self._right_click_start_square == end_square:
                    existing = [
                        s for s in self._state.shapes
                        if s.type == "circle" and s.orig == end_square
                    ]
                    if existing:
                        for s in existing:
                            self._state.shapes.remove(s)
                    else:
                        self._state.shapes.append(BoardShape(
                            type="circle",
                            orig=end_square,
                            color="rgba(21, 128, 61, 0.6)",
                            width=4.0,
                        ))
                else:
                    existing = [
                        s for s in self._state.shapes
                        if s.type == "arrow"
                        and s.orig == self._right_click_start_square
                        and s.dest == end_square
                    ]
                    if existing:
                        for s in existing:
                            self._state.shapes.remove(s)
                    else:
                        self._state.shapes.append(BoardShape(
                            type="arrow",
                            orig=self._right_click_start_square,
                            dest=end_square,
                            color="rgba(21, 128, 61, 0.6)",
                            width=4.0,
                        ))

            self._right_click_start_square = None
            self._current_draw_target_square = None
            self.update()
            event.accept()
            return

        # --- Left-click / drag release ---
        if event.button() == Qt.LeftButton and self._drag_square is not None:
            pos = QPointF(event.pos())
            dest_square = self._point_to_square(pos)
            drag_start = self._drag_square

            if self._state.editable:
                board = chess.Board(self._state.fen)
                piece = board.piece_at(drag_start)
                if piece:
                    if dest_square is not None:
                        if dest_square != drag_start:
                            board.remove_piece_at(drag_start)
                            board.set_piece_at(dest_square, piece)
                            self._state.fen = board.fen()
                            self._suppress_anim_square = dest_square
                            self._drag_square = None
                            self._drag_pos = None
                            self._state.dragging = False
                            self._click_origin = None
                            self._state.selected = None
                            self.update()
                            self.fenChanged.emit(self._state.fen)
                            self.pieceDropped.emit(chess.Move(drag_start, dest_square))
                        else:
                            # Dropped on same square — cancel
                            self._drag_square = None
                            self._drag_pos = None
                            self._state.dragging = False
                            self.update()
                    else:
                        # Off-board — delete piece
                        board.remove_piece_at(drag_start)
                        self._state.fen = board.fen()
                        self._drag_square = None
                        self._drag_pos = None
                        self._state.dragging = False
                        self._click_origin = None
                        self._state.selected = None
                        self.update()
                        self.fenChanged.emit(self._state.fen)
            else:
                visual_board = self.get_visual_board()
                true_board = chess.Board(self._state.fen)
                is_our_turn = (
                    self._state.movable.color is None
                    or true_board.turn == self._state.movable.color
                )

                if dest_square is not None and dest_square != drag_start:
                    move = self._create_move(drag_start, dest_square, visual_board)

                    if is_our_turn and not self._state.premoves:
                        if self._is_move_valid(move, visual_board):
                            self._suppress_anim_square = dest_square
                            # Don't animate — piece just dropped
                            self.moveMade.emit(move)
                            self.pieceDropped.emit(move)
                            self._click_origin = None
                            self._state.selected = None
                        # else: invalid drag, snap back (just redraw without moving piece)
                    else:
                        if self._state.premovable.enabled:
                            if move in visual_board.legal_moves:
                                self._state.premoves.append(move)
                                self._click_origin = None
                                self._state.selected = None
                else:
                    # Dropped on same square — keep selected for click-click
                    pass

                self._drag_square = None
                self._drag_pos = None
                self._state.dragging = False
                self.update()

    # -----------------------------------------------------------------------
    # Drag & drop (external — editable mode)
    # -----------------------------------------------------------------------

    def dragEnterEvent(self, event):
        if self._state.editable and event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._state.editable and event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if self._state.editable and event.mimeData().hasText():
            text = event.mimeData().text()
            pos = QPointF(event.pos())
            square = self._point_to_square(pos)
            if square is not None:
                try:
                    piece = chess.Piece.from_symbol(text)
                    self.setpiece_at(square, piece)
                    event.acceptProposedAction()
                except ValueError:
                    super().dropEvent(event)
            else:
                super().dropEvent(event)
        else:
            super().dropEvent(event)

    # -----------------------------------------------------------------------
    # Resize
    # -----------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        side = min(self.width(), self.height())
        self._square_size = side / 8.0
        # Invalidate cache — will be rebuilt on next paintEvent
        self._cache_sq_size = 0
        self.update()
