# PyQt5 GChessboard - Chessground Inspired Widget

A modern, high-performance chessboard widget for PyQt5, built using the QGraphics Framework and inspired by the interaction quality and architecture of [Chessground](https://github.com/lichess-org/chessground).

## Features

- **State-Driven Architecture**: Managed by a centralized `BoardState` for predictable and reactive updates.
- **Smooth Animations**: High-quality sliding animations for piece movements and board transitions using `QPropertyAnimation`.
- **Intelligent Interaction**:
  - Drag-and-drop piece movement.
  - Click-Click (Origin-Destination) movement strategy.
  - Piece dragging is clamped within the board boundaries.
  - **Premoves**: Queue moves during the opponent's turn. Supports multiple premoves for the same piece by tracking "in-flight" moves.
  - **Promotion**: Customizable promotion dialog for pawn reach (Upcoming).
  - Selection management with intuitive deselection and re-selection.
- **Lichess-style Visuals**:
  - Legal move highlights (small centered dots for empty squares, hollow circles for captures).
  - Last move highlights.
  - **Improved Check highlights**: Vibrant radial gradients on the king's square.
  - **High-Contrast Coordinates**: File and rank labels automatically contrast with their underlying square color.
  - Highly responsive scaling: all elements (pieces, squares, coordinates) scale linearly with the window size.
- **Efficient Rendering**:
  - SVG-based piece rendering using `QSvgRenderer`.
  - Advanced renderer caching to minimize overhead.
  - Graphics item reuse (pieces and squares are moved, not recreated, during state changes).
- **Public API**: A unified `.set()` method inspired by Chessground for easy configuration from external code.

## Installation

Requires `PyQt5` and `python-chess`.

```bash
pip install PyQt5 python-chess
```

## Architecture

The project is modularized for maintainability:

- `src/models.py`: Defines the `BoardState` and configuration dataclasses.
- `src/scene.py`: Implements `BoardScene`, handling rendering, highlights, and animations.
- `src/view.py`: Implements `BoardView`, handling user input and coordinate mapping.
- `src/pieces.py`: Handles SVG piece rendering and caching.

## Public API

The primary way to interact with the widget is via the `.set()` method.

### `.set(**kwargs)`

Updates the widget state and refreshes the display.

- `fen`: str - The board position in FEN format.
- `orientation`: chess.Color - `chess.WHITE` or `chess.BLACK`.
- `viewOnly`: bool - If true, interactions are disabled.
- `editable`: bool - If true, enables position editor mode. Pieces can be dragged and dropped anywhere to configure the position, and dragging a piece off the board deletes it. In this mode, only drag-and-drop is supported (click-to-move is disabled), and all legal move logic/highlights are bypassed. Drag-and-drop operations or API calls will update the internal FEN directly and emit `fenChanged` and `pieceDropped`.
- `lastMove`: Optional[chess.Move] - Highlight the last move.
- `selected`: Optional[chess.Square] - Programmatically select a square.
- `movable`: dict - Configuration for piece movement:
  - `free`: bool - If true, any move is allowed.
  - `color`: Optional[chess.Color] - Restrict movement to a specific color.
  - `dests`: dict - Mapping of squares to lists of valid destination squares (e.g., `{chess.E2: [chess.E3, chess.E4]}`).
- `animation`: dict - Configuration for animations:
  - `enabled`: bool.
  - `duration`: int (ms).

### Methods

#### `.setpiece_at(square, piece, color=None)` / `.set_piece_at(square, piece, color=None)`

Sets or clears a piece at a given square.

- `square`: `chess.Square` (0 to 63).
- `piece`: Can be a `chess.Piece` object, a string symbol (e.g. `'P'` for White Pawn, `'q'` for Black Queen), a `chess.PieceType` integer (e.g. `chess.PAWN`), or `None` to remove the piece.
- `color`: `chess.Color` (optional, defaults to `chess.WHITE` if `piece` is a `chess.PieceType` integer).

### Signals

- `moveMade(chess.Move)`: Emitted when a user completes a move (drag-and-drop or click-click) in standard mode.
- `pieceDropped(chess.Move)`: Emitted when a piece is dropped on the board, used predominantly in editable mode.
- `squareClicked(chess.Square)`: Emitted when any square is clicked.
- `fenChanged(str)`: Emitted when the FEN state changes.
- `selectionChanged(Optional[chess.Square])`: Emitted when the selected square changes.

## Example Usage

```python
from src.board import BoardView
import chess

# ... in your QMainWindow ...
self.board_view = BoardView()
self.board_view.moveMade.connect(self.handle_move)

# Configure the board
self.board_view.set(
    orientation=chess.WHITE,
    movable={
        'color': chess.WHITE,
        'dests': {chess.E2: [chess.E3, chess.E4]}
    }
)
```
