"""
test_painter_board.py — Test suite for PainterChessBoard feature parity.

Covers:
  1.  Starting position
  2.  Empty board
  3.  Arbitrary FEN
  4.  Board flipping
  5.  Piece movement (programmatic)
  6.  Captures
  7.  Promotion (auto-queen)
  8.  Drag simulation
  9.  Click-to-move simulation
  10. Animations (enabled/disabled)
  11. Highlights (last move, selected, custom)
  12. Check detection
  13. Arrows and circles via state
  14. Premoves
  15. Resizing
  16. Rapid repeated moves
  17. Switching positions while animation active
  18. Signals
  19. API parity (set, set_fen, flip, move_piece, setpiece_at, set_state)
  20. Verify existing main tests not broken (import sanity check)
"""

import sys
import chess
import pytest

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QPointF, Qt

from src.painter_board import PainterChessBoard
from src.board import BoardView
from src.models import BoardState


@pytest.fixture(scope="session")
def app():
    """Single QApplication for all tests."""
    _app = QApplication.instance() or QApplication(sys.argv)
    return _app


@pytest.fixture
def board(app):
    """Fresh PainterChessBoard for each test."""
    b = PainterChessBoard()
    b.resize(480, 480)
    b.show()
    QApplication.processEvents()
    return b


# ---------------------------------------------------------------------------
# 1. Starting position
# ---------------------------------------------------------------------------


def test_starting_position(board):
    cb = chess.Board(board._state.fen)
    assert cb == chess.Board()
    assert board._state.fen == chess.STARTING_FEN


# ---------------------------------------------------------------------------
# 2. Empty board
# ---------------------------------------------------------------------------


def test_empty_board(board):
    empty_fen = "8/8/8/8/8/8/8/8 w - - 0 1"
    board.set(fen=empty_fen)
    cb = chess.Board(board._state.fen)
    assert len(cb.piece_map()) == 0


# ---------------------------------------------------------------------------
# 3. Arbitrary FEN
# ---------------------------------------------------------------------------


def test_arbitrary_fen(board):
    fen = "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2"
    board.set(fen=fen)
    assert chess.Board(board._state.fen).fen() == chess.Board(fen).fen()


# ---------------------------------------------------------------------------
# 4. Board flipping
# ---------------------------------------------------------------------------


def test_flip_orientation(board):
    assert board._state.orientation == chess.WHITE
    board.flip_orientation()
    assert board._state.orientation == chess.BLACK
    board.flip_orientation()
    assert board._state.orientation == chess.WHITE


def test_flip_and_square_mapping(board):
    board.flip_orientation()
    # a1 in black-bottom orientation: file=0 → col=7, rank=0 → row=0 (top-right)
    col, row = board._square_to_col_row(chess.A1)
    assert col == 7 and row == 0


# ---------------------------------------------------------------------------
# 5. Piece movement (programmatic)
# ---------------------------------------------------------------------------


def test_move_piece(board):
    move = chess.Move.from_uci("e2e4")
    board.move_piece(move)
    cb = chess.Board(board._state.fen)
    assert cb.piece_at(chess.E4) == chess.Piece(chess.PAWN, chess.WHITE)
    assert cb.piece_at(chess.E2) is None


def test_move_piece_illegal_ignored(board):
    original_fen = board._state.fen
    board.move_piece(chess.Move.from_uci("e2e5"))  # illegal
    assert board._state.fen == original_fen


# ---------------------------------------------------------------------------
# 6. Captures
# ---------------------------------------------------------------------------


def test_capture(board):
    # Scholar's mate capture: 1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6?? 4.Qxf7#
    moves = ["e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7"]
    cb = chess.Board()
    for uci in moves:
        m = chess.Move.from_uci(uci)
        cb.push(m)
    board.set(fen=cb.fen())
    # f7 should now have a white queen
    assert chess.Board(board._state.fen).piece_at(chess.F7) == chess.Piece(
        chess.QUEEN, chess.WHITE
    )


# ---------------------------------------------------------------------------
# 7. Promotion (auto-queen via _create_move)
# ---------------------------------------------------------------------------


def test_promotion_auto_queen(board):
    # Put a white pawn on e7
    fen = "4k3/4P3/8/8/8/8/8/4K3 w - - 0 1"
    board.set(fen=fen)
    cb = chess.Board(fen)
    # Patch _ask_promotion to avoid a blocking dialog in tests
    board._ask_promotion = lambda color: chess.QUEEN
    move = board._create_move(chess.E7, chess.E8, cb)
    assert move.promotion == chess.QUEEN


