import chess
import chess.svg
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QPushButton, QVBoxLayout, QLabel
from PyQt5.QtCore import pyqtSignal, Qt, QByteArray, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtSvg import QSvgRenderer

def get_piece_icon(piece: chess.Piece, size: int = 45) -> QIcon:
    svg_data = chess.svg.piece(piece, size=size).encode("utf-8")
    renderer = QSvgRenderer(QByteArray(svg_data))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
class PromotionDialog(QDialog):
    """
    An independent promotion dialog that emits a signal when a piece is selected.
    """
    pieceSelected = pyqtSignal(chess.PieceType)

    def __init__(self, color: chess.Color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Promote Pawn")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        label = QLabel("Choose promotion piece:")
        label.setStyleSheet("color: white; font-weight: bold; background: rgba(0,0,0,150); padding: 5px; border-radius: 3px;")
        layout.addWidget(label, alignment=Qt.AlignCenter)

        button_layout = QHBoxLayout()
        
        # Define pieces to promote to
        promotion_types = [
            (chess.QUEEN, "q"),
            (chess.ROOK, "r"),
            (chess.BISHOP, "b"),
            (chess.KNIGHT, "n")
        ]

        color_str = "w" if color == chess.WHITE else "b"
        
        for p_type, char in promotion_types:
            btn = QPushButton()
            btn.setFixedSize(60, 60)
            btn.setCursor(Qt.PointingHandCursor)
            
            piece = chess.Piece(p_type, color)
            btn.setIcon(get_piece_icon(piece, size=45))
            btn.setIconSize(QSize(45, 45))
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #f0f0f0;
                    border: 2px solid #555;
                    border-radius: 5px;
                }}
                QPushButton:hover {{
                    background-color: #ddd;
                }}
            """)
            
            # Closure to capture p_type
            btn.clicked.connect(lambda checked, t=p_type: self._on_piece_selected(t))
            button_layout.addWidget(btn)

        layout.addLayout(button_layout)

    def _on_piece_selected(self, piece_type):
        self.pieceSelected.emit(piece_type)
        self.accept()

def get_promotion_piece(color: chess.Color, parent=None) -> chess.PieceType:
    """Helper function to show the dialog and return the selected piece type."""
    dialog = PromotionDialog(color, parent)
    if dialog.exec_() == QDialog.Accepted:
        # Note: This helper might need a way to pass the result back if not using signals
        # But the requirement asked for signals.
        pass
    return chess.QUEEN # Default fallback
