import pytest
import chess
from PyQt5.QtWidgets import QApplication
from src.board import BoardView
from src.models import BoardHighlight, BoardShape

# Ensure a QApplication instance exists
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

def test_custom_highlights_and_shapes(qapp):
    board_view = BoardView()
    
    # Test setting custom highlights with strings and BoardHighlight
    board_view.set(
        customHighlights={
            "e4": "rgba(0, 255, 0, 0.5)",
            chess.F3: BoardHighlight(color="blue", square=chess.F3),
            "e5": {"color": "rgba(255, 0, 0, 0.4)"}
        }
    )
    
    state = board_view._state
    assert chess.E4 in state.custom_highlights
    assert isinstance(state.custom_highlights[chess.E4], BoardHighlight)
    assert state.custom_highlights[chess.E4].color == "rgba(0, 255, 0, 0.5)"
    assert state.custom_highlights[chess.E4].square == chess.E4
    
    assert chess.F3 in state.custom_highlights
    assert state.custom_highlights[chess.F3].color == "blue"
    assert state.custom_highlights[chess.F3].square == chess.F3

    assert chess.E5 in state.custom_highlights
    assert state.custom_highlights[chess.E5].color == "rgba(255, 0, 0, 0.4)"
    
    # Test setting shapes
    board_view.set(
        shapes=[
            {"type": "arrow", "orig": "e2", "dest": "e4", "color": "rgba(0, 128, 255, 0.7)", "width": 6.0},
            {"type": "circle", "orig": "d4", "color": "rgba(255, 128, 0, 0.8)", "width": 4.0},
            {"type": "cross", "orig": "g1", "color": "rgba(255, 0, 128, 0.8)", "width": 5.0},
            BoardShape(type="circle", orig=chess.H3, color="green", width=3.0)
        ]
    )
    
    assert len(state.shapes) == 4
    
    arrow = state.shapes[0]
    assert isinstance(arrow, BoardShape)
    assert arrow.type == "arrow"
    assert arrow.orig == chess.E2
    assert arrow.dest == chess.E4
    assert arrow.color == "rgba(0, 128, 255, 0.7)"
    assert arrow.width == 6.0
    
    circle = state.shapes[1]
    assert isinstance(circle, BoardShape)
    assert circle.type == "circle"
    assert circle.orig == chess.D4
    assert circle.dest is None
    assert circle.color == "rgba(255, 128, 0, 0.8)"
    
    cross = state.shapes[2]
    assert isinstance(cross, BoardShape)
    assert cross.type == "cross"
    assert cross.orig == chess.G1
    assert cross.dest is None
    assert cross.color == "rgba(255, 0, 128, 0.8)"

    circle2 = state.shapes[3]
    assert isinstance(circle2, BoardShape)
    assert circle2.type == "circle"
    assert circle2.orig == chess.H3
    assert circle2.color == "green"
    
    # Verify scene items exist
    scene = board_view.scene()
    assert len(scene.shape_items) == 4
    
    # Test clearing custom highlights and shapes
    board_view.set(customHighlights={}, shapes=[])
    assert len(state.custom_highlights) == 0
    assert len(state.shapes) == 0
    assert len(scene.shape_items) == 0

def test_right_click_drawing(qapp):
    board_view = BoardView()
    squares_map = {}
    board_view.get_square_at = lambda pos: squares_map.get((pos.x(), pos.y()))
    
    from PyQt5.QtCore import QEvent, QPoint, Qt
    from PyQt5.QtGui import QMouseEvent
    
    p_e2 = QPoint(10, 10)
    p_e4 = QPoint(20, 20)
    squares_map[(10, 10)] = chess.E2
    squares_map[(20, 20)] = chess.E4
    
    # 1. Right Click Press on E2
    press_event = QMouseEvent(QEvent.MouseButtonPress, p_e2, Qt.RightButton, Qt.RightButton, Qt.NoModifier)
    board_view.mousePressEvent(press_event)
    
    assert board_view._is_drawing_shape is True
    assert board_view._right_click_start_square == chess.E2
    assert board_view._state.preview_shape is not None
    assert board_view._state.preview_shape.type == "circle"
    assert board_view._state.preview_shape.orig == chess.E2
    
    # 2. Right Click Drag to E4 (MouseMove)
    move_event = QMouseEvent(QEvent.MouseMove, p_e4, Qt.NoButton, Qt.RightButton, Qt.NoModifier)
    board_view.mouseMoveEvent(move_event)
    
    assert board_view._state.preview_shape.type == "arrow"
    assert board_view._state.preview_shape.orig == chess.E2
    assert board_view._state.preview_shape.dest == chess.E4
    
    # 3. Right Click Release on E4
    release_event = QMouseEvent(QEvent.MouseButtonRelease, p_e4, Qt.RightButton, Qt.NoButton, Qt.NoModifier)
    board_view.mouseReleaseEvent(release_event)
    
    assert board_view._is_drawing_shape is False
    assert board_view._state.preview_shape is None
    assert len(board_view._state.shapes) == 1
    assert board_view._state.shapes[0].type == "arrow"
    assert board_view._state.shapes[0].orig == chess.E2
    assert board_view._state.shapes[0].dest == chess.E4
    assert board_view._state.shapes[0].color == "rgba(21, 128, 61, 0.6)"
    
    # 4. Right Click Press on E4
    press_event2 = QMouseEvent(QEvent.MouseButtonPress, p_e4, Qt.RightButton, Qt.RightButton, Qt.NoModifier)
    board_view.mousePressEvent(press_event2)
    
    # 5. Right Click Release on E4 (single click circle toggle)
    release_event2 = QMouseEvent(QEvent.MouseButtonRelease, p_e4, Qt.RightButton, Qt.NoButton, Qt.NoModifier)
    board_view.mouseReleaseEvent(release_event2)
    
    assert len(board_view._state.shapes) == 2
    assert board_view._state.shapes[1].type == "circle"
    assert board_view._state.shapes[1].orig == chess.E4
    
    # 6. Left Click Press clears shapes
    left_press_event = QMouseEvent(QEvent.MouseButtonPress, p_e4, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    board_view.mousePressEvent(left_press_event)
    
    assert len(board_view._state.shapes) == 0

