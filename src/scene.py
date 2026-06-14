import chess
from PyQt5.QtWidgets import (
    QGraphicsScene,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QGraphicsEllipseItem,
)
from PyQt5.QtCore import Qt, QPointF, QPropertyAnimation, QParallelAnimationGroup
from PyQt5.QtGui import QBrush, QColor, QFont, QPen, QRadialGradient
from typing import Dict, Optional

from .models import BoardState, AnimationConfig
from .pieces import PieceItem


class SquareItem(QGraphicsRectItem):
    def __init__(self, square: chess.Square, size: float, color: QColor, parent=None):
        super().__init__(parent)
        self.square = square
        self.setRect(0, 0, size, size)
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.NoPen))
        self.setZValue(-2)
        self.setAcceptHoverEvents(True)


def parse_color(color_str: str) -> QColor:
    """Helper to parse color strings like #RRGGBB or rgba(r,g,b,a)"""
    if color_str.startswith("rgba"):
        # Very basic rgba parser
        content = color_str[color_str.find("(") + 1 : color_str.find(")")]
        parts = [p.strip() for p in content.split(",")]
        if len(parts) == 4:
            r, g, b = map(int, parts[:3])
            a = int(float(parts[3]) * 255)
            return QColor(r, g, b, a)
    return QColor(color_str)


class BoardScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.squares: Dict[chess.Square, SquareItem] = {}
        self.piece_items: Dict[chess.Square, PieceItem] = {}
        self.file_labels: list[QGraphicsTextItem] = []
        self.rank_labels: list[QGraphicsTextItem] = []

        self.highlights: Dict[str, list[QGraphicsRectItem]] = {
            "last_move": [],
            "selected": [],
            "check": [],
            "legal_moves": [],
            "premove": [],
        }

        self._initialized = False
        self._current_fen = None
        self._current_square_size = 0
        self._current_orientation = None
        self._current_theme = None
        self._anim_group = QParallelAnimationGroup()

    def update_highlights(
        self,
        state: BoardState,
        visual_board: chess.Board,
        square_size: float,
        orientation: chess.Color,
    ):
        for hl_list in self.highlights.values():
            for hl in hl_list:
                self.removeItem(hl)
            hl_list.clear()

        true_board = chess.Board(state.fen)
        theme = state.theme

        # Legal moves (dots or circles)
        if state.selected and not state.view_only:
            dests = []
            is_premove = len(state.premoves) > 0 or (
                state.movable.color is not None
                and true_board.turn != state.movable.color
            )

            if is_premove and not state.premovable.showDests:
                pass  # Don't show dests if disabled
            else:
                # Normal or premove dests are just legal moves on the visual_board
                if (
                    not is_premove
                    and state.movable.dests
                    and state.selected in state.movable.dests
                ):
                    dests = state.movable.dests[state.selected]
                else:
                    dests = [
                        m.to_square
                        for m in visual_board.legal_moves
                        if m.from_square == state.selected
                    ]

            color = (
                parse_color(theme.get("premove", "rgba(20, 100, 200, 0.4)"))
                if is_premove
                else QColor(0, 0, 0, 30)
            )
            for dest in dests:
                is_capture = visual_board.piece_at(dest) is not None
                hl = self._add_legal_move_highlight(
                    dest, is_capture, square_size, orientation, color
                )
                self.highlights["legal_moves"].append(hl)

        if state.last_move:
            hl_color = parse_color(theme.get("lastMove", "rgba(255, 255, 0, 0.5)"))
            self._add_highlight(
                state.last_move.from_square,
                hl_color,
                "last_move",
                square_size,
                orientation,
            )
            self._add_highlight(
                state.last_move.to_square,
                hl_color,
                "last_move",
                square_size,
                orientation,
            )

        if state.selected:
            sel_color = parse_color(theme.get("selected", "rgba(0, 0, 255, 0.4)"))
            self._add_highlight(
                state.selected, sel_color, "selected", square_size, orientation
            )

        # Highlight all premoves in the queue
        pm_color = parse_color(theme.get("premove", "rgba(20, 100, 200, 0.5)"))
        for pm in state.premoves:
            self._add_highlight(
                pm.from_square, pm_color, "premove", square_size, orientation
            )
            self._add_highlight(
                pm.to_square, pm_color, "premove", square_size, orientation
            )

        if true_board.is_check():
            king_square = true_board.king(true_board.turn)
            if king_square is not None:
                check_color = parse_color(theme.get("check", "rgba(255, 0, 0, 0.8)"))
                self._add_check_highlight(
                    king_square, square_size, orientation, check_color
                )

    def _add_legal_move_highlight(
        self,
        square: chess.Square,
        is_capture: bool,
        square_size: float,
        orientation: chess.Color,
        color: QColor = QColor(0, 0, 0, 30),
    ):
        pos = self.get_square_pos(square, square_size, orientation)

        if is_capture:
            # Hollow circle around the piece
            margin = square_size * 0.05
            hl = QGraphicsEllipseItem(
                margin, margin, square_size - 2 * margin, square_size - 2 * margin
            )
            pen = QPen(color)
            pen.setWidth(int(square_size * 0.08))
            hl.setPen(pen)
            hl.setBrush(QBrush(Qt.NoBrush))
        else:
            # Small dot in the center
            radius = square_size * 0.15
            hl = QGraphicsEllipseItem(
                square_size / 2 - radius,
                square_size / 2 - radius,
                2 * radius,
                2 * radius,
            )
            hl.setBrush(QBrush(color))
            hl.setPen(QPen(Qt.NoPen))

        hl.setPos(pos)
        hl.setZValue(-1)
        self.addItem(hl)
        return hl

    def _add_check_highlight(
        self,
        square: chess.Square,
        square_size: float,
        orientation: chess.Color,
        color: QColor,
    ):
        pos = self.get_square_pos(square, square_size, orientation)
        hl = QGraphicsEllipseItem(0, 0, square_size, square_size)

        gradient = QRadialGradient(square_size / 2, square_size / 2, square_size / 2)
        c2 = QColor(color)
        c2.setAlpha(color.alpha() // 2)
        c3 = QColor(color)
        c3.setAlpha(0)

        gradient.setColorAt(0, color)
        gradient.setColorAt(0.5, c2)
        gradient.setColorAt(1, c3)

        hl.setBrush(QBrush(gradient))
        hl.setPen(QPen(Qt.NoPen))
        hl.setPos(pos)
        hl.setZValue(-1)
        self.addItem(hl)
        self.highlights["check"].append(hl)

    def _add_highlight(
        self,
        square: chess.Square,
        color: QColor,
        category: str,
        square_size: float,
        orientation: chess.Color,
    ):
        hl = QGraphicsRectItem(0, 0, square_size, square_size)
        hl.setBrush(QBrush(color))
        hl.setPen(QPen(Qt.NoPen))
        hl.setPos(self.get_square_pos(square, square_size, orientation))
        hl.setZValue(-1)
        self.addItem(hl)
        self.highlights[category].append(hl)

    def setup_board(
        self, square_size: float, orientation: chess.Color, theme: dict = None
    ):
        if not self._initialized or theme != self._current_theme:
            self._create_board(square_size, orientation, theme)
            self._initialized = True
            self._current_theme = theme
        else:
            self._update_positions(square_size, orientation, theme)

    def set_fen(
        self,
        fen: str,
        square_size: float,
        orientation: chess.Color,
        animation_config: AnimationConfig,
        instant_square: Optional[chess.Square] = None,
    ) -> bool:
        size_changed = (
            square_size != self._current_square_size
            or orientation != self._current_orientation
        )
        theme_changed = (
            self._current_fen is None
        )  # Signaled by _create_board clearing current_fen
        if fen == self._current_fen and not size_changed and not theme_changed:
            # Check if all pieces are physically in their correct positions.
            # If any piece has been dragged away, we bypass this early return.
            pieces_in_pos = True
            for sq, item in self.piece_items.items():
                try:
                    _ = item.zValue()
                    target = self.get_square_pos(sq, square_size, orientation)
                    if (item.pos() - target).manhattanLength() > 1:
                        pieces_in_pos = False
                        break
                except RuntimeError:
                    pieces_in_pos = False
                    break
            if pieces_in_pos:
                return False

        fen_changed = fen != self._current_fen or theme_changed
        new_board = chess.Board(fen)
        old_board = chess.Board(self._current_fen) if self._current_fen else None

        self._anim_group.stop()
        self._anim_group.clear()

        new_piece_items = {}

        if old_board:
            for square in chess.SQUARES:
                piece = new_board.piece_at(square)
                if not piece:
                    continue

                matched_item = None
                if square in self.piece_items:
                    item = self.piece_items[square]
                    try:
                        # Check if the C++ object is still alive by accessing a property
                        _ = item.zValue()
                        if item.piece == piece:
                            matched_item = self.piece_items.pop(square)
                    except RuntimeError:
                        # C++ object deleted
                        self.piece_items.pop(square)

                if not matched_item:
                    for old_square, old_item in list(self.piece_items.items()):
                        try:
                            _ = old_item.zValue()
                            if (
                                old_item.piece == piece
                                and new_board.piece_at(old_square) != piece
                            ):
                                matched_item = self.piece_items.pop(old_square)
                                break
                        except RuntimeError:
                            self.piece_items.pop(old_square)

                if matched_item:
                    matched_item.set_square(square)
                    matched_item.set_square_size(square_size)
                    new_piece_items[square] = matched_item

                    target_pos = self.get_square_pos(square, square_size, orientation)
                    dist = (matched_item.pos() - target_pos).manhattanLength()
                    if (
                        animation_config.enabled
                        and square != instant_square
                        and dist > 1
                        and not size_changed
                    ):
                        anim = QPropertyAnimation(matched_item, b"pos")
                        anim.setDuration(animation_config.duration)
                        anim.setEndValue(target_pos)
                        self._anim_group.addAnimation(anim)
                    else:
                        matched_item.setPos(target_pos)
                else:
                    piece_item = PieceItem(piece, square, square_size)
                    self.addItem(piece_item)
                    piece_item.setPos(
                        self.get_square_pos(square, square_size, orientation)
                    )
                    new_piece_items[square] = piece_item
        else:
            for square in chess.SQUARES:
                piece = new_board.piece_at(square)
                if piece:
                    piece_item = PieceItem(piece, square, square_size)
                    self.addItem(piece_item)
                    piece_item.setPos(
                        self.get_square_pos(square, square_size, orientation)
                    )
                    new_piece_items[square] = piece_item

        for item in self.piece_items.values():
            self.removeItem(item)

        self.piece_items = new_piece_items
        self._current_fen = fen
        self._current_square_size = square_size
        self._current_orientation = orientation

        if animation_config.enabled and self._anim_group.animationCount() > 0:
            self._anim_group.start()

        return fen_changed

    def get_square_pos(
        self, square: chess.Square, square_size: float, orientation: chess.Color
    ) -> QPointF:
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        if orientation == chess.WHITE:
            x = file * square_size
            y = (7 - rank) * square_size
        else:
            x = (7 - file) * square_size
            y = rank * square_size
        return QPointF(x, y)

    def _create_board(
        self, square_size: float, orientation: chess.Color, theme: dict = None
    ):
        self.clear()
        self.squares.clear()
        self.piece_items.clear()
        self.file_labels.clear()
        self.rank_labels.clear()
        for hl_list in self.highlights.values():
            hl_list.clear()

        self._current_fen = None

        if theme:
            light_color = parse_color(theme["light"])
            dark_color = parse_color(theme["dark"])
        else:
            light_color = QColor("#dee3e6")
            dark_color = QColor("#8ca2ad")

        for square in chess.SQUARES:
            file = chess.square_file(square)
            rank = chess.square_rank(square)
            is_light = (file + rank) % 2 != 0
            color = light_color if is_light else dark_color

            sq_item = SquareItem(square, square_size, color)
            self.addItem(sq_item)
            self.squares[square] = sq_item

        for i in range(8):
            file_label = QGraphicsTextItem()
            file_label.setZValue(1)
            self.addItem(file_label)
            self.file_labels.append(file_label)

            rank_label = QGraphicsTextItem()
            rank_label.setZValue(1)
            self.addItem(rank_label)
            self.rank_labels.append(rank_label)

        self._update_positions(square_size, orientation, theme)

    def _update_positions(
        self, square_size: float, orientation: chess.Color, theme: dict = None
    ):
        font_size = int(square_size * 0.16)
        if font_size < 1:
            font_size = 1
        font = QFont("Arial", font_size, QFont.Bold)

        if theme:
            light_color = parse_color(theme["light"])
            dark_color = parse_color(theme["dark"])
        else:
            light_color = QColor("#dee3e6")
            dark_color = QColor("#8ca2ad")

        for square, sq_item in self.squares.items():
            pos = self.get_square_pos(square, square_size, orientation)
            sq_item.setRect(0, 0, square_size, square_size)
            sq_item.setPos(pos)

        for i in range(8):
            file_char = (
                chess.FILE_NAMES[i]
                if orientation == chess.WHITE
                else chess.FILE_NAMES[7 - i]
            )
            f_label = self.file_labels[i]
            f_label.setFont(font)
            is_light_white = i % 2 != 0
            is_light_black = (7 - i + 7) % 2 != 0
            is_light = is_light_white if orientation == chess.WHITE else is_light_black
            f_label.setDefaultTextColor(dark_color if is_light else light_color)
            f_label.setPlainText(file_char)
            rect_f = f_label.boundingRect()
            f_label.setPos(
                i * square_size + square_size - rect_f.width() - 1,
                7 * square_size + square_size - rect_f.height() - 1,
            )

            rank_char = (
                chess.RANK_NAMES[i]
                if orientation == chess.BLACK
                else chess.RANK_NAMES[7 - i]
            )
            r_label = self.rank_labels[i]
            r_label.setFont(font)
            is_light_white_rank = (7 - i) % 2 != 0
            is_light_black_rank = (7 + i) % 2 != 0
            is_light = (
                is_light_white_rank
                if orientation == chess.WHITE
                else is_light_black_rank
            )
            r_label.setDefaultTextColor(dark_color if is_light else light_color)
            r_label.setPlainText(rank_char)
            r_label.setPos(1, i * square_size + 1)