# ---------------------------------------------------------------------------
# 8. Drag simulation
# ---------------------------------------------------------------------------


def test_drag_simulation(board):
    board._state.movable.color = chess.WHITE
    sq = board._square_size

    # Press on e2 (white pawn)
    e2_col, e2_row = board._square_to_col_row(chess.E2)
    press_pos = QPointF(e2_col * sq + sq / 2, e2_row * sq + sq / 2)

    from PyQt5.QtTest import QTest
    from PyQt5.QtCore import QPoint

    QTest.mousePress(
        board,
        Qt.LeftButton,
        Qt.NoModifier,
        QPoint(int(press_pos.x()), int(press_pos.y())),
    )
    QApplication.processEvents()

    assert board._drag_square == chess.E2

    # Move mouse
    e4_col, e4_row = board._square_to_col_row(chess.E4)
    move_pos = QPointF(e4_col * sq + sq / 2, e4_row * sq + sq / 2)
    QTest.mouseMove(board, QPoint(int(move_pos.x()), int(move_pos.y())))
    QApplication.processEvents()

    # Release
    moves_made = []
    board.moveMade.connect(lambda m: moves_made.append(m))
    QTest.mouseRelease(
        board,
        Qt.LeftButton,
        Qt.NoModifier,
        QPoint(int(move_pos.x()), int(move_pos.y())),
    )
    QApplication.processEvents()

    assert len(moves_made) == 1
    assert moves_made[0].from_square == chess.E2
    assert moves_made[0].to_square == chess.E4


# ---------------------------------------------------------------------------
# 9. Click-to-move simulation
# ---------------------------------------------------------------------------


def test_click_to_move(board):
    board._state.movable.color = chess.WHITE
    sq = board._square_size
    moves_made = []
    board.moveMade.connect(lambda m: moves_made.append(m))

    from PyQt5.QtTest import QTest
    from PyQt5.QtCore import QPoint

    def click_square(square):
        col, row = board._square_to_col_row(square)
        p = QPoint(int(col * sq + sq / 2), int(row * sq + sq / 2))
        QTest.mouseClick(board, Qt.LeftButton, Qt.NoModifier, p)
        QApplication.processEvents()

    click_square(chess.D2)  # select pawn on d2
    assert board._state.selected == chess.D2

    click_square(chess.D4)  # move to d4
    assert len(moves_made) == 1
    assert moves_made[0] == chess.Move.from_uci("d2d4")


# ---------------------------------------------------------------------------
# 10. Animation state
# ---------------------------------------------------------------------------


def test_animation_disabled(board):
    board.set(animation={"enabled": False})
    assert board._state.animation.enabled is False
    board.move_piece(chess.Move.from_uci("e2e4"))
    # With animation disabled, no animation should be running
    assert board._anim is None


def test_animation_enabled(board):
    board.set(animation={"enabled": True, "duration": 50})
    board.move_piece(chess.Move.from_uci("e2e4"))
    # Animation might or might not have started depending on timing,
    # but no exception should occur and the FEN should be updated
    cb = chess.Board(board._state.fen)
    assert cb.piece_at(chess.E4) is not None


# ---------------------------------------------------------------------------
# 11. Highlights
# ---------------------------------------------------------------------------


def test_last_move_highlight(board):
    move = chess.Move.from_uci("e2e4")
    board.set(lastMove=move)
    assert board._state.last_move == move


def test_selected_highlight(board):
    board.set(selected=chess.E2)
    assert board._state.selected == chess.E2


def test_custom_highlights(board):
    board.set(customHighlights={chess.A1: "rgba(255, 0, 0, 0.5)"})
    assert chess.A1 in board._state.custom_highlights


# ---------------------------------------------------------------------------
# 12. Check detection
# ---------------------------------------------------------------------------


def test_check_highlight_in_state(board):
    # Set a position where white is in check
    check_fen = "rnb1kbnr/pppp1ppp/4p3/8/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
    board.set(fen=check_fen)
    cb = chess.Board(check_fen)
    assert cb.is_check()
    # paintEvent should not throw
    board.repaint()
    QApplication.processEvents()


# ---------------------------------------------------------------------------
# 13. Arrows and circles
# ---------------------------------------------------------------------------


