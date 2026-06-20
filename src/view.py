import chess
from PyQt5.QtWidgets import QGraphicsView
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter
from typing import Optional

from .models import BoardState
from .scene import BoardScene, SquareItem
from .pieces import PieceItem


class BoardView(QGraphicsView):
    moveMade = pyqtSignal(chess.Move)
    squareClicked = pyqtSignal(chess.Square)
    pieceDropped = pyqtSignal(chess.Move)
    fenChanged = pyqtSignal(str)
    selectionChanged = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(BoardScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAcceptDrops(True)

        self._state = BoardState()
        self._square_size = 60

        # Interaction state
        self._drag_piece = None
        self._drag_start_square = None
        self._drag_start_pos = None
        self._click_origin = None  # For click-click strategy
        self._suppress_anim_square: Optional[chess.Square] = None

        self.update_board()

    def get_visual_board(self) -> chess.Board:
        """Returns the board state predicted by the current queue of premoves."""
        if self._state.editable:
            return chess.Board(self._state.fen)
        board = chess.Board(self._state.fen)
        color = self._state.movable.color
        
        if color is None:
            if self._state.last_sent_premove:
                if self._state.last_sent_premove in board.legal_moves:
                    board.push(self._state.last_sent_premove)
            for pm in self._state.premoves:
                if pm in board.legal_moves:
                    board.push(pm)
                else: break
            return board

        # Apply last sent premove if any
        if self._state.last_sent_premove:
            if self._state.last_sent_premove in board.legal_moves:
                board.push(self._state.last_sent_premove)

        # Apply premoves one by one, forcing turn to player color for each
        for pm in self._state.premoves:
            board.turn = color
            if pm in board.legal_moves:
                board.push(pm)
            else:
                break
        
        # Ensure the final visual board is on the player's turn for next move validation
        board.turn = color
        return board

    def _prune_premoves(self):
        """Validates and prunes the premove queue against the true board state."""
        if self._state.editable:
            return
        board = chess.Board(self._state.fen)
        color = self._state.movable.color
        if color is None: return

        # If we just sent a premove, apply it to the board before validating the rest
        if self._state.last_sent_premove:
            if self._state.last_sent_premove in board.legal_moves:
                board.push(self._state.last_sent_premove)

        valid_queue = []
        for pm in self._state.premoves:
            board.turn = color
            if pm in board.legal_moves:
                board.push(pm)
                valid_queue.append(pm)
            else:
                break
        self._state.premoves = valid_queue

    def update_board(self, instant_square: Optional[chess.Square] = None):
        sq = instant_square if instant_square is not None else self._suppress_anim_square
        self.scene().setup_board(self._square_size, self._state.orientation, self._state.theme)
        
        self._prune_premoves()
        visual_board = self.get_visual_board()
        
        anim_config = self._state.animation
        if self._state.editable:
            from .models import AnimationConfig
            anim_config = AnimationConfig(enabled=False)

        fen_changed = self.scene().set_fen(
            visual_board.fen(),
            self._square_size,
            self._state.orientation,
            anim_config,
            sq,
        )
        self.scene().update_highlights(
            self._state, visual_board, self._square_size, self._state.orientation
        )
        self.setSceneRect(0, 0, self._square_size * 8, self._square_size * 8)

        if fen_changed or instant_square is not None:
            self._suppress_anim_square = None

    # Public API
    def set(self, **kwargs):
        """Unified configuration method inspired by Chessground."""
        for key, value in kwargs.items():
            if key == "fen":
                old_fen = self._state.fen
                self._state.fen = value
                if old_fen != value:
                    self._handle_fen_change()
            elif key == "orientation":
                self._state.orientation = value
            elif key == "viewOnly":
                self._state.view_only = value
            elif key == "lastMove":
                self._state.last_move = value
            elif key == "selected":
                self._state.selected = value
            elif key == "editable":
                self._state.editable = value
            elif key == "theme" and isinstance(value, dict):
                new_theme = self._state.theme.copy()
                new_theme.update(value)
                self._state.theme = new_theme
            elif key == "movable" and isinstance(value, dict):
                for mkey, mvalue in value.items():
                    if hasattr(self._state.movable, mkey):
                        setattr(self._state.movable, mkey, mvalue)
            elif key == "premovable" and isinstance(value, dict):
                for pkey, pvalue in value.items():
                    if hasattr(self._state.premovable, pkey):
                        setattr(self._state.premovable, pkey, pvalue)
            elif key == "animation" and isinstance(value, dict):
                for akey, avalue in value.items():
                    if hasattr(self._state.animation, akey):
                        setattr(self._state.animation, akey, avalue)
            elif hasattr(self._state, key):
                setattr(self._state, key, value)

        self.update_board()

    def _handle_fen_change(self):
        if self._state.editable:
            self._state.last_sent_premove = None
            return
        board = chess.Board(self._state.fen)
        is_our_turn = self._state.movable.color is None or board.turn == self._state.movable.color
        
        if self._state.premoves and is_our_turn:
            premove = self._state.premoves.pop(0)
            if premove in board.legal_moves:
                self._state.last_sent_premove = premove
                QTimer.singleShot(0, lambda: self.moveMade.emit(premove))
            else:
                self._state.premoves.clear()
                self._state.last_sent_premove = None
                self.update_board()
        else:
            # FEN changed and it's either not our turn or no premoves left.
            # This usually means the last sent premove is now reflected in the FEN.
            self._state.last_sent_premove = None

    def set_fen(self, fen: str):
        self.set(fen=fen)
        self.fenChanged.emit(fen)

    def set_state(self, state: BoardState):
        self._state = state
        self.update_board()
        self.fenChanged.emit(self._state.fen)

    def move_piece(self, move: chess.Move):
        board = chess.Board(self._state.fen)
        if move in board.legal_moves:
            board.push(move)
            self._state.fen = board.fen()
            self._state.last_move = move
            self.update_board()
            self.moveMade.emit(move)

    def flip_orientation(self):
        self._state.orientation = (
            chess.BLACK if self._state.orientation == chess.WHITE else chess.WHITE
        )
        self.update_board()

    def set_view_only(self, enabled: bool):
        self._state.view_only = enabled

    def setpiece_at(self, square: chess.Square, piece: Optional[chess.Piece], color: Optional[chess.Color] = None):
        """Sets a piece at a given square. 
        Accepts:
            - square: a chess.Square (0 to 63)
            - piece: chess.Piece, string symbol (e.g. 'P', 'q'), chess.PieceType integer, or None to remove
            - color: chess.Color (optional, used if piece is a chess.PieceType integer)
        """
        if piece is None:
            p_obj = None
        elif isinstance(piece, chess.Piece):
            p_obj = piece
        elif isinstance(piece, str):
            p_obj = chess.Piece.from_symbol(piece)
        elif isinstance(piece, int):
            if color is None:
                color = chess.WHITE
            p_obj = chess.Piece(piece, color)
        else:
            p_obj = piece

        board = chess.Board(self._state.fen)
        board.set_piece_at(square, p_obj)
        self.set(fen=board.fen())

    def set_piece_at(self, square: chess.Square, piece: Optional[chess.Piece], color: Optional[chess.Color] = None):
        """Alias for setpiece_at."""
        self.setpiece_at(square, piece, color)

    def mousePressEvent(self, event):
        if self._state.view_only:
            super().mousePressEvent(event)
            return

        pos = event.pos()
        square = self.get_square_at(pos)

        if event.button() == Qt.RightButton:
            self._state.premoves.clear()
            self._state.selected = None
            self._click_origin = None
            self._suppress_anim_square = None
            self.update_board()
            return

        if event.button() == Qt.LeftButton and square is not None:
            self.squareClicked.emit(square)

            piece_item = self.scene().piece_items.get(square)
            
            if self._state.editable:
                if piece_item:
                    self._start_drag(square, piece_item)
            else:
                visual_board = self.get_visual_board()
                true_board = chess.Board(self._state.fen)
                is_our_turn = self._state.movable.color is None or true_board.turn == self._state.movable.color
                can_select = self._can_move_piece(square, visual_board)

                if self._click_origin is not None:
                    if square == self._click_origin:
                        if piece_item and can_select:
                            self._start_drag(square, piece_item)
                    else:
                        move = self._create_move(self._click_origin, square, visual_board)
                        if is_our_turn and not self._state.premoves:
                            if self._is_move_valid(move, visual_board):
                                self.moveMade.emit(move)
                                self._click_origin = None
                                self._state.selected = None
                            else:
                                if piece_item and can_select:
                                    self._click_origin = square
                                    self._state.selected = square
                                    self._start_drag(square, piece_item)
                                else:
                                    self._click_origin = None
                                    self._state.selected = None
                        else:
                            if self._state.premovable.enabled:
                                if move in visual_board.legal_moves:
                                    self._state.premoves.append(move)
                                    self._click_origin = None
                                    self._state.selected = None
                                else:
                                    if piece_item and can_select:
                                        self._click_origin = square
                                        self._state.selected = square
                                        self._start_drag(square, piece_item)
                                    else:
                                        self._click_origin = None
                                        self._state.selected = None
                            else:
                                self._click_origin = None
                                self._state.selected = None
                else:
                    if piece_item and can_select:
                        self._click_origin = square
                        self._state.selected = square
                        self._start_drag(square, piece_item)

            self.selectionChanged.emit(self._state.selected)
            self.update_board()

        super().mousePressEvent(event)

    def _start_drag(self, square: chess.Square, piece_item: PieceItem):
        self._suppress_anim_square = None
        self._drag_piece = piece_item
        self._drag_start_square = square
        self._drag_start_pos = piece_item.pos()
        self._drag_piece.setZValue(1000)
        self._state.dragging = True

    def mouseMoveEvent(self, event):
        if self._drag_piece:
            pos = self.mapToScene(event.pos())
            max_coord = self._square_size * 8
            x = max(
                0, min(pos.x() - self._square_size / 2, max_coord - self._square_size)
            )
            y = max(
                0, min(pos.y() - self._square_size / 2, max_coord - self._square_size)
            )
            self._drag_piece.setPos(x, y)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_piece:
            pos = event.pos()
            dest_square = self.get_square_at(pos)

            if self._state.editable:
                board = chess.Board(self._state.fen)
                piece = board.piece_at(self._drag_start_square)
                start_sq = self._drag_start_square
                if piece:
                    if dest_square is not None:
                        if dest_square != self._drag_start_square:
                            board.remove_piece_at(self._drag_start_square)
                            board.set_piece_at(dest_square, piece)
                            self._state.fen = board.fen()
                            self._suppress_anim_square = dest_square
                            
                            self._drag_piece.setZValue(0)
                            self._drag_piece = None
                            self._drag_start_square = None
                            self._state.dragging = False
                            
                            self.update_board(instant_square=dest_square)
                            
                            self.fenChanged.emit(self._state.fen)
                            self.pieceDropped.emit(chess.Move(start_sq, dest_square))
                            self._click_origin = None
                            self._state.selected = None
                        else:
                            self._drag_piece.setPos(self._drag_start_pos)
                            self._drag_piece.setZValue(0)
                            self._drag_piece = None
                            self._drag_start_square = None
                            self._state.dragging = False
                            self.update_board()
                    else:
                        # Dragged off the board - delete the piece
                        board.remove_piece_at(self._drag_start_square)
                        self._state.fen = board.fen()
                        
                        self._drag_piece.setZValue(0)
                        self._drag_piece = None
                        self._drag_start_square = None
                        self._state.dragging = False
                        
                        self.update_board()
                        
                        self.fenChanged.emit(self._state.fen)
                        self._click_origin = None
                        self._state.selected = None
            else:
                visual_board = self.get_visual_board()
                true_board = chess.Board(self._state.fen)
                is_our_turn = self._state.movable.color is None or true_board.turn == self._state.movable.color

                if dest_square is not None and dest_square != self._drag_start_square:
                    move = self._create_move(self._drag_start_square, dest_square, visual_board)
                    
                    if is_our_turn and not self._state.premoves:
                        if self._is_move_valid(move, visual_board):
                            self._suppress_anim_square = dest_square
                            self.moveMade.emit(move)
                            self.pieceDropped.emit(move)
                            self._click_origin = None
                            self._state.selected = None
                            self.update_board(instant_square=dest_square)
                        else:
                            self._drag_piece.setPos(self._drag_start_pos)
                    else:
                        if self._state.premovable.enabled:
                            if move in visual_board.legal_moves:
                                self._state.premoves.append(move)
                                self._click_origin = None
                                self._state.selected = None
                                target_pos = self.scene().get_square_pos(dest_square, self._square_size, self._state.orientation)
                                self._drag_piece.setPos(target_pos)
                            else:
                                self._drag_piece.setPos(self._drag_start_pos)
                        else:
                            self._drag_piece.setPos(self._drag_start_pos)
                else:
                    self._drag_piece.setPos(self._drag_start_pos)

                self._drag_piece.setZValue(0)
                self._drag_piece = None
                self._drag_start_square = None
                self._state.dragging = False
                self.update_board(instant_square=dest_square if dest_square else None)

        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if self._state.editable and event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._state.editable and event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if self._state.editable and event.mimeData().hasText():
            text = event.mimeData().text()
            pos = event.pos()
            square = self.get_square_at(pos)
            if square is not None:
                try:
                    piece = chess.Piece.from_symbol(text)
                    self.setpiece_at(square, piece)
                    event.acceptProposedAction()
                except ValueError:
                    super().dropEvent(event)
            else:
                super().dropEvent(event)
        else:
            super().dropEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        side = min(self.width(), self.height())
        self._square_size = side / 8
        self.update_board()
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def get_square_at(self, pos) -> Optional[chess.Square]:
        items = self.items(pos)
        for item in items:
            if isinstance(item, SquareItem):
                return item.square
        return None

    def _can_move_piece(self, square: chess.Square, board: chess.Board) -> bool:
        if self._state.movable.free:
            return True
        piece = board.piece_at(square)
        if piece:
            if (
                self._state.movable.color is None
                or piece.color == self._state.movable.color
            ):
                return True
        return False

    def _is_move_valid(self, move: chess.Move, board: chess.Board) -> bool:
        if self._state.movable.free:
            return True
        if self._state.movable.dests and not self._state.premoves:
            if move.from_square in self._state.movable.dests:
                return move.to_square in self._state.movable.dests[move.from_square]
        return move in board.legal_moves

    def _create_move(self, from_sq: chess.Square, to_sq: chess.Square, board: chess.Board) -> chess.Move:
        move = chess.Move(from_sq, to_sq)
        piece = board.piece_at(from_sq)
        if piece and piece.piece_type == chess.PAWN:
            if (chess.square_rank(to_sq) == 7 and piece.color == chess.WHITE) or (
                chess.square_rank(to_sq) == 0 and piece.color == chess.BLACK
            ):
                move.promotion = chess.QUEEN
        return move
