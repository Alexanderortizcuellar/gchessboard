import sys
import chess
import chess.svg
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QLineEdit,
    QCheckBox
)
from PyQt5.QtCore import Qt, QSize, QByteArray
from PyQt5.QtGui import QPixmap, QPainter, QIcon
from PyQt5.QtSvg import QSvgRenderer
from src.board import BoardView

def get_piece_icon(symbol: str) -> QIcon:
    piece = chess.Piece.from_symbol(symbol)
    svg_data = chess.svg.piece(piece, size=45).encode("utf-8")
    renderer = QSvgRenderer(QByteArray(svg_data))
    pixmap = QPixmap(45, 45)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


class EditorTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GChessboard Position Editor & SetPiece Test")
        self.resize(900, 950)

        # Core layout
        main_layout = QHBoxLayout()

        # Left Column: Chessboard
        left_layout = QVBoxLayout()
        self.board_view = BoardView()
        left_layout.addWidget(self.board_view)

        # Bottom info
        self.info_label = QLabel(
            "Instructions:\n"
            "1. Check 'Enable Position Editor (Editable)' to drag pieces anywhere, or drag them off the board to delete.\n"
            "2. Select a piece from the Palette and click a square to place it.\n"
            "3. Use the buttons below to manipulate the board programmatically."
        )
        self.info_label.setStyleSheet("padding: 10px; background: #ecf0f1; border-radius: 5px; color: #2c3e50; font-size: 13px;")
        left_layout.addWidget(self.info_label)
        main_layout.addLayout(left_layout, stretch=3)

        # Right Column: Controls & Palette
        right_layout = QVBoxLayout()

        # FEN Input / Output
        fen_label = QLabel("Current FEN:")
        fen_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        right_layout.addWidget(fen_label)

        self.fen_input = QLineEdit()
        self.fen_input.setText(chess.STARTING_FEN)
        self.fen_input.editingFinished.connect(self.load_fen_from_input)
        right_layout.addWidget(self.fen_input)

        # Editable Mode Checkbox
        self.edit_mode_cb = QCheckBox("Enable Position Editor (Editable Mode)")
        self.edit_mode_cb.stateChanged.connect(self.toggle_edit_mode)
        self.edit_mode_cb.setChecked(True)
        right_layout.addWidget(self.edit_mode_cb)

        # Palette
        palette_label = QLabel("Piece Palette (Select & click square to place):")
        palette_label.setStyleSheet("font-weight: bold; margin-top: 15px;")
        right_layout.addWidget(palette_label)

        palette_layout = QHBoxLayout()
        self.palette_buttons = {}
        # None button to clear
        clear_btn = QPushButton("Eraser")
        clear_btn.setCheckable(True)
        clear_btn.setFixedHeight(50)
        clear_btn.clicked.connect(lambda: self.select_palette(None, clear_btn))
        palette_layout.addWidget(clear_btn)
        self.palette_buttons[None] = clear_btn

        pieces_to_add = [
            ("P", "wP"), ("N", "wN"), ("B", "wB"), ("R", "wR"), ("Q", "wQ"), ("K", "wK"),
            ("p", "bP"), ("n", "bN"), ("b", "bB"), ("r", "bR"), ("q", "bQ"), ("k", "bK")
        ]

        self.selected_piece_symbol = None

        # Grid-like layout for pieces
        palette_grid = QVBoxLayout()
        # Add eraser row to palette_grid first
        palette_grid.addLayout(palette_layout)
        
        white_row = QHBoxLayout()
        black_row = QHBoxLayout()

        for sym, name in pieces_to_add:
            btn = QPushButton()
            btn.setIcon(get_piece_icon(sym))
            btn.setIconSize(QSize(40, 40))
            btn.setCheckable(True)
            btn.setFixedSize(50, 50)
            btn.clicked.connect(lambda checked, s=sym, b=btn: self.select_palette(s, b))
            if sym.isupper():
                white_row.addWidget(btn)
            else:
                black_row.addWidget(btn)
            self.palette_buttons[sym] = btn

        palette_grid.addLayout(white_row)
        palette_grid.addLayout(black_row)
        right_layout.addLayout(palette_grid)

        # Board manipulation buttons
        btn_label = QLabel("Actions:")
        btn_label.setStyleSheet("font-weight: bold; margin-top: 20px;")
        right_layout.addWidget(btn_label)

        self.btn_clear_board = QPushButton("Clear Board (All Empty)")
        self.btn_clear_board.clicked.connect(self.clear_board)
        right_layout.addWidget(self.btn_clear_board)

        self.btn_reset_starting = QPushButton("Reset to Starting Position")
        self.btn_reset_starting.clicked.connect(self.reset_to_starting)
        right_layout.addWidget(self.btn_reset_starting)

        self.btn_flip = QPushButton("Flip Orientation")
        self.btn_flip.clicked.connect(self.board_view.flip_orientation)
        right_layout.addWidget(self.btn_flip)

        right_layout.addStretch()
        main_layout.addLayout(right_layout, stretch=1)

        # Set central widget
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Connect signals
        self.board_view.fenChanged.connect(self.on_fen_changed)
        self.board_view.squareClicked.connect(self.on_square_clicked)
        self.board_view.pieceDropped.connect(self.on_piece_dropped)

        # Initialize view state
        self.reset_to_starting()

    def toggle_edit_mode(self, state):
        is_editable = (state == Qt.Checked)
        self.board_view.set(editable=is_editable)
        self.info_label.setText(f"Editable mode set to: {is_editable}")

    def select_palette(self, sym, clicked_btn):
        # Uncheck all other buttons
        for s, btn in self.palette_buttons.items():
            if btn != clicked_btn:
                btn.setChecked(False)
        
        if clicked_btn.isChecked():
            self.selected_piece_symbol = sym
        else:
            self.selected_piece_symbol = None

    def on_square_clicked(self, square):
        # If a palette piece is selected, set it at the square
        # We only do this if the checkbox is checked, or if we want to demonstrate setpiece_at
        if self.selected_piece_symbol is not None:
            self.board_view.setpiece_at(square, self.selected_piece_symbol)
        elif None in self.palette_buttons and self.palette_buttons[None].isChecked():
            # Eraser mode
            self.board_view.setpiece_at(square, None)
        
        sq_name = chess.square_name(square)
        print(f"Square clicked: {sq_name}")

    def on_piece_dropped(self, move):
        print(f"Piece dropped / moved: {move}")

    def on_fen_changed(self, fen):
        self.fen_input.setText(fen)

    def load_fen_from_input(self):
        fen = self.fen_input.text().strip()
        try:
            # Validate FEN structure slightly by feeding to chess.Board
            chess.Board(fen)
            self.board_view.set(fen=fen)
        except ValueError as e:
            self.info_label.setText(f"Invalid FEN: {e}")

    def clear_board(self):
        # Empty board FEN
        empty_fen = "8/8/8/8/8/8/8/8 w - - 0 1"
        self.board_view.set(fen=empty_fen)

    def reset_to_starting(self):
        self.board_view.set(fen=chess.STARTING_FEN)

def main():
    app = QApplication(sys.argv)
    window = EditorTestWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
