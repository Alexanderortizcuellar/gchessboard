import sys
import chess
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
from src.board import BoardView
from src.models import BoardHighlight, BoardShape

class ShapesTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GChessboard Custom Shapes & Highlights Test")
        self.resize(800, 800)

        layout = QVBoxLayout()
        self.board_view = BoardView()
        layout.addWidget(self.board_view)

        self.btn = QPushButton("Toggle Shapes & Highlights")
        self.btn.clicked.connect(self.toggle_shapes)
        layout.addWidget(self.btn)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.has_shapes = False
        self.board_view.set(
            fen=chess.STARTING_FEN,
            movable={'color': chess.WHITE}
        )

    def toggle_shapes(self):
        if not self.has_shapes:
            # Add highlights and shapes
            self.board_view.set(
                customHighlights={
                    "e4": "rgba(0, 255, 0, 0.4)",
                    "e5": "rgba(255, 0, 0, 0.4)",
                    chess.F3: "rgba(0, 0, 255, 0.4)"
                },
                shapes=[
                    # Arrow from e2 to e4
                    {"type": "arrow", "orig": "e2", "dest": "e4", "color": "rgba(0, 128, 255, 0.7)", "width": 6.0},
                    # Circle on d4
                    {"type": "circle", "orig": "d4", "color": "rgba(255, 128, 0, 0.8)", "width": 4.0},
                    # Cross on g1
                    {"type": "cross", "orig": "g1", "color": "rgba(255, 0, 128, 0.8)", "width": 5.0}
                ]
            )
            self.has_shapes = True
        else:
            # Clear them
            self.board_view.set(
                customHighlights={},
                shapes=[]
            )
            self.has_shapes = False

def main():
    app = QApplication(sys.argv)
    window = ShapesTestWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
