import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QDialog
from src.board import BoardView
from src.promotion import PromotionDialog
import chess

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 GChessboard - Chessground Inspired")
        self.resize(800, 850)

        self.game = chess.Board()

        layout = QVBoxLayout()
        
        self.board_view = BoardView()
        self.board_view.moveMade.connect(self.handle_move)
        layout.addWidget(self.board_view)

        self.update_board_config()

        controls = QVBoxLayout()
        
        self.flip_button = QPushButton("Flip Board")
        self.flip_button.clicked.connect(self.board_view.flip_orientation)
        controls.addWidget(self.flip_button)

        self.reset_button = QPushButton("Reset Board")
        self.reset_button.clicked.connect(self.reset_board)
        controls.addWidget(self.reset_button)

        layout.addLayout(controls)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def update_board_config(self):
        # Emulate Chessground's movable.dests
        dests = {}
        for move in self.game.legal_moves:
            if move.from_square not in dests:
                dests[move.from_square] = []
            dests[move.from_square].append(move.to_square)

        # Cleaner API using .set()
        self.board_view.set(
            fen=self.game.fen(),
            movable={
                'dests': dests,
                'color': self.game.turn
            }
        )

    def handle_move(self, move):
        # Check for promotion
        piece = self.game.piece_at(move.from_square)
        if piece and piece.piece_type == chess.PAWN:
            is_promotion = (chess.square_rank(move.to_square) == 7 and piece.color == chess.WHITE) or \
                           (chess.square_rank(move.to_square) == 0 and piece.color == chess.BLACK)
            
            if is_promotion:
                # Show dialog if it's our turn
                if self.game.turn == piece.color:
                    dialog = PromotionDialog(piece.color, self)
                    promo_type = [chess.QUEEN] # Use list for closure
                    dialog.pieceSelected.connect(lambda t: promo_type.__setitem__(0, t))
                    if dialog.exec_() == QDialog.Rejected:
                        self.update_board_config()
                        return
                    move.promotion = promo_type[0]
                else:
                    # Premoves default to Queen if not already set
                    if not move.promotion:
                        move.promotion = chess.QUEEN

        if move in self.game.legal_moves:
            self.game.push(move)
            print(f"Move made: {move}")
            self.board_view.set(lastMove=move) # Highlight last move
            self.update_board_config()

    def reset_board(self):
        self.game.reset()
        self.board_view.set(lastMove=None)
        self.update_board_config()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
