"""
pgn_navigator_demo.py — Interactive PGN Navigator & Animation Stress-Tester.

Features:
- Full PGN navigation with sample famous games or custom PGN loading.
- Move list with interactive move-clicking and active move highlighting.
- Multiple input methods:
    * Left / Right arrow keys (with key-repeat hold testing)
    * Mouse wheel scrolling (over board or move list)
    * Step forward / backward, First / Last buttons
    * Autoplay mode with adjustable speed
- Animation queue & strategy comparison modes:
    1. Direct FEN (Current behavior): calls set_fen immediately on every event.
    2. Sequential Queue (ChessBase style): waits for move animation to finish before starting the next.
    3. Adaptive / Fast-Forward (Lichess style): cancels/snaps intermediate steps when inputs arrive rapidly.
- Switchable board renderer: BoardView (SVG) vs PainterChessBoard (QPainter).
"""

import sys
import os
import io
import time
import chess
import chess.pgn

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QSlider,
    QGroupBox,
    QFileDialog,
)
from PyQt5.QtCore import Qt, QTimer, QObject, QEvent

# Make sure src package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.board import BoardView
from src.painter_board import PainterChessBoard


class GlobalKeyFilter(QObject):
    """Global event filter to ensure arrow keys always navigate moves regardless of widget focus."""
    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Right, Qt.Key_Down):
                self.window.step_forward()
                return True
            elif key in (Qt.Key_Left, Qt.Key_Up):
                self.window.step_backward()
                return True
            elif key == Qt.Key_Home:
                self.window.navigate_to(0, clear_queue=True)
                return True
            elif key == Qt.Key_End:
                self.window.navigate_to(len(self.window.node_list) - 1, clear_queue=True)
                return True
        return super().eventFilter(obj, event)


SAMPLE_GAMES = {
    "Kasparov vs. Topalov (Wijk aan Zee 1999 - 'Kasparov's Immortal')": """[Event "Hoogovens A Tournament"]
[Site "Wijk aan Zee NED"]
[Date "1999.01.20"]
[Round "4"]
[White "Garry Kasparov"]
[Black "Veselin Topalov"]
[Result "1-0"]
[ECO "B07"]

1. e4 d6 2. d4 Nf6 3. Nc3 g6 4. Be3 Bg7 5. Qd2 c6 6. f3 b5 7. Nge2 Nbd7 8. Bh6
Bxh6 9. Qxh6 Bb7 10. a3 e5 11. O-O-O Qe7 12. Kb1 a6 13. Nc1 O-O-O 14. Nb3 exd4
15. Rxd4 c5 16. Rd1 Nb6 17. g3 Kb8 18. Na5 Ba8 19. Bh3 d5 20. Qf4+ Ka7 21. Rhe1
d4 22. Nd5 Nbxd5 23. exd5 Qd6 24. Rxd4 cxd4 25. Re7+ Kb6 26. Qxd4+ Kxa5 27. b4+
Ka4 28. Qc3 Qxd5 29. Ra7 Bb7 30. Rxb7 Qc4 31. Qxf6 Kxa3 32. Qxa6+ Kxb4 33. c3+
Kxc3 34. Qa1+ Kd2 35. Qb2+ Kd1 36. Bf1 Rd2 37. Rd7 Rxd7 38. Bxc4 bxc4 39. Qxh8
Rd3 40. Qa8 c3 41. Qa4+ Ke1 42. f4 f5 43. Kc1 Rd2 44. Qa7 1-0
""",
    "Morphy vs. Duke of Brunswick / Count Isouard (Paris Opera 1858)": """[Event "Paris Opera"]
[Site "Paris FRA"]
[Date "1858.11.02"]
[Round "1"]
[White "Paul Morphy"]
[Black "Duke Karl of Brunswick and Count Isouard"]
[Result "1-0"]
[ECO "C41"]

1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7 8.
Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7 14.
Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0
""",
    "Byrne vs. Fischer (New York 1956 - 'Game of the Century')": """[Event "Third Rosenwald Trophy"]
[Site "New York, NY USA"]
[Date "1956.10.17"]
[Round "8"]
[White "Donald Byrne"]
[Black "Robert James Fischer"]
[Result "0-1"]
[ECO "D92"]

1. Nf3 Nf6 2. c4 g6 3. Nc3 Bg7 4. d4 O-O 5. Bf4 d5 6. Qb3 dxc4 7. Qxc4 c6 8. e4
Nbd7 9. Rd1 Nb6 10. Qc5 Bg4 11. Bg5 Na4 12. Qa3 Nxc3 13. bxc3 Nxe4 14. Bxe7 Qb6
15. Bc4 Nxc3 16. Bc5 Rfe8+ 17. Kf1 Be6 18. Bxb6 Bxc4+ 19. Kg1 Ne2+ 20. Kf1 Nxd4+
21. Kg1 Ne2+ 22. Kf1 Nc3+ 23. Kg1 axb6 24. Qb4 Ra4 25. Qxb6 Nxd1 26. h3 Rxa2 27.
Kh2 Nxf2 28. Re1 Rxe1 29. Qd8+ Bf8 30. Nxe1 Bd5 31. Nf3 Ne4 32. Qb8 b5 33. h4 h5
34. Ne5 Kg7 35. Kg1 Bc5+ 36. Kf1 Ng3+ 37. Ke1 Bb4+ 38. Kd1 Bb3+ 39. Kc1 Ne2+ 40.
Kb1 Nc3+ 41. Kc1 Rc2# 0-1
""",
}


class PgnNavigatorDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GChessboard — PGN Navigator & Animation Stress Tester")
        self.resize(1150, 750)

        # Game state tracking
        self.game = None
        self.node_list = []  # List of (ply_index, node, fen, move, san)
        self.current_ply = 0

        # Animation & Timing management
        self._anim_end_time = 0.0

        # Autoplay timer
        self.autoplay_timer = QTimer(self)
        self.autoplay_timer.timeout.connect(self._autoplay_step)

        # Last key/wheel interaction timestamp for adaptive mode
        self._last_input_time = 0.0

        # Global event filter for arrows
        self._key_filter = GlobalKeyFilter(self)
        app = QApplication.instance()
        if app:
            app.installEventFilter(self._key_filter)

        self._build_ui()
        self._load_sample_game(list(SAMPLE_GAMES.keys())[0])

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # --- Left: Board Column ---
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # Renderer Switcher Header
        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("<b>Board Renderer:</b>"))
        self.renderer_combo = QComboBox()
        self.renderer_combo.setFocusPolicy(Qt.NoFocus)
        self.renderer_combo.addItems(["SVG Board (BoardView)", "QPainter Board (PainterChessBoard)"])
        self.renderer_combo.currentIndexChanged.connect(self._switch_renderer)
        header_row.addWidget(self.renderer_combo, stretch=1)
        left_layout.addLayout(header_row)

        # Board container
        self.board_container = QWidget()
        self.board_layout = QVBoxLayout(self.board_container)
        self.board_layout.setContentsMargins(0, 0, 0, 0)

        self.svg_board = BoardView()
        self.svg_board.set(viewOnly=True)
        self.painter_board = PainterChessBoard()
        self.painter_board.set(viewOnly=True)
        self.painter_board.hide()

        self.board_layout.addWidget(self.svg_board)
        self.board_layout.addWidget(self.painter_board)
        left_layout.addWidget(self.board_container, stretch=1)

        # Navigation Buttons Row
        nav_row = QHBoxLayout()
        self.btn_first = QPushButton("|< (Start)")
        self.btn_prev = QPushButton("< (Prev)")
        self.btn_next = QPushButton("> (Next)")
        self.btn_last = QPushButton(">| (End)")

        for b in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            b.setFocusPolicy(Qt.NoFocus)

        self.btn_first.clicked.connect(lambda: self.navigate_to(0, is_jump=True))
        self.btn_prev.clicked.connect(self.step_backward)
        self.btn_next.clicked.connect(self.step_forward)
        self.btn_last.clicked.connect(lambda: self.navigate_to(len(self.node_list) - 1, is_jump=True))

        nav_row.addWidget(self.btn_first)
        nav_row.addWidget(self.btn_prev)
        nav_row.addWidget(self.btn_next)
        nav_row.addWidget(self.btn_last)
        left_layout.addLayout(nav_row)

        # Autoplay & Flip Row
        action_row = QHBoxLayout()
        self.btn_play = QPushButton("▶ Autoplay")
        self.btn_play.setCheckable(True)
        self.btn_play.setFocusPolicy(Qt.NoFocus)
        self.btn_play.toggled.connect(self._toggle_autoplay)
        action_row.addWidget(self.btn_play)

        btn_flip = QPushButton("Flip Board")
        btn_flip.setFocusPolicy(Qt.NoFocus)
        btn_flip.clicked.connect(self._flip_board)
        action_row.addWidget(btn_flip)
        left_layout.addLayout(action_row)

        root_layout.addWidget(left_col, stretch=3)

        # --- Right: Moves & Controls Column ---
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # Game Selector Group
        game_grp = QGroupBox("Select / Load PGN")
        game_grp_layout = QVBoxLayout(game_grp)
        self.game_combo = QComboBox()
        self.game_combo.setFocusPolicy(Qt.NoFocus)
        self.game_combo.addItems(list(SAMPLE_GAMES.keys()))
        self.game_combo.currentIndexChanged.connect(self._on_sample_selected)
        game_grp_layout.addWidget(self.game_combo)

        load_btn = QPushButton("Open PGN File...")
        load_btn.setFocusPolicy(Qt.NoFocus)
        load_btn.clicked.connect(self._open_pgn_file)
        game_grp_layout.addWidget(load_btn)
        right_layout.addWidget(game_grp)

        # Move Table
        self.move_table = QTableWidget()
        self.move_table.setColumnCount(3)
        self.move_table.setHorizontalHeaderLabels(["#", "White", "Black"])
        self.move_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.move_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.move_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.move_table.setSelectionMode(QTableWidget.SingleSelection)
        self.move_table.setFocusPolicy(Qt.NoFocus)
        self.move_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.move_table.cellClicked.connect(self._on_table_cell_clicked)
        right_layout.addWidget(self.move_table, stretch=1)

        # Queue / Animation Experiment Controls
        exp_grp = QGroupBox("Animation Strategy (Stress Testing)")
        exp_layout = QVBoxLayout(exp_grp)

        # Strategy selector
        strat_row = QHBoxLayout()
        strat_row.addWidget(QLabel("<b>Strategy:</b>"))
        self.strat_combo = QComboBox()
        self.strat_combo.setFocusPolicy(Qt.NoFocus)
        self.strat_combo.addItems([
            "1. Direct FEN (Raw set_fen per event)",
            "2. Animation-Locked Gate (ChessBase — drops repeats, zero lag)",
            "3. Adaptive Fast-Forward (Lichess — dynamic speedup on rapid inputs)",
        ])
        strat_row.addWidget(self.strat_combo, stretch=1)
        exp_layout.addLayout(strat_row)

        # Animation Duration Slider
        dur_row = QHBoxLayout()
        self.lbl_duration = QLabel("Duration: 200 ms")
        self.slider_duration = QSlider(Qt.Horizontal)
        self.slider_duration.setFocusPolicy(Qt.NoFocus)
        self.slider_duration.setRange(0, 600)
        self.slider_duration.setValue(200)
        self.slider_duration.valueChanged.connect(self._on_duration_changed)
        dur_row.addWidget(self.lbl_duration)
        dur_row.addWidget(self.slider_duration)
        exp_layout.addLayout(dur_row)

        # Status / Diagnostics Label
        self.lbl_status = QLabel("Position: 0 / 0")
        self.lbl_status.setStyleSheet("color: #444; font-weight: bold;")
        exp_layout.addWidget(self.lbl_status)

        # Helper hint
        hint = QLabel(
            "<i>Tip: Hold down Left/Right Arrow keys or use Mouse Wheel.<br>"
            "Strategy 2 locks rate to animation speed with zero lag on release.<br>"
            "Strategy 3 snaps instantly when scrolling fast, but animates jumps.</i>"
        )
        hint.setStyleSheet("color: #666; font-size: 11px;")
        exp_layout.addWidget(hint)

        right_layout.addWidget(exp_grp)
        root_layout.addWidget(right_col, stretch=2)

    # -----------------------------------------------------------------------
    # Active board access
    # -----------------------------------------------------------------------
    @property
    def active_board(self):
        return self.svg_board if self.renderer_combo.currentIndex() == 0 else self.painter_board

    def _switch_renderer(self, index):
        if index == 0:
            self.painter_board.hide()
            self.svg_board.show()
        else:
            self.svg_board.hide()
            self.painter_board.show()
        self._sync_board(instant=True)

    def _flip_board(self):
        self.svg_board.flip_orientation()
        self.painter_board.flip_orientation()

    # -----------------------------------------------------------------------
    # PGN Parsing and Move Table Setup
    # -----------------------------------------------------------------------
    def _load_sample_game(self, title: str):
        pgn_text = SAMPLE_GAMES[title]
        self._load_pgn_text(pgn_text)

    def _on_sample_selected(self, index):
        title = self.game_combo.currentText()
        if title in SAMPLE_GAMES:
            self._load_sample_game(title)

    def _open_pgn_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open PGN File", "", "PGN Files (*.pgn);;All Files (*)")
        if filepath:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                self._load_pgn_text(f.read())

    def _load_pgn_text(self, text: str):
        self.autoplay_timer.stop()
        self.btn_play.setChecked(False)

        pgn_io = io.StringIO(text)
        self.game = chess.pgn.read_game(pgn_io)
        if not self.game:
            return

        # Flatten game into node list: (ply, node, fen, move, san)
        self.node_list = []
        board = self.game.board()
        self.node_list.append((0, self.game, board.fen(), None, "Start"))

        node = self.game
        ply = 1
        while node.variations:
            next_node = node.variation(0)
            move = next_node.move
            san = board.san(move)
            board.push(move)
            self.node_list.append((ply, next_node, board.fen(), move, san))
            node = next_node
            ply += 1

        self._populate_table()
        self.current_ply = 0
        self._sync_board(instant=True)
        self._update_status()

    def _populate_table(self):
        self.move_table.setRowCount(0)
        # Group plies into full moves
        total_moves = (len(self.node_list) - 1 + 1) // 2
        self.move_table.setRowCount(total_moves)

        for ply in range(1, len(self.node_list)):
            move_num = (ply + 1) // 2
            row = move_num - 1
            col = 1 if (ply % 2 != 0) else 2

            _, _, _, _, san = self.node_list[ply]
            item = QTableWidgetItem(san)
            item.setData(Qt.UserRole, ply)
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            num_item = QTableWidgetItem(f"{move_num}.")
            num_item.setTextAlignment(Qt.AlignCenter)
            num_item.setFlags(Qt.NoItemFlags)
            self.move_table.setItem(row, 0, num_item)
            self.move_table.setItem(row, col, item)

    def _highlight_table_move(self, ply: int):
        self.move_table.blockSignals(True)
        if ply == 0:
            self.move_table.clearSelection()
        else:
            row = (ply - 1) // 2
            col = 1 if (ply % 2 != 0) else 2
            self.move_table.setCurrentCell(row, col)
            item = self.move_table.item(row, col)
            if item:
                self.move_table.scrollToItem(item)
        self.move_table.blockSignals(False)

    def _on_table_cell_clicked(self, row, col):
        if col == 0:
            return
        item = self.move_table.item(row, col)
        if item:
            ply = item.data(Qt.UserRole)
            if ply is not None:
                self.navigate_to(ply, is_jump=True)

    # -----------------------------------------------------------------------
    # Navigation & Strategy Dispatcher
    # -----------------------------------------------------------------------
    def step_forward(self):
        if not self.node_list:
            return
        if self.current_ply < len(self.node_list) - 1:
            self.navigate_to(self.current_ply + 1, is_jump=False)

    def step_backward(self):
        if not self.node_list:
            return
        if self.current_ply > 0:
            self.navigate_to(self.current_ply - 1, is_jump=False)

    def navigate_to(self, target_ply: int, is_jump: bool = False):
        if not self.node_list:
            return
        target_ply = max(0, min(len(self.node_list) - 1, target_ply))
        if target_ply == self.current_ply:
            return

        now = time.time()
        delta_ms = (now - self._last_input_time) * 1000.0
        self._last_input_time = now

        dur_sec = self.slider_duration.value() / 1000.0
        strat = self.strat_combo.currentIndex()

        if is_jump:
            # Discrete jumps (Start, End, clicking table cell):
            # Always perform full smooth FEN transition animation!
            self.current_ply = target_ply
            self._sync_board(instant=False)
            self._anim_end_time = now + dur_sec
            self._highlight_table_move(target_ply)
            self._update_status()
            return

        # Continuous / step-by-step navigation:
        if strat == 0:
            # 1. Direct FEN (Raw set_fen per event — baseline behavior)
            self.current_ply = target_ply
            self._sync_board(instant=False)
            self._highlight_table_move(target_ply)
            self._update_status()

        elif strat == 1:
            # 2. Animation-Locked Gate (ChessBase style)
            # If previous move animation is still active, discard repeat input!
            if now < self._anim_end_time:
                return

            self.current_ply = target_ply
            self._sync_board(instant=False)
            self._anim_end_time = now + dur_sec
            self._highlight_table_move(target_ply)
            self._update_status()

        elif strat == 2:
            # 3. Adaptive Fast-Forward (Lichess style)
            # If rapid navigation is detected (< 90ms between steps), fast forward/snap
            if delta_ms < 90:
                self.current_ply = target_ply
                self._sync_board(instant=True)
            else:
                self.current_ply = target_ply
                self._sync_board(instant=False)
            self._highlight_table_move(target_ply)
            self._update_status()

    def _sync_board(self, instant: bool = False):
        if not self.node_list:
            return
        ply, _, fen, move, _ = self.node_list[self.current_ply]
        dur = 0 if instant else self.slider_duration.value()

        # Update both boards so user can flip or compare
        self.svg_board.set(
            fen=fen,
            lastMove=move,
            animation={"enabled": (dur > 0), "duration": dur},
        )
        self.painter_board.set(
            fen=fen,
            lastMove=move,
            animation={"enabled": (dur > 0), "duration": dur},
        )

    def _on_duration_changed(self, val):
        self.lbl_duration.setText(f"Duration: {val} ms")

    def _update_status(self):
        total = len(self.node_list) - 1 if self.node_list else 0
        self.lbl_status.setText(f"Position: {self.current_ply} / {total}")

    def _sync_board(self, instant: bool = False):
        if not self.node_list:
            return
        ply, _, fen, move, _ = self.node_list[self.current_ply]
        dur = 0 if instant else self.slider_duration.value()

        # Update both boards so user can flip or compare
        self.svg_board.set(
            fen=fen,
            lastMove=move,
            animation={"enabled": (dur > 0), "duration": dur},
        )
        self.painter_board.set(
            fen=fen,
            lastMove=move,
            animation={"enabled": (dur > 0), "duration": dur},
        )

    def _on_duration_changed(self, val):
        self.lbl_duration.setText(f"Duration: {val} ms")

    # -----------------------------------------------------------------------
    # Keyboard & Mouse Wheel Event Stress-Testing
    # -----------------------------------------------------------------------
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Right or key == Qt.Key_Down:
            self.step_forward()
            event.accept()
        elif key == Qt.Key_Left or key == Qt.Key_Up:
            self.step_backward()
            event.accept()
        elif key == Qt.Key_Home:
            self.navigate_to(0)
            event.accept()
        elif key == Qt.Key_End:
            self.navigate_to(len(self.node_list) - 1)
            event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        # Mouse wheel stress testing
        delta = event.angleDelta().y()
        if delta < 0:
            self.step_forward()
        elif delta > 0:
            self.step_backward()
        event.accept()

    # -----------------------------------------------------------------------
    # Autoplay
    # -----------------------------------------------------------------------
    def _toggle_autoplay(self, enabled):
        if enabled:
            self.btn_play.setText("⏸ Pause")
            dur = self.slider_duration.value()
            self.autoplay_timer.start(max(50, dur + 150))
        else:
            self.btn_play.setText("▶ Autoplay")
            self.autoplay_timer.stop()

    def _autoplay_step(self):
        if self.current_ply < len(self.node_list) - 1:
            self.step_forward()
        else:
            self.btn_play.setChecked(False)


def main():
    app = QApplication(sys.argv)
    window = PgnNavigatorDemo()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