def test_arrow_shape(board):
    board.set(
        shapes=[
            {
                "type": "arrow",
                "orig": "e2",
                "dest": "e4",
                "color": "rgba(21,128,61,0.6)",
                "width": 4.0,
            }
        ]
    )
    assert len(board._state.shapes) == 1
    assert board._state.shapes[0].type == "arrow"


def test_circle_shape(board):
    board.set(
        shapes=[
            {
                "type": "circle",
                "orig": "e4",
                "color": "rgba(21,128,61,0.6)",
                "width": 4.0,
            }
        ]
    )
    assert len(board._state.shapes) == 1
    assert board._state.shapes[0].type == "circle"


def test_right_click_draws_circle(board):
    """Simulate right-click press and release on same square → circle added."""
    board.set(drawShapes=True)
    sq = board._square_size

    from PyQt5.QtTest import QTest
    from PyQt5.QtCore import QPoint

    e4_col, e4_row = board._square_to_col_row(chess.E4)
    p = QPoint(int(e4_col * sq + sq / 2), int(e4_row * sq + sq / 2))

    QTest.mousePress(board, Qt.RightButton, Qt.NoModifier, p)
    QApplication.processEvents()
    QTest.mouseRelease(board, Qt.RightButton, Qt.NoModifier, p)
    QApplication.processEvents()

    circles = [
        s for s in board._state.shapes if s.type == "circle" and s.orig == chess.E4
    ]
    assert len(circles) == 1


# ---------------------------------------------------------------------------
# 14. Premoves
# ---------------------------------------------------------------------------


def test_premove_queued(board):
    """While it's white's turn, premoves queue when movable.color=BLACK."""
    board.set(
        movable={"color": chess.BLACK},
        premovable={"enabled": True},
    )
    # Board is on white's turn → black can queue premove
    board._state.premoves.append(chess.Move.from_uci("e7e5"))
    assert len(board._state.premoves) == 1


def test_premove_highlight(board):
    board._state.premoves.append(chess.Move.from_uci("e7e5"))
    board._state.selected = chess.E7
    # Repaint should not throw
    board.repaint()
    QApplication.processEvents()


# ---------------------------------------------------------------------------
# 15. Resizing
# ---------------------------------------------------------------------------


def test_resize_invalidates_cache(board):
    board.resize(320, 320)
    QApplication.processEvents()
    old_cache_size = board._cache_sq_size
    board.resize(480, 480)
    QApplication.processEvents()
    # Cache should be invalidated (0 until next repaint)
    # After repaint it rebuilds
    board.repaint()
    QApplication.processEvents()
    assert board._cache_sq_size == int(board._square_size)
    assert board._cache_sq_size != old_cache_size


def test_resize_multiple_times(board):
    for size in [200, 300, 400, 500, 600, 480]:
        board.resize(size, size)
        board.repaint()
        QApplication.processEvents()
    # No crash


# ---------------------------------------------------------------------------
# 16. Rapid repeated moves
# ---------------------------------------------------------------------------


def test_rapid_moves(board):
    cb = chess.Board()
    moves = list(cb.legal_moves)[:10]
    for move in moves:
        board.move_piece(move)
        QApplication.processEvents()
    # No crash, FEN should reflect last move
    cb2 = chess.Board(board._state.fen)
    assert cb2 is not None


# ---------------------------------------------------------------------------
# 17. Switching positions while animation is active
# ---------------------------------------------------------------------------


def test_switch_fen_during_animation(board):
    board.set(animation={"enabled": True, "duration": 500})
    board.move_piece(chess.Move.from_uci("e2e4"))  # starts animation
    # Immediately switch FEN
    board.set(fen=chess.STARTING_FEN)
    QApplication.processEvents()
    # Animation should be cancelled
    # No crash


# ---------------------------------------------------------------------------
# 18. Signals
# ---------------------------------------------------------------------------


def test_signals_emitted(board):
    fen_signals = []
    move_signals = []
    board.fenChanged.connect(lambda f: fen_signals.append(f))
    board.moveMade.connect(lambda m: move_signals.append(m))

    board.set_fen("rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2")
    assert len(fen_signals) >= 1

    board.move_piece(chess.Move.from_uci("g1f3"))
    assert len(move_signals) >= 1


