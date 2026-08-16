import os
import sys
import chess
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
)
from vector_chessboard import VectorChessboard


class ExperimentWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            "Experiments: Vector Chessboard Font Playground (Approach D)"
        )
        self.resize(750, 800)

        main_layout = QVBoxLayout()

        # Header Info
        info_label = QLabel(
            "Experiment: Font Theme Tester & Approach D Vector Chessboard\n"
            "• Dynamically converts any chess font glyph path into QPixmap caches.\n"
            "• Fills hollow white pieces solid white and strokes black details."
        )
        info_label.setStyleSheet(
            "padding: 8px; background: #2c3e50; color: #ecf0f1; border-radius: 4px; font-size: 13px;"
        )
        main_layout.addWidget(info_label)

        # Chessboard Widget
        self.board_widget = VectorChessboard()
        main_layout.addWidget(self.board_widget, stretch=1)

        # Controls Layout
        controls_layout = QHBoxLayout()

        reset_btn = QPushButton("Reset Position")
        reset_btn.clicked.connect(lambda: self.board_widget.set_fen(chess.STARTING_FEN))
        controls_layout.addWidget(reset_btn)

        flip_btn = QPushButton("Flip Board")
        flip_btn.clicked.connect(self.board_widget.flip_orientation)
        controls_layout.addWidget(flip_btn)

        # Font Selector Dropdown
        font_label = QLabel("Select Font Theme:")
        controls_layout.addWidget(font_label)

        self.font_combo = QComboBox()
        exp_dir = os.path.dirname(__file__)
        ttf_files = sorted([f for f in os.listdir(exp_dir) if f.endswith(".TTF")])
        self.font_combo.addItems(ttf_files)

        if "MERIFONT.TTF" in ttf_files:
            self.font_combo.setCurrentText("MERIFONT.TTF")

        self.font_combo.currentTextChanged.connect(self.on_font_changed)
        controls_layout.addWidget(self.font_combo)

        main_layout.addLayout(controls_layout)

        # FEN Status Line
        fen_layout = QHBoxLayout()
        fen_label = QLabel("FEN:")
        fen_layout.addWidget(fen_label)

        self.fen_input = QLineEdit()
        self.fen_input.setText(self.board_widget.get_fen())
        self.fen_input.editingFinished.connect(self.on_fen_edited)
        fen_layout.addWidget(self.fen_input)

        self.board_widget.fenChanged.connect(self.fen_input.setText)
        main_layout.addLayout(fen_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def on_font_changed(self, font_filename: str):
        if font_filename:
            self.board_widget.set_font_file(font_filename)

    def on_fen_edited(self):
        fen = self.fen_input.text().strip()
        try:
            self.board_widget.set_fen(fen)
        except ValueError:
            pass


def main():
    app = QApplication(sys.argv)
    window = ExperimentWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
