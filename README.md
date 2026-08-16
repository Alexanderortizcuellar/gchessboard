# PyQt5 GChessboard

A modern, high-performance, modular chessboard widget library for PyQt5 inspired by [Chessground](https://github.com/lichess-org/chessground).

The repository provides two independent rendering architectures sharing a common state model and API:
1. **SVG / QGraphicsView Renderer** (`BoardView`): Crisp vector-based rendering with SVG piece sets and smooth scene graph animations.
2. **QPainter / Font Renderer** (`PainterChessBoard`): Lightweight, low-overhead custom widget rendering with cached piece pixmaps rasterized from chess fonts (`MERIFONT.TTF`).

---

## Features

- **State-Driven Architecture**: Managed by a centralized `BoardState` for predictable and reactive updates.
- **Dual Rendering Engines**:
  - `BoardView`: `QGraphicsView` + SVG pieces for maximum visual fidelity and smooth graphics item animations.
  - `PainterChessBoard`: `QWidget` + `QPainter` + font raster cache for ultra-low memory usage and high-FPS rendering.
- **Intelligent Interaction**:
  - Drag-and-drop piece movement (with boundary clamping).
  - Click-to-move (origin to destination).
  - **Premoves**: Queue moves during the opponent's turn, with support for multi-premove tracking.
  - **Board Editor Mode**: Free piece placement, off-board dragging to delete, and external MIME drops.
  - **Custom Shapes & Annotations**: Interactive right-click circle, cross, and arrow drawing with live preview.
  - **Custom Highlights**: Arbitrary square coloring and configurable theme highlights (last move, check, selection, premoves).
  - **Promotion**: Built-in dialog and customizable promotion handling.
- **High-Contrast Coordinates**: Dynamically contrasting file (`a`-`h`) and rank (`1`-`8`) labels that adapt to the underlying square color.

---

## Installation

Ensure you have Python 3.9+ installed, then install dependencies:

```bash
pip install -r requirements.txt
```

*(Requirements: `PyQt5`, `chess`)*

---

## Quick Start

### 1. SVG / QGraphicsView Board (`BoardView`)

```python
import sys
import chess
from PyQt5.QtWidgets import QApplication, QMainWindow
from src.board import BoardView

app = QApplication(sys.argv)
window = QMainWindow()
board = BoardView()

# Configure board state
board.set(
    fen=chess.STARTING_FEN,
    orientation=chess.WHITE,
    movable={"color": chess.WHITE}
)

board.moveMade.connect(lambda move: print(f"Move made: {move}"))

window.setCentralWidget(board)
window.resize(600, 600)
window.show()
sys.exit(app.exec_())
```

### 2. QPainter / Font Board (`PainterChessBoard`)

```python
import sys
import chess
from PyQt5.QtWidgets import QApplication, QMainWindow
from src.painter_board import PainterChessBoard

app = QApplication(sys.argv)
window = QMainWindow()
board = PainterChessBoard()

board.set(
    fen=chess.STARTING_FEN,
    orientation=chess.WHITE,
    movable={"color": chess.WHITE},
    animation={"enabled": True, "duration": 200}
)

board.moveMade.connect(lambda move: print(f"Move made: {move}"))

window.setCentralWidget(board)
window.resize(600, 600)
window.show()
sys.exit(app.exec_())
```

---

## Public API Reference

Both board implementations provide a unified `.set()` method:

### `.set(**kwargs)`

- `fen`: `str` — Position in FEN notation.
- `orientation`: `chess.Color` (`chess.WHITE` or `chess.BLACK`).
- `viewOnly`: `bool` — Disable all board interaction.
- `editable`: `bool` — Enable position editor mode (unrestricted drag & drop, off-board removal).
- `lastMove`: `Optional[chess.Move]` — Highlight the last executed move.
- `selected`: `Optional[chess.Square]` — Programmatically select a square.
- `movable`: `dict` — Movement constraints:
  - `free`: `bool` — Allow any move without legal checks.
  - `color`: `Optional[chess.Color]` — Restrict movement to white or black.
  - `dests`: `dict` — Allowed destination squares map (e.g., `{chess.E2: [chess.E3, chess.E4]}`).
- `animation`: `dict` — Animation settings:
  - `enabled`: `bool`.
  - `duration`: `int` (milliseconds).
- `shapes`: `List[dict | BoardShape]` — Shapes to render (arrows, circles, crosses).
- `drawShapes`: `bool` — Enable/disable interactive right-click shape drawing.
- `customHighlights`: `dict` — Map of squares to colors (e.g., `{chess.E4: "rgba(255, 0, 0, 0.5)"}`).
- `theme`: `dict` — Board color theme (keys: `light`, `dark`, `lastMove`, `selected`, `check`, `premove`).

### Signals

- `moveMade(chess.Move)`: Emitted when a move is completed by the user.
- `pieceDropped(chess.Move)`: Emitted when a piece is dropped on the board.
- `squareClicked(chess.Square)`: Emitted when any square is clicked.
- `fenChanged(str)`: Emitted when the board FEN position changes.
- `selectionChanged(Optional[chess.Square])`: Emitted when square selection changes.

---

## Running Demos & Benchmarks

- **Interactive SVG Board**:
  ```bash
  python main.py
  ```
- **Interactive QPainter Board**:
  ```bash
  python main_painter.py
  ```
- **Side-by-Side Dual Renderer Comparison**:
  ```bash
  python painter_board_demo.py
  ```
- **Performance Benchmark**:
  ```bash
  python benchmark.py
  ```

---

## Running Tests

Run the full pytest suite:

```bash
python -m pytest tests/
```