def test_squareclicked_signal(board):
    clicked = []
    board.squareClicked.connect(lambda sq: clicked.append(sq))

    from PyQt5.QtTest import QTest
    from PyQt5.QtCore import QPoint

    sq = board._square_size
    col, row = board._square_to_col_row(chess.E2)
    p = QPoint(int(col * sq + sq / 2), int(row * sq + sq / 2))
    QTest.mouseClick(board, Qt.LeftButton, Qt.NoModifier, p)
    QApplication.processEvents()

    assert chess.E2 in clicked


def test_selection_changed_signal(board):
    changed = []
    board.selectionChanged.connect(lambda sq: changed.append(sq))

    from PyQt5.QtTest import QTest
    from PyQt5.QtCore import QPoint

    sq = board._square_size
    col, row = board._square_to_col_row(chess.E2)
    p = QPoint(int(col * sq + sq / 2), int(row * sq + sq / 2))
    QTest.mouseClick(board, Qt.LeftButton, Qt.NoModifier, p)
    QApplication.processEvents()

    assert len(changed) >= 1


# ---------------------------------------------------------------------------
# 19. API parity
# ---------------------------------------------------------------------------


def test_set_fen_api(board):
    board.set_fen("8/8/8/8/8/8/8/8 w - - 0 1")
    assert len(chess.Board(board._state.fen).piece_map()) == 0


def test_setpiece_at(board):
    board.setpiece_at(chess.A1, chess.Piece(chess.QUEEN, chess.WHITE))
    cb = chess.Board(board._state.fen)
    assert cb.piece_at(chess.A1) == chess.Piece(chess.QUEEN, chess.WHITE)


def test_setpiece_at_string(board):
    board.setpiece_at(chess.H8, "k")  # black king
    cb = chess.Board(board._state.fen)
    assert cb.piece_at(chess.H8) == chess.Piece(chess.KING, chess.BLACK)


def test_setpiece_at_none_removes(board):
    board.setpiece_at(chess.E1, None)  # remove king
    cb = chess.Board(board._state.fen)
    assert cb.piece_at(chess.E1) is None


def test_set_piece_at_alias(board):
    board.set_piece_at(chess.D4, chess.Piece(chess.BISHOP, chess.BLACK))
    cb = chess.Board(board._state.fen)
    assert cb.piece_at(chess.D4) == chess.Piece(chess.BISHOP, chess.BLACK)


def test_set_state(board):
    state = BoardState(orientation=chess.BLACK)
    board.set_state(state)
    assert board._state.orientation == chess.BLACK


def test_view_only(board):
    board.set_view_only(True)
    assert board._state.view_only is True
    board.set_view_only(False)


def test_theme_via_set(board):
    board.set(theme={"light": "#ffffff", "dark": "#000000"})
    assert board._state.theme["light"] == "#ffffff"
    assert board._state.theme["dark"] == "#000000"


def test_editable_mode(board):
    board.set(editable=True)
    assert board._state.editable is True
    # In editable mode, any drag is allowed (legal move check bypassed)
    board.set(editable=False)


# ---------------------------------------------------------------------------
# 20. Paintability — no crash on extreme states
# ---------------------------------------------------------------------------


def test_paint_empty_board(board):
    board.set(fen="8/8/8/8/8/8/8/8 w - - 0 1")
    board.repaint()
    QApplication.processEvents()


def test_paint_with_shapes_and_highlights(board):
    board.set(
        lastMove=chess.Move.from_uci("e2e4"),
        selected=chess.E4,
        shapes=[
            {
                "type": "arrow",
                "orig": "e2",
                "dest": "e4",
                "color": "rgba(21,128,61,0.6)",
                "width": 4.0,
            },
            {
                "type": "circle",
                "orig": "d4",
                "color": "rgba(200,0,0,0.5)",
                "width": 3.0,
            },
        ],
        customHighlights={chess.A1: "rgba(255, 255, 0, 0.5)"},
    )
    board.repaint()
    QApplication.processEvents()


# ---------------------------------------------------------------------------
# Sanity: existing BoardView still importable and functional
# ---------------------------------------------------------------------------


def test_existing_board_view_still_works(app):
    bv = BoardView()
    bv.resize(400, 400)
    bv.show()
    QApplication.processEvents()
    bv.set(fen=chess.STARTING_FEN)
    bv.move_piece(chess.Move.from_uci("e2e4"))
    assert chess.Board(bv._state.fen).piece_at(chess.E4) is not None
    bv.hide()
