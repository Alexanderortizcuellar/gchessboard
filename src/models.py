import chess
from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class AnimationConfig:
    enabled: bool = True
    duration: int = 200


@dataclass
class MovableConfig:
    free: bool = False
    color: Optional[chess.Color] = None
    dests: Optional[Dict[chess.Square, list[chess.Square]]] = None


@dataclass
class PremoveConfig:
    enabled: bool = True
    showDests: bool = True
    castle: bool = True


@dataclass
class BoardState:
    fen: str = chess.STARTING_FEN
    orientation: chess.Color = chess.WHITE
    view_only: bool = False
    editable: bool = False
    last_move: Optional[chess.Move] = None
    selected: Optional[chess.Square] = None
    dragging: bool = False
    last_sent_premove: Optional[chess.Move] = None
    animation: AnimationConfig = field(default_factory=AnimationConfig)
    movable: MovableConfig = field(default_factory=MovableConfig)
    premoves: list[chess.Move] = field(default_factory=list)
    premovable: PremoveConfig = field(default_factory=PremoveConfig)
    theme: dict = field(
        default_factory=lambda: {
            "light": "#dee3e6",
            "dark": "#8ca2ad",
            "lastMove": "rgba(255, 255, 0, 0.5)",
            "selected": "rgba(0, 0, 255, 0.4)",
            "check": "rgba(255, 0, 0, 0.8)",
            "premove": "rgba(20, 100, 200, 0.5)",
        }
    )
