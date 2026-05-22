
import sys
import chess
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PyQt5.QtCore import  QTimer
from src.view import BoardView

class PremoveTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GChessboard Multi-Premove Test")
        self.resize(800, 900)

        layout = QVBoxLayout()
        self.info_label = QLabel(
            "1. Wait 1s for White to play e4.\n"
            "2. QUEUE UP 3 PREMOVES (e.g., Ng1-f3, d2-d4, c2-c4).\n"
            "3. Every 3s, Black will move automatically.\n"
            "4. Watch your premoves fire one by one!"
        )
        self.info_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50; padding: 10px; background: #ecf0f1;")
        layout.addWidget(self.info_label)

        self.board_view = BoardView()
        layout.addWidget(self.board_view)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.board = chess.Board()
        self.board_view.set(
            fen=self.board.fen(),
            movable={'color': chess.WHITE},
            premovable={'enabled': True, 'showDests': True}
        )

        self.board_view.moveMade.connect(self.on_move_made)

        # Start sequence
        QTimer.singleShot(1500, self.white_init_move)

    def white_init_move(self):
        move = chess.Move.from_uci("e2e4")
        self.board.push(move)
        self.board_view.set(fen=self.board.fen(), lastMove=move)
        self.info_label.setText("It is BLACK's turn. QUEUE 3 PREMOVES NOW!")
        
        # Schedule 3 Black moves
        QTimer.singleShot(5000, lambda: self.opponent_plays("d7d5"))
        QTimer.singleShot(8000, lambda: self.opponent_plays("c7c6"))
        QTimer.singleShot(11000, lambda: self.opponent_plays("e7e6"))

    def opponent_plays(self, uci):
        if not self.board.is_game_over():
            move = chess.Move.from_uci(uci)
            if move in self.board.legal_moves:
                self.board.push(move)
                print(f"Opponent moved: {move}")
                self.board_view.set(fen=self.board.fen(), lastMove=move)
                # If we have a premove, the view will emit moveMade immediately
            else:
                print(f"Simulated move {uci} became illegal!")

    def on_move_made(self, move):
        print(f"Move Signal Received: {move}")
        if move in self.board.legal_moves:
            self.board.push(move)
            self.board_view.set(fen=self.board.fen(), lastMove=move)
            self.info_label.setText(f"You played: {move}. Queue size: {len(self.board_view._state.premoves)}")

def main():
    app = QApplication(sys.argv)
    window = PremoveTestWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
