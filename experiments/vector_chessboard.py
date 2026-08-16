import os
import chess
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import (
    Qt,
    QRectF,
    pyqtSignal,
    QPointF,
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
    QPixmap,
    QRadialGradient,
)


class VectorChessboard(QWidget):
    """
    High-Performance Chessboard implementation based on Approach D in instructions.md:
    1. Uses the exact Merida piece mapping from painter_chessboard.py (p,n,b,r,q,k and o,m,v,t,w,l).
    2. Fills the hollow interior of white piece glyphs solid white using their outer contour path.
    3. Renders into cached QPixmap buffers whenever square size changes for maximum FPS.
    """

    moveMade = pyqtSignal(chess.Move)
    fenChanged = pyqtSignal(str)

    # Standard Merida TTF Character Mappings (Identical to painter_chessboard.py)
    PIECE_CHARS = {
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

    def __init__(self, font_file: str = "MERIFONT.TTF", parent=None):
        super().__init__(parent)
        self.board = chess.Board()
        self.orientation = chess.WHITE
        self.light_color = QColor("#f0d9b5")
        self.dark_color = QColor("#b58863")
        self.selected_square = None
        self.drag_square = None
        self.drag_pos = None

        # Highlights & Indicators
        self.last_move = None
        self.last_move_color = QColor(255, 255, 0, 110)

        # Animation state
        self.animation_enabled = True
        self.animation_duration = 200  # ms
        self._anim = None
        self._anim_progress = 0.0
        self._anim_piece = None
        self._anim_start_sq = None
        self._anim_dest_sq = None

        # Cache for rendered pixmaps
        self._pixmap_cache = {}
        self._cache_sq_size = 0

        # Load Chess Font
        self.set_font_file(font_file)

    def set_font_file(self, font_file: str):
        """Loads a chess font file (e.g. MERIFONT.TTF, LINEFONT.TTF) and clears cache."""
        font_path = os.path.join(os.path.dirname(__file__), font_file)
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                self.font_family = families[0]
            else:
                self.font_family = "Arial"
        else:
            self.font_family = "Arial"

        self._cache_sq_size = 0
        self._pixmap_cache.clear()
        self.update()

    def set_fen(self, fen: str, animate: bool = True, last_move: chess.Move = None):
        old_board = self.board
        new_board = chess.Board(fen)

        if last_move is not None:
            self.last_move = last_move
        elif animate and self.animation_enabled and old_board != new_board:
            self._detect_and_start_animation(old_board, new_board)

        self.board = new_board
        self.selected_square = None
        self.drag_square = None
        self.update()
        self.fenChanged.emit(self.board.fen())

    def _detect_and_start_animation(
        self, old_board: chess.Board, new_board: chess.Board
    ):
        disappeared = []
        appeared = []

        for sq in chess.SQUARES:
            p_old = old_board.piece_at(sq)
            p_new = new_board.piece_at(sq)
            if p_old != p_new:
                if p_old is not None and (p_new is None or p_new.color != p_old.color):
                    disappeared.append((sq, p_old))
                if p_new is not None and (p_old is None or p_old.color != p_new.color):
                    appeared.append((sq, p_new))

        from_sq, to_sq, piece = None, None, None
        for d_sq, d_piece in disappeared:
            for a_sq, a_piece in appeared:
                if (
                    d_piece.piece_type == a_piece.piece_type
                    and d_piece.color == a_piece.color
                ):
                    from_sq, to_sq, piece = d_sq, a_sq, a_piece
                    break
            if from_sq is not None:
                break

        if from_sq is not None and to_sq is not None:
            self.last_move = chess.Move(from_sq, to_sq)
            self._start_move_animation(from_sq, to_sq, piece)

    def _start_move_animation(
        self, from_sq: chess.Square, to_sq: chess.Square, piece: chess.Piece
    ):
        if self._anim:
            self._anim.stop()

        self._anim_piece = piece
        self._anim_start_sq = from_sq
        self._anim_dest_sq = to_sq
        self._anim_progress = 0.0

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(self.animation_duration)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_valueChanged)
        self._anim.finished.connect(self._on_anim_finished)
        self._anim.start()

    def _on_anim_valueChanged(self, value):
        self._anim_progress = float(value)
        self.update()

    def _on_anim_finished(self):
        self._anim_piece = None
        self._anim_start_sq = None
        self._anim_dest_sq = None
        self._anim = None
        self.update()

    def get_fen(self) -> str:
        return self.board.fen()

    def flip_orientation(self):
        self.orientation = (
            chess.BLACK if self.orientation == chess.WHITE else chess.WHITE
        )
        self.update()

    def get_square_at(self, pos: QPointF) -> chess.Square:
        sq_size = self.get_square_size()
        if sq_size == 0:
            return None
        file = int(pos.x() // sq_size)
        rank = int(pos.y() // sq_size)

        if 0 <= file < 8 and 0 <= rank < 8:
            sq_file = file if self.orientation == chess.WHITE else 7 - file
            sq_rank = 7 - rank if self.orientation == chess.WHITE else rank
            return chess.square(sq_file, sq_rank)
        return None

    def get_square_size(self) -> float:
        size = min(self.width(), self.height())
        return size / 8.0

    def _create_glyph_path(
        self, char: str, font: QFont, sq_size: float
    ) -> QPainterPath:
        """Converts piece character into a centered QPainterPath vector path."""
        temp_path = QPainterPath()
        temp_path.addText(0, 0, font, char)
        br = temp_path.boundingRect()

        target_cx = sq_size / 2.0
        target_cy = sq_size / 2.0
        glyph_cx = br.x() + br.width() / 2.0
        glyph_cy = br.y() + br.height() / 2.0

        dx = target_cx - glyph_cx
        dy = target_cy - glyph_cy

        path = QPainterPath()
        path.addText(dx, dy, font, char)
        return path

    def _generate_pixmap_cache(self, sq_size: float):
        """Renders original Merida glyph paths into transparent QPixmap buffers, filling hollow white pieces solid white."""
        self._pixmap_cache.clear()
        self._cache_sq_size = int(sq_size)

        font = QFont(self.font_family)
        font.setPixelSize(int(sq_size * 0.85))

        for (p_type, p_color), char in self.PIECE_CHARS.items():
            path = self._create_glyph_path(char, font, sq_size)

            pixmap = QPixmap(int(sq_size), int(sq_size))
            pixmap.fill(Qt.transparent)

            p = QPainter(pixmap)
            p.setRenderHint(QPainter.Antialiasing)
            p.setRenderHint(QPainter.TextAntialiasing)

            if p_color == chess.WHITE:
                # Extract outer contour of hollow white piece glyph and fill it solid white
                polys = path.toSubpathPolygons()
                if polys:
                    sorted_polys = sorted(
                        polys,
                        key=lambda poly: (
                            poly.boundingRect().width() * poly.boundingRect().height()
                        ),
                        reverse=True,
                    )
                    outer_path = QPainterPath()
                    outer_path.addPolygon(sorted_polys[0])
                    p.fillPath(outer_path, QBrush(QColor("#ffffff")))

                # Draw white piece black outline & inner details over the white fill
                p.fillPath(path, QBrush(QColor("#000000")))
            else:
                # Black pieces are drawn solid black
                p.fillPath(path, QBrush(QColor("#000000")))

            p.end()
            self._pixmap_cache[(p_type, p_color)] = pixmap

    def get_piece_pixmap(
        self, piece_type: chess.PieceType, piece_color: chess.Color, sq_size: float
    ) -> QPixmap:
        if int(sq_size) != self._cache_sq_size:
            self._generate_pixmap_cache(sq_size)
        return self._pixmap_cache.get((piece_type, piece_color))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        sq_size = self.get_square_size()
        if sq_size <= 0:
            return

        # Ensure pixmap cache is updated for current sq_size
        if int(sq_size) != self._cache_sq_size:
            self._generate_pixmap_cache(sq_size)

        # 1. Draw Squares
        for rank in range(8):
            for file in range(8):
                sq_rank = 7 - rank if self.orientation == chess.WHITE else rank
                sq_file = file if self.orientation == chess.WHITE else 7 - file
                square = chess.square(sq_file, sq_rank)

                x = file * sq_size
                y = rank * sq_size

                is_light = (sq_rank + sq_file) % 2 != 0
                color = self.light_color if is_light else self.dark_color
                painter.fillRect(QRectF(x, y, sq_size, sq_size), color)

        # 2. Draw Last Move Highlight
        if self.last_move is not None:
            for sq in (self.last_move.from_square, self.last_move.to_square):
                s_file = chess.square_file(sq)
                s_rank = chess.square_rank(sq)
                col = s_file if self.orientation == chess.WHITE else 7 - s_file
                row = 7 - s_rank if self.orientation == chess.WHITE else s_rank
                painter.fillRect(
                    QRectF(col * sq_size, row * sq_size, sq_size, sq_size),
                    self.last_move_color,
                )

        # 3. Draw Selected Square Highlight
        if self.selected_square is not None:
            s_file = chess.square_file(self.selected_square)
            s_rank = chess.square_rank(self.selected_square)
            col = s_file if self.orientation == chess.WHITE else 7 - s_file
            row = 7 - s_rank if self.orientation == chess.WHITE else s_rank
            painter.fillRect(
                QRectF(col * sq_size, row * sq_size, sq_size, sq_size),
                QColor(20, 100, 200, 120),
            )

        # 4. Draw Check Indicator on King
        if not self.board.is_game_over() and self.board.is_check():
            king_sq = self.board.king(self.board.turn)
            if king_sq is not None:
                k_file = chess.square_file(king_sq)
                k_rank = chess.square_rank(king_sq)
                col = k_file if self.orientation == chess.WHITE else 7 - k_file
                row = 7 - k_rank if self.orientation == chess.WHITE else k_rank

                cx = col * sq_size + sq_size / 2.0
                cy = row * sq_size + sq_size / 2.0
                r = sq_size / 2.0

                grad = QRadialGradient(cx, cy, r)
                grad.setColorAt(0.0, QColor(255, 0, 0, 200))
                grad.setColorAt(0.5, QColor(255, 0, 0, 100))
                grad.setColorAt(1.0, QColor(255, 0, 0, 0))

                painter.fillRect(
                    QRectF(col * sq_size, row * sq_size, sq_size, sq_size), QBrush(grad)
                )

        # 5. Draw Static Pieces (Cached pixmaps of original Merida pieces)
        for square in chess.SQUARES:
            if square == self.drag_square:
                continue
            if self._anim_piece is not None and square == self._anim_dest_sq:
                continue

            piece = self.board.piece_at(square)
            if piece:
                file = chess.square_file(square)
                rank = chess.square_rank(square)
                col = file if self.orientation == chess.WHITE else 7 - file
                row = 7 - rank if self.orientation == chess.WHITE else rank

                x = col * sq_size
                y = row * sq_size

                pixmap = self.get_piece_pixmap(piece.piece_type, piece.color, sq_size)
                if pixmap:
                    painter.drawPixmap(int(x), int(y), pixmap)

        # 6. Draw Animated Moving Piece
        if (
            self._anim_piece is not None
            and self._anim_start_sq is not None
            and self._anim_dest_sq is not None
        ):
            start_file = chess.square_file(self._anim_start_sq)
            start_rank = chess.square_rank(self._anim_start_sq)
            s_col = start_file if self.orientation == chess.WHITE else 7 - start_file
            s_row = 7 - start_rank if self.orientation == chess.WHITE else start_rank

            dest_file = chess.square_file(self._anim_dest_sq)
            dest_rank = chess.square_rank(self._anim_dest_sq)
            d_col = dest_file if self.orientation == chess.WHITE else 7 - dest_file
            d_row = 7 - dest_rank if self.orientation == chess.WHITE else dest_rank

            x0 = s_col * sq_size
            y0 = s_row * sq_size
            x1 = d_col * sq_size
            y1 = d_row * sq_size

            curr_x = x0 + (x1 - x0) * self._anim_progress
            curr_y = y0 + (y1 - y0) * self._anim_progress

            pixmap = self.get_piece_pixmap(
                self._anim_piece.piece_type, self._anim_piece.color, sq_size
            )
            if pixmap:
                painter.drawPixmap(int(curr_x), int(curr_y), pixmap)

        # 7. Draw Dragging Piece
        if self.drag_square is not None and self.drag_pos is not None:
            piece = self.board.piece_at(self.drag_square)
            if piece:
                pixmap = self.get_piece_pixmap(piece.piece_type, piece.color, sq_size)
                if pixmap:
                    x = self.drag_pos.x() - sq_size / 2
                    y = self.drag_pos.y() - sq_size / 2
                    painter.drawPixmap(int(x), int(y), pixmap)

        # 8. Draw Coordinates (Uncropped, Dynamically Scaled & High Contrast on top)
        coord_font = QFont("Arial", max(10, int(sq_size * 0.16)), QFont.Bold)
        painter.setFont(coord_font)
        pad = max(2.0, sq_size * 0.04)
        box_dim = sq_size * 0.45

        for i in range(8):
            file_char = chess.FILE_NAMES[
                i if self.orientation == chess.WHITE else 7 - i
            ]
            rank_char = chess.RANK_NAMES[
                7 - i if self.orientation == chess.WHITE else i
            ]

            file_sq_file = i if self.orientation == chess.WHITE else 7 - i
            file_sq_rank = 0 if self.orientation == chess.WHITE else 7
            is_file_sq_light = (file_sq_rank + file_sq_file) % 2 != 0

            painter.setPen(self.dark_color if is_file_sq_light else self.light_color)
            file_rect = QRectF(
                i * sq_size + sq_size - box_dim - pad,
                7 * sq_size + sq_size - box_dim - pad,
                box_dim,
                box_dim,
            )
            painter.drawText(file_rect, Qt.AlignRight | Qt.AlignBottom, file_char)

            rank_sq_file = 0 if self.orientation == chess.WHITE else 7
            rank_sq_rank = 7 - i if self.orientation == chess.WHITE else i
            is_rank_sq_light = (rank_sq_rank + rank_sq_file) % 2 != 0

            painter.setPen(self.dark_color if is_rank_sq_light else self.light_color)
            rank_rect = QRectF(
                pad,
                i * sq_size + pad,
                box_dim,
                box_dim,
            )
            painter.drawText(rank_rect, Qt.AlignLeft | Qt.AlignTop, rank_char)

    # Mouse Events for Dragging and Clicking
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            sq = self.get_square_at(event.localPos())
            if sq is not None:
                piece = self.board.piece_at(sq)
                if piece and piece.color == self.board.turn:
                    self.drag_square = sq
                    self.drag_pos = event.localPos()
                    self.selected_square = sq
                    self.update()
                elif self.selected_square is not None:
                    move = chess.Move(self.selected_square, sq)
                    if (
                        self.board.piece_at(self.selected_square)
                        and self.board.piece_at(self.selected_square).piece_type
                        == chess.PAWN
                        and (chess.square_rank(sq) == 7 or chess.square_rank(sq) == 0)
                    ):
                        move = chess.Move(
                            self.selected_square, sq, promotion=chess.QUEEN
                        )

                    if move in self.board.legal_moves:
                        self.last_move = move
                        if self.animation_enabled:
                            self._start_move_animation(
                                move.from_square,
                                move.to_square,
                                self.board.piece_at(move.from_square),
                            )
                        self.board.push(move)
                        self.moveMade.emit(move)
                        self.fenChanged.emit(self.board.fen())
                    self.selected_square = None
                    self.update()
                else:
                    self.selected_square = None
                    self.update()

    def mouseMoveEvent(self, event):
        if self.drag_square is not None:
            self.drag_pos = event.localPos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drag_square is not None:
            dest_sq = self.get_square_at(event.localPos())
            if dest_sq is not None and dest_sq != self.drag_square:
                move = chess.Move(self.drag_square, dest_sq)
                if (
                    self.board.piece_at(self.drag_square)
                    and self.board.piece_at(self.drag_square).piece_type == chess.PAWN
                    and (
                        chess.square_rank(dest_sq) == 7
                        or chess.square_rank(dest_sq) == 0
                    )
                ):
                    move = chess.Move(self.drag_square, dest_sq, promotion=chess.QUEEN)

                if move in self.board.legal_moves:
                    self.last_move = move
                    self.board.push(move)
                    self.moveMade.emit(move)
                    self.fenChanged.emit(self.board.fen())
                    self.selected_square = None
                else:
                    self.selected_square = self.drag_square
            self.drag_square = None
            self.drag_pos = None
            self.update()
