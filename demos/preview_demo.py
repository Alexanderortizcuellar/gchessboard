"""
preview_demo.py — Interactive GUI to test and experience the temporary preview state.

Run with:
    python preview_demo.py

Features:
- Play moves normally on the active board (drag-and-drop, premoves, click-to-move).
- Hover over any engine variation / opening move in the right panel to see a live ghost preview.
- Move mouse away to immediately restore the active game state without losing position or queued premoves.
- Switch between QPainter/Font renderer and SVG/QGraphicsView renderer.
- Tweak ghost opacity and background dimming live with UI sliders and toggles.
"""

import sys
import os
import chess

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QSlider,
    QCheckBox,
    QGroupBox,
    QFrame,
    QLineEdit,
    QTabWidget,
)
from PyQt5.QtCore import Qt, pyqtSignal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.board import BoardView
from src.painter_board import PainterChessBoard
from src.models import BoardShape


class HoverCard(QFrame):
    """A card widget that emits hoverEntered and hoverLeft signals for preview testing."""

    hoverEntered = pyqtSignal(dict)
    hoverLeft = pyqtSignal()

    def __init__(self, title: str, description: str, preview_data: dict, parent=None):
        super().__init__(parent)
        self.preview_data = preview_data
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            """
            HoverCard {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px;
            }
            HoverCard:hover {
                background-color: #e0f2fe;
                border: 1px solid #38bdf8;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        t_lbl = QLabel(f"<b>{title}</b>")
        t_lbl.setStyleSheet("color: #0f172a;")
        d_lbl = QLabel(description)
        d_lbl.setStyleSheet("color: #475569; font-size: 11px;")
        d_lbl.setWordWrap(True)

        layout.addWidget(t_lbl)
        layout.addWidget(d_lbl)

    def enterEvent(self, event):
        self.hoverEntered.emit(self.preview_data)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hoverLeft.emit()
        super().leaveEvent(event)


class PreviewDemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            "GChessboard — Temporary Preview State Demo (ChessBase Style)"
        )
        self.resize(1180, 720)

        # Main layout
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(16)

        # --- Left: Chessboard area ---
        board_panel = QWidget()
        board_layout = QVBoxLayout(board_panel)
        board_layout.setContentsMargins(0, 0, 0, 0)
        board_layout.setSpacing(10)

        # Status badge
        self.status_banner = QLabel("Active Game State: Real Position (Interactive)")
        self.status_banner.setAlignment(Qt.AlignCenter)
        self.status_banner.setStyleSheet(
            """
            QLabel {
                background-color: #ecfdf5;
                color: #065f46;
                border: 1px solid #a7f3d0;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 12px;
            }
            """
        )
        board_layout.addWidget(self.status_banner)

        # Board Tab (Painter / Font vs SVG / GraphicsView)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { height: 28px; padding: 0 16px; }")

        self.painter_board = PainterChessBoard()
        self.painter_board.set(
            fen=chess.STARTING_FEN,
            orientation=chess.WHITE,
            movable={"color": chess.WHITE},
            premovable={"enabled": True},
            animation={"enabled": True, "duration": 200},
        )
        self.painter_board.moveMade.connect(self._on_move_made)

        self.svg_board = BoardView()
        self.svg_board.set(
            fen=chess.STARTING_FEN,
            orientation=chess.WHITE,
            movable={"color": chess.WHITE},
            premovable={"enabled": True},
            animation={"enabled": True, "duration": 200},
        )
        self.svg_board.moveMade.connect(self._on_move_made)

        self.tabs.addTab(self.painter_board, "QPainter / Font Board (Lightweight)")
        self.tabs.addTab(self.svg_board, "SVG / QGraphicsView Board")
        board_layout.addWidget(self.tabs, stretch=1)

        # Quick board controls
        btn_bar = QHBoxLayout()
        reset_btn = QPushButton("Reset Game Position")
        reset_btn.clicked.connect(self._reset_game)
        flip_btn = QPushButton("Flip Orientation")
        flip_btn.clicked.connect(self._flip_board)
        btn_bar.addWidget(reset_btn)
        btn_bar.addWidget(flip_btn)
        board_layout.addLayout(btn_bar)

        root_layout.addWidget(board_panel, stretch=6)

        # --- Right: Variations & Preview Controls ---
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(12)

        # Title & instructions
        head_box = QGroupBox("ChessBase-Style Variation Preview")
        head_lay = QVBoxLayout(head_box)
        info_lbl = QLabel(
            "<b>Hover over any variation below</b> to temporarily ghost-preview "
            "the position with move highlights and threat arrows.<br><br>"
            "Move mouse away to immediately restore your active game state."
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("color: #334155; font-size: 12px;")
        head_lay.addWidget(info_lbl)
        control_layout.addWidget(head_box)

        # Preview visual settings
        settings_box = QGroupBox("Ghost Visual Style Settings")
        set_lay = QGridLayout(settings_box)

        set_lay.addWidget(QLabel("Ghost Piece Opacity:"), 0, 0)
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setValue(80)
        self.opacity_val_lbl = QLabel("0.80")
        self.opacity_slider.valueChanged.connect(
            lambda v: self.opacity_val_lbl.setText(f"{v / 100:.2f}")
        )
        set_lay.addWidget(self.opacity_slider, 0, 1)
        set_lay.addWidget(self.opacity_val_lbl, 0, 2)

        self.dim_check = QCheckBox("Dim Background Squares (Subtle Dark Veil)")
        self.dim_check.setChecked(False)
        set_lay.addWidget(self.dim_check, 1, 0, 1, 3)
        control_layout.addWidget(settings_box)

        # Preset Variation Hover Cards
        cards_box = QGroupBox("Hover Over Variations to Preview")
        cards_lay = QVBoxLayout(cards_box)
        cards_lay.setSpacing(8)

        variations = [
            (
                "Ruy Lopez — 3. Bb5 (Spanish Opening)",
                "Pinning the knight and fighting for the center.\nMove: f1 -> b5",
                {
                    "fen": "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 1 3",
                    "last_move": "f1b5",
                    "shapes": [
                        BoardShape(
                            type="arrow",
                            orig=chess.B5,
                            dest=chess.E8,
                            color="rgba(239, 68, 68, 0.75)",
                            width=5.0,
                        ),
                    ],
                },
            ),
            (
                "Italian Game — 3. Bc4 (Giuoco Piano)",
                "Targeting the vulnerable f7 square.\nMove: f1 -> c4",
                {
                    "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 1 3",
                    "last_move": "f1c4",
                    "shapes": [
                        BoardShape(
                            type="arrow",
                            orig=chess.C4,
                            dest=chess.F7,
                            color="rgba(220, 38, 38, 0.75)",
                            width=5.0,
                        ),
                        BoardShape(
                            type="circle",
                            orig=chess.F7,
                            color="rgba(220, 38, 38, 0.75)",
                            width=4.0,
                        ),
                    ],
                },
            ),
            (
                "Scotch Game — 3. d4 (Center Break)",
                "Striking immediately at Black's e5 pawn.\nMove: d2 -> d4",
                {
                    "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 3",
                    "last_move": "d2d4",
                    "shapes": [
                        BoardShape(
                            type="arrow",
                            orig=chess.D4,
                            dest=chess.E5,
                            color="rgba(16, 185, 129, 0.8)",
                            width=5.0,
                        ),
                    ],
                },
            ),
            (
                "Fried Liver Threat — 4. Ng5 (Tactical Attack)",
                "Double attacking f7 with Bishop and Knight.\nMove: f3 -> g5",
                {
                    "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p1N1/2B1P3/8/PPPP1PPP/RNBQK2R b KQkq - 3 4",
                    "last_move": "f3g5",
                    "shapes": [
                        BoardShape(
                            type="arrow",
                            orig=chess.G5,
                            dest=chess.F7,
                            color="rgba(239, 68, 68, 0.85)",
                            width=5.5,
                        ),
                        BoardShape(
                            type="arrow",
                            orig=chess.C4,
                            dest=chess.F7,
                            color="rgba(239, 68, 68, 0.85)",
                            width=5.5,
                        ),
                        BoardShape(
                            type="circle",
                            orig=chess.F7,
                            color="rgba(239, 68, 68, 0.85)",
                            width=5.0,
                        ),
                    ],
                },
            ),
        ]

        for title, desc, pdata in variations:
            card = HoverCard(title, desc, pdata)
            card.hoverEntered.connect(self._activate_preview)
            card.hoverLeft.connect(self._clear_preview)
            cards_lay.addWidget(card)

        control_layout.addWidget(cards_box)

        # Custom FEN Preview input
        custom_box = QGroupBox("Custom FEN Preview")
        custom_lay = QVBoxLayout(custom_box)
        self.custom_fen_input = QLineEdit("8/8/8/4k3/8/8/4K3/4R3 w - - 0 1")
        self.custom_fen_input.setPlaceholderText("Paste arbitrary FEN string...")
        btn_row = QHBoxLayout()
        prev_custom_btn = QPushButton("Preview Custom FEN")
        prev_custom_btn.clicked.connect(self._preview_custom_fen)
        clear_custom_btn = QPushButton("Clear Preview")
        clear_custom_btn.clicked.connect(self._clear_preview)
        btn_row.addWidget(prev_custom_btn)
        btn_row.addWidget(clear_custom_btn)

        custom_lay.addWidget(self.custom_fen_input)
        custom_lay.addLayout(btn_row)
        control_layout.addWidget(custom_box)

        control_layout.addStretch(1)
        root_layout.addWidget(control_panel, stretch=5)

    def _get_active_board(self):
        return self.tabs.currentWidget()

    def _activate_preview(self, preview_data: dict):
        opacity = self.opacity_slider.value() / 100.0
        dim_board = self.dim_check.isChecked()

        fen = preview_data.get("fen")
        last_move = preview_data.get("last_move")
        shapes = preview_data.get("shapes", [])

        # Apply preview on both boards
        self.painter_board.set_preview(
            fen=fen,
            last_move=last_move,
            shapes=shapes,
            opacity=opacity,
            dim_board=dim_board,
        )
        self.svg_board.set_preview(
            fen=fen,
            last_move=last_move,
            shapes=shapes,
            opacity=opacity,
            dim_board=dim_board,
        )

        self.status_banner.setText(
            "Preview Mode: Ghost Variation Active (Non-destructive)"
        )
        self.status_banner.setStyleSheet(
            """
            QLabel {
                background-color: #eff6ff;
                color: #1d4ed8;
                border: 1px solid #93c5fd;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 12px;
            }
            """
        )

    def _clear_preview(self):
        self.painter_board.clear_preview()
        self.svg_board.clear_preview()

        self.status_banner.setText("Active Game State: Real Position (Interactive)")
        self.status_banner.setStyleSheet(
            """
            QLabel {
                background-color: #ecfdf5;
                color: #065f46;
                border: 1px solid #a7f3d0;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 12px;
            }
            """
        )

    def _preview_custom_fen(self):
        fen = self.custom_fen_input.text().strip()
        if fen:
            self._activate_preview({"fen": fen})

    def _on_move_made(self, move: chess.Move):
        # Sync move to the other board
        sender = self.sender()
        target = self.svg_board if sender == self.painter_board else self.painter_board

        board = chess.Board(sender._state.fen)
        target.set(fen=board.fen(), lastMove=move)

    def _reset_game(self):
        self._clear_preview()
        self.painter_board.set(
            fen=chess.STARTING_FEN,
            lastMove=None,
            shapes=[],
            customHighlights={},
        )
        self.svg_board.set(
            fen=chess.STARTING_FEN,
            lastMove=None,
            shapes=[],
            customHighlights={},
        )

    def _flip_board(self):
        self.painter_board.flip_orientation()
        self.svg_board.set(
            orientation=chess.BLACK
            if self.svg_board._state.orientation == chess.WHITE
            else chess.WHITE
        )


def main():
    app = QApplication(sys.argv)
    window = PreviewDemoWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
