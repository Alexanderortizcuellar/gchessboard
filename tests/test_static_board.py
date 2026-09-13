import os
import sys

# Ensure repository root is on sys.path for direct script execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import chess
import pytest
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QGridLayout,
    QLabel,
    QVBoxLayout,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QPixmap, QImage

from src.static_board import (
    StaticChessBoard,
    LightChessBoard,
    _GLOBAL_PIXMAP_CACHE,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_init_default(qapp):
    board = StaticChessBoard()
    assert board.fen == chess.STARTING_FEN
    assert board.orientation == chess.WHITE
    assert board.hasHeightForWidth() is True
    assert board.heightForWidth(200) == 200
    assert board.sizeHint() == QSize(240, 240)
    assert board.minimumSizeHint() == QSize(64, 64)


def test_alias_equivalence(qapp):
    assert LightChessBoard is StaticChessBoard
    board = LightChessBoard()
    assert isinstance(board, StaticChessBoard)


def test_set_fen_and_property(qapp):
    board = StaticChessBoard()
    test_fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
    board.set_fen(test_fen)
    assert board.get_fen() == test_fen
    assert board.fen == test_fen
    assert board.board.piece_at(chess.F3) == chess.Piece(chess.KNIGHT, chess.WHITE)

    # Test setter via property
    another_fen = "8/8/8/4k3/8/8/4K3/8 w - - 0 1"
    board.fen = another_fen
    assert board.fen == another_fen


def test_set_board_and_property(qapp):
    board = StaticChessBoard()
    custom_board = chess.Board()
    custom_board.push_san("e4")
    custom_board.push_san("e5")
    board.set_board(custom_board)
    assert board.board.piece_at(chess.E4) == chess.Piece(chess.PAWN, chess.WHITE)
    assert board.board.piece_at(chess.E5) == chess.Piece(chess.PAWN, chess.BLACK)

    # Test set_position convenience
    board.set_position(chess.STARTING_FEN)
    assert board.fen == chess.STARTING_FEN


def test_orientation_and_flip(qapp):
    board = StaticChessBoard(orientation=chess.BLACK)
    assert board.orientation == chess.BLACK
    board.flip()
    assert board.orientation == chess.WHITE
    board.orientation = chess.BLACK
    assert board.orientation == chess.BLACK


def test_board_dimensions(qapp):
    board = StaticChessBoard(size=320)
    assert board.width() == 320
    assert board.height() == 320

    board.set_board_size((160, 160))
    assert board.width() == 160
    assert board.height() == 160

    board.set_square_size(40.0)
    assert board.width() == 320
    assert board.height() == 320


def test_theme_and_colors(qapp):
    board = StaticChessBoard(
        light_color="#ffffff",
        dark_color="#000000",
    )
    assert board._light_color == QColor("#ffffff")
    assert board._dark_color == QColor("#000000")

    board.set_theme("rgba(240, 217, 181, 1.0)", "rgba(181, 136, 99, 1.0)")
    assert board._light_color == QColor(240, 217, 181, 255)
    assert board._dark_color == QColor(181, 136, 99, 255)


def test_highlights_and_last_move(qapp):
    board = StaticChessBoard()
    board.set_highlight(chess.E4, "rgba(0, 255, 0, 0.5)")
    assert chess.E4 in board._highlights
    board.set_highlight("e5", "#ff0000")
    assert chess.E5 in board._highlights

    board.set_last_move(chess.Move.from_uci("e2e4"))
    assert board._last_move == chess.Move(chess.E2, chess.E4)

    board.set_last_move("g1f3")
    assert board._last_move == chess.Move(chess.G1, chess.F3)

    board.clear_highlights()
    assert len(board._highlights) == 0


def test_coordinates_toggle(qapp):
    board = StaticChessBoard(show_coordinates=False)
    assert board._show_coordinates is False
    board.set_coordinates(True)
    assert board._show_coordinates is True


def test_render_to_pixmap_and_image(qapp):
    board = StaticChessBoard(position=chess.STARTING_FEN)
    pixmap = board.render_to_pixmap(width=200, height=200)
    assert isinstance(pixmap, QPixmap)
    assert not pixmap.isNull()
    assert pixmap.width() == 200
    assert pixmap.height() == 200

    image = board.render_to_image(width=128)
    assert isinstance(image, QImage)
    assert not image.isNull()
    assert image.width() == 128
    assert image.height() == 128


def test_shared_pixmap_cache(qapp):
    # Multiple boards with the same square size share the exact same cached pixmaps
    board1 = StaticChessBoard(square_size=40)
    board2 = StaticChessBoard(square_size=40)

    pixmap1 = board1.render_to_pixmap(320, 320)
    pixmap2 = board2.render_to_pixmap(320, 320)

    assert not pixmap1.isNull()
    assert not pixmap2.isNull()

    # Check that cache key (font_family, 40) exists
    key = (board1._font_family, 40)
    assert key in _GLOBAL_PIXMAP_CACHE
    assert len(_GLOBAL_PIXMAP_CACHE[key]) == 12


def test_widget_paint(qapp):
    board = StaticChessBoard(size=200)
    board.show()
    # Trigger a real paint event
    pixmap = QPixmap(200, 200)
    board.render(pixmap)
    assert not pixmap.isNull()
    board.close()


# ---------------------------------------------------------------------------
# Visual Demo Window when running this file directly
# ---------------------------------------------------------------------------


class StaticBoardDemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StaticChessBoard Demo — Lightweight Position Display")
        self.resize(860, 680)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        title = QLabel(
            "<b>StaticChessBoard</b>: Ultra-lightweight position display with shared glyph cache"
        )
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        grid = QGridLayout()
        root.addLayout(grid)

        # 1. Starting position (standard)
        b1 = StaticChessBoard(size=200, show_coordinates=True)
        grid.addWidget(
            QLabel("1. Starting Position + Coordinates"), 0, 0, Qt.AlignCenter
        )
        grid.addWidget(b1, 1, 0, Qt.AlignCenter)

        # 2. Tactical position + last move highlight
        b2 = StaticChessBoard(
            position="r1bqk2r/pppp1ppp/2n5/1B2p3/4n3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 6",
            size=200,
        )
        b2.set_last_move("f3e5")
        b2.set_highlight(chess.E4, "rgba(239, 68, 68, 0.5)")
        grid.addWidget(
            QLabel("2. Ruy Lopez + Last Move / Highlights"), 0, 1, Qt.AlignCenter
        )
        grid.addWidget(b2, 1, 1, Qt.AlignCenter)

        # 3. Endgame position + flipped orientation (Black perspective)
        b3 = StaticChessBoard(
            position="8/5k2/8/8/8/8/4K3/4R3 w - - 0 1",
            orientation=chess.BLACK,
            size=200,
            show_coordinates=True,
        )
        grid.addWidget(
            QLabel("3. Endgame (Flipped / Black view)"), 0, 2, Qt.AlignCenter
        )
        grid.addWidget(b3, 1, 2, Qt.AlignCenter)

        # 4. Custom Dark/Neon Theme
        b4 = StaticChessBoard(
            position="rnbqkb1r/pp2pppp/3p1n2/8/3NP3/8/PPP2PPP/RNBQKB1R w KQkq - 1 5",
            size=200,
            light_color="#3d4f5d",
            dark_color="#243039",
        )
        grid.addWidget(QLabel("4. Custom Theme (Dark Blue)"), 2, 0, Qt.AlignCenter)
        grid.addWidget(b4, 3, 0, Qt.AlignCenter)

        # 5. Mini Thumbnail (120x120)
        b5 = StaticChessBoard(
            position="r1b1k2r/ppppqppp/2n2n2/4p3/1b2P3/2NP1N2/PPP1BPPP/R1BQK2R w KQkq - 3 6",
            size=120,
        )
        grid.addWidget(QLabel("5. Mini Thumbnail (120px)"), 2, 1, Qt.AlignCenter)
        grid.addWidget(b5, 3, 1, Qt.AlignCenter)

        # 6. Micro Thumbnail (80x80)
        b6 = StaticChessBoard(
            position="8/8/8/3k4/8/4K3/8/8 w - - 0 1",
            size=80,
        )
        grid.addWidget(QLabel("6. Micro Thumbnail (80px)"), 2, 2, Qt.AlignCenter)
        grid.addWidget(b6, 3, 2, Qt.AlignCenter)


def main():
    app = QApplication(sys.argv)
    window = StaticBoardDemoWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    # If invoked directly via python, run pytest tests and show demo
    ret = pytest.main(["-v", __file__])
    if ret == 0:
        main()
