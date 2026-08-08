"""
painter_board_demo.py — Side-by-side comparison of the two chessboard implementations.

Left  : BoardView        (QGraphicsView + SVG pieces)
Right : PainterChessBoard (QWidget + QPainter + MERIFONT.TTF)

Run with:
    python painter_board_demo.py

Both boards are kept in sync via moveMade signals for visual comparison.
"""

import sys
import chess

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QPushButton, QLabel, QSplitter,
)
from PyQt5.QtCore import Qt

# Make sure the src package is on the path
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.board import BoardView, PainterChessBoard
from src.models import BoardState


class DemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GChessboard — Dual Renderer Demo")
        self.resize(1200, 680)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(8)

        # --- Title bar ---
        title = QLabel(
            "<b>QPainter/Font board</b> (right) vs <b>SVG/QGraphicsView board</b> (left) — "
            "make a move on either board to sync them"
        )
        title.setAlignment(Qt.AlignCenter)
        root_layout.addWidget(title)

        # --- Board split ---
        splitter = QSplitter(Qt.Horizontal)

        # SVG board (existing)
        svg_container = QWidget()
        svg_layout = QVBoxLayout(svg_container)
        svg_layout.setContentsMargins(0, 0, 0, 0)
        svg_label = QLabel("BoardView — QGraphicsView + SVG")
        svg_label.setAlignment(Qt.AlignCenter)
        self.svg_board = BoardView()
        svg_layout.addWidget(svg_label)
        svg_layout.addWidget(self.svg_board)
        splitter.addWidget(svg_container)

        # Painter board (new)
        painter_container = QWidget()
        painter_layout = QVBoxLayout(painter_container)
        painter_layout.setContentsMargins(0, 0, 0, 0)
        painter_label = QLabel("PainterChessBoard — QWidget + QPainter + MERIFONT.TTF")
        painter_label.setAlignment(Qt.AlignCenter)
        self.painter_board = PainterChessBoard()
        painter_layout.addWidget(painter_label)
        painter_layout.addWidget(self.painter_board)
        splitter.addWidget(painter_container)

        root_layout.addWidget(splitter, stretch=1)

        # --- Controls ---
        btn_row = QHBoxLayout()

        flip_btn = QPushButton("Flip Both Boards")
        flip_btn.clicked.connect(self._flip_both)
        btn_row.addWidget(flip_btn)

        reset_btn = QPushButton("Reset to Starting Position")
        reset_btn.clicked.connect(self._reset_both)
        btn_row.addWidget(reset_btn)

        viewonly_btn = QPushButton("Toggle View-Only")
        viewonly_btn.setCheckable(True)
        viewonly_btn.toggled.connect(self._toggle_viewonly)
        btn_row.addWidget(viewonly_btn)

        arrows_btn = QPushButton("Toggle Draw Shapes")
        arrows_btn.setCheckable(True)
        arrows_btn.setChecked(True)
        arrows_btn.toggled.connect(self._toggle_shapes)
        btn_row.addWidget(arrows_btn)

        root_layout.addLayout(btn_row)

        # Example FEN buttons
        fen_row = QHBoxLayout()
        fen_examples = [
            ("Starting", chess.STARTING_FEN),
            ("Sicilian", "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2"),
            ("Endgame",  "8/5k2/3p4/1p1Pp2p/pP2Pp1P/P4P1K/8/8 b - - 99 50"),
            ("Check",    "rnb1kbnr/pppp1ppp/4p3/8/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"),
        ]
        for name, fen in fen_examples:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, f=fen: self._load_fen(f))
            fen_row.addWidget(btn)
        root_layout.addLayout(fen_row)

        # --- Cross-sync signals ---
        self._syncing = False
        self.svg_board.moveMade.connect(self._svg_move_made)
        self.painter_board.moveMade.connect(self._painter_move_made)

        # Enable arrow drawing on both
        self.svg_board.set(drawShapes=True)
        self.painter_board.set(drawShapes=True)

    # -----------------------------------------------------------------------

    def _flip_both(self):
        self.svg_board.flip_orientation()
        self.painter_board.flip_orientation()

    def _reset_both(self):
        self.svg_board.set(fen=chess.STARTING_FEN, lastMove=None)
        self.painter_board.set(fen=chess.STARTING_FEN, lastMove=None)

    def _toggle_viewonly(self, checked):
        self.svg_board.set_view_only(checked)
        self.painter_board.set_view_only(checked)

    def _toggle_shapes(self, checked):
        self.svg_board.set(drawShapes=checked)
        self.painter_board.set(drawShapes=checked)

    def _load_fen(self, fen):
        self.svg_board.set(fen=fen, lastMove=None)
        self.painter_board.set(fen=fen, lastMove=None)

    def _svg_move_made(self, move: chess.Move):
        if self._syncing:
            return
        self._syncing = True
        board = chess.Board(self.svg_board._state.fen)
        self.painter_board.set(fen=board.fen(), lastMove=move)
        self._syncing = False

    def _painter_move_made(self, move: chess.Move):
        if self._syncing:
            return
        self._syncing = True
        fen = self.painter_board._state.fen
        self.svg_board.set(fen=fen, lastMove=move)
        self._syncing = False


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = DemoWindow()
    win.show()
    sys.exit(app.exec_())
