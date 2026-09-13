import os
import sys

# Ensure repository root is on sys.path for direct script execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import chess
import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtTest import QTest

from src.board import BoardView
from src.painter_board import PainterChessBoard
from src.static_board import StaticChessBoard
from src.models import BoardShape


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_board_view_preview_lifecycle(qapp):
    board = BoardView()
    board.resize(480, 480)

    # 1. Set up game state with a move and premove
    game_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    board.set(
        fen=game_fen,
        orientation=chess.WHITE,
        movable={"color": chess.WHITE},
        premovable={"enabled": True},
    )
    board._state.premoves.append(chess.Move.from_uci("g1f3"))

    assert board.is_previewing is False
    assert board._state.fen == game_fen
    assert len(board._state.premoves) == 1

    # 2. Activate preview
    preview_fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
    board.set_preview(
        fen=preview_fen,
        last_move="g1f3",
        opacity=0.75,
        dim_board=True,
    )

    assert board.is_previewing is True
    assert board._state.preview is not None
    assert board._state.preview.fen == preview_fen
    assert board._state.preview.last_move == chess.Move(chess.G1, chess.F3)
    assert board._state.preview.opacity == 0.75
    assert board._state.preview.dim_board is True

    # Real game state must remain untouched
    assert board._state.fen == game_fen
    assert len(board._state.premoves) == 1
    assert board.get_visual_board().fen() == preview_fen

    # 3. User clicks are ignored during preview
    square_e4 = chess.E4
    e4_pos = board.scene().get_square_pos(
        square_e4, board._square_size, board._state.orientation
    )
    viewport_pos = board.mapFromScene(e4_pos + QPoint(10, 10))
    QTest.mousePress(board.viewport(), Qt.LeftButton, Qt.NoModifier, viewport_pos)
    assert board._drag_piece is None

    # 4. Clear preview — real game state resumes seamlessly
    board.clear_preview()

    assert board.is_previewing is False
    assert board._state.preview is None
    assert board._state.fen == game_fen
    assert len(board._state.premoves) == 1
    # Visual board returns to predicted premove position on real board
    assert board.get_visual_board().piece_at(chess.F3) == chess.Piece(
        chess.KNIGHT, chess.WHITE
    )


def test_painter_board_preview_lifecycle(qapp):
    board = PainterChessBoard()
    board.resize(480, 480)

    game_fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
    board.set(
        fen=game_fen,
        orientation=chess.WHITE,
        movable={"color": chess.WHITE},
        premovable={"enabled": True},
    )
    board._state.premoves.append(chess.Move.from_uci("g1f3"))

    assert board.is_previewing is False

    # Activate preview via set_preview
    preview_fen = "8/8/8/4k3/8/8/4K3/8 w - - 0 1"
    board.set_preview(fen=preview_fen, last_move="e2e3", opacity=0.85)

    assert board.is_previewing is True
    assert board.get_visual_board().fen() == preview_fen
    assert board._state.fen == game_fen
    assert len(board._state.premoves) == 1

    # Clear preview
    board.clear_preview()
    assert board.is_previewing is False
    assert board._state.preview is None
    assert board._state.fen == game_fen
    assert len(board._state.premoves) == 1


def test_unified_set_preview(qapp):
    board = PainterChessBoard()
    preview_fen = "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1"

    # Set via dict in .set()
    board.set(
        preview={
            "fen": preview_fen,
            "lastMove": "d2d4",
            "opacity": 0.70,
            "dimBoard": True,
        }
    )
    assert board.is_previewing is True
    assert board._state.preview.opacity == 0.70
    assert board._state.preview.last_move == chess.Move(chess.D2, chess.D4)
    assert board._state.preview.dim_board is True

    # Clear via preview=None in .set()
    board.set(preview=None)
    assert board.is_previewing is False
    assert board._state.preview is None


def test_preview_with_shapes(qapp):
    board = BoardView()
    preview_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    arrow = BoardShape(
        type="arrow", orig=chess.E2, dest=chess.E4, color="rgba(0, 128, 255, 0.8)"
    )

    board.set_preview(
        fen=preview_fen,
        shapes=[arrow],
    )
    assert board.is_previewing is True
    assert len(board._state.preview.shapes) == 1
    assert board._state.preview.shapes[0].type == "arrow"

    board.clear_preview()
    assert board.is_previewing is False


def test_static_board_preview(qapp):
    board = StaticChessBoard(position=chess.STARTING_FEN, size=200)
    assert board.is_previewing is False

    preview_fen = "8/8/8/8/8/8/8/4K2k w - - 0 1"
    board.set_preview(fen=preview_fen, opacity=0.6)
    assert board.is_previewing is True

    # Offline pixmap render works in preview mode
    pixmap = board.render_to_pixmap(200, 200)
    assert not pixmap.isNull()

    board.clear_preview()
    assert board.is_previewing is False
    assert board.fen == chess.STARTING_FEN


if __name__ == "__main__":
    ret = pytest.main(["-v", __file__])
    sys.exit(ret)
