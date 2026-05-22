import chess
import chess.svg
from PyQt5.QtSvg import QSvgRenderer, QGraphicsSvgItem
from PyQt5.QtCore import QByteArray, Qt, QRectF
from PyQt5.QtGui import QPainter
from typing import Dict, Optional

class RendererCache:
    _renderers: Dict[str, QSvgRenderer] = {}

    @classmethod
    def get_renderer(cls, piece: chess.Piece) -> QSvgRenderer:
        key = f"{piece.symbol()}"
        if key not in cls._renderers:
            svg_data = chess.svg.piece(piece, size=45).encode("utf-8")
            renderer = QSvgRenderer(QByteArray(svg_data))
            cls._renderers[key] = renderer
        return cls._renderers[key]

class PieceItem(QGraphicsSvgItem):
    def __init__(self, piece: chess.Piece, square: chess.Square, square_size: float, parent=None):
        super().__init__(parent)
        self.piece = piece
        self.square = square
        self._square_size = square_size
        
        self.setSharedRenderer(RendererCache.get_renderer(piece))
        self._update_scale()

    def _update_scale(self):
        # SVG piece size is default 45 in chess.svg.piece
        # We want it to fit in square_size
        bound = self.renderer().viewBoxF()
        if not bound.isEmpty():
            scale = self._square_size / bound.width()
            self.setScale(scale)

    def set_square_size(self, size: float):
        if self._square_size != size:
            self._square_size = size
            self._update_scale()

    def set_square(self, square: chess.Square):
        self.square = square
