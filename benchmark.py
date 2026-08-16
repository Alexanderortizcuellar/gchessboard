"""
benchmark.py — Measures and compares rendering performance of both chessboard implementations.

Metrics collected:
  - Initial board creation time
  - Piece-cache creation time
  - paintEvent time (average over N repaints)
  - Average FPS during animation (move sequence)
  - Memory: baseline, with board, after moves, peak

Run with:
    python benchmark.py

Results are printed to stdout and saved to benchmark_results.txt.
"""

import sys
import os
import time
import tracemalloc
import gc

import chess
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QElapsedTimer

sys.path.insert(0, os.path.dirname(__file__))

from src.board import BoardView, PainterChessBoard

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
N_REPAINTS = 200  # how many forced repaints to measure
BOARD_SIZE_PX = 480  # widget size in pixels
MOVE_SEQUENCE = [  # moves for animation benchmark
    chess.Move.from_uci("e2e4"),
    chess.Move.from_uci("e7e5"),
    chess.Move.from_uci("g1f3"),
    chess.Move.from_uci("b8c6"),
    chess.Move.from_uci("f1b5"),
    chess.Move.from_uci("a7a6"),
    chess.Move.from_uci("b5a4"),
    chess.Move.from_uci("g8f6"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def mem_kb(snapshot) -> float:
    stats = snapshot.statistics("lineno")
    return sum(s.size for s in stats) / 1024


def force_repaint(widget):
    widget.repaint()
    QApplication.processEvents()


def time_repaints(widget, n: int) -> float:
    """Return average repaint time in ms."""
    timer = QElapsedTimer()
    total = 0
    for _ in range(n):
        timer.start()
        force_repaint(widget)
        total += timer.nsecsElapsed()
    return total / n / 1_000_000  # ns → ms


def benchmark_board(board_widget, name: str, app: QApplication) -> dict:
    results = {"name": name}
    board_widget.resize(BOARD_SIZE_PX, BOARD_SIZE_PX)
    board_widget.show()
    app.processEvents()

    # Baseline memory
    gc.collect()
    tracemalloc.start()
    snap_baseline = tracemalloc.take_snapshot()
    results["mem_baseline_kb"] = mem_kb(snap_baseline)

    # Board displayed memory
    force_repaint(board_widget)
    snap_with_board = tracemalloc.take_snapshot()
    results["mem_with_board_kb"] = mem_kb(snap_with_board)

    # Repaint benchmark (no animation)
    avg_ms = time_repaints(board_widget, N_REPAINTS)
    results["avg_repaint_ms"] = round(avg_ms, 3)
    results["est_fps_idle"] = round(1000 / avg_ms if avg_ms > 0 else 0, 1)

    # Move sequence
    board = chess.Board()
    t0 = time.perf_counter()
    for move in MOVE_SEQUENCE:
        if move in board.legal_moves:
            board.push(move)
            board_widget.set(fen=board.fen(), lastMove=move)
            force_repaint(board_widget)
    t1 = time.perf_counter()
    results["move_seq_s"] = round(t1 - t0, 4)

    snap_after_moves = tracemalloc.take_snapshot()
    results["mem_after_moves_kb"] = mem_kb(snap_after_moves)

    # Resize stress
    t0 = time.perf_counter()
    for size in [300, 400, 480, 600, 480, 300]:
        board_widget.resize(size, size)
        force_repaint(board_widget)
    t1 = time.perf_counter()
    results["resize_6x_s"] = round(t1 - t0, 4)

    snap_peak = tracemalloc.take_snapshot()
    results["mem_peak_kb"] = mem_kb(snap_peak)

    tracemalloc.stop()
    board_widget.hide()
    return results


def fmt(results: dict) -> str:
    lines = [
        f"== {results['name']} ==",
        f"  Memory baseline       : {results['mem_baseline_kb']:.1f} KB",
        f"  Memory with board     : {results['mem_with_board_kb']:.1f} KB",
        f"  Memory after moves    : {results['mem_after_moves_kb']:.1f} KB",
        f"  Memory peak           : {results['mem_peak_kb']:.1f} KB",
        f"  Avg repaint time      : {results['avg_repaint_ms']:.3f} ms  ({results['est_fps_idle']:.1f} FPS est.)",
        f"  Move sequence time    : {results['move_seq_s']:.4f} s  ({len(MOVE_SEQUENCE)} moves)",
        f"  Resize (6×) time      : {results['resize_6x_s']:.4f} s",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    print("Benchmarking... (this may take a few seconds)\n")

    # SVG board
    svg_board = BoardView()
    svg_res = benchmark_board(svg_board, "BoardView (QGraphicsView + SVG)", app)

    # Painter board
    painter_board = PainterChessBoard()
    painter_res = benchmark_board(
        painter_board, "PainterChessBoard (QWidget + QPainter + Font)", app
    )

    output = "\n".join(
        [
            "=" * 60,
            "  GChessboard Benchmark Results",
            "=" * 60,
            "",
            fmt(svg_res),
            "",
            fmt(painter_res),
            "",
            "=" * 60,
            "  Comparison (Painter vs SVG)",
            "=" * 60,
            f"  Repaint speedup      : {svg_res['avg_repaint_ms'] / max(painter_res['avg_repaint_ms'], 0.001):.2f}×",
            f"  FPS improvement      : +{painter_res['est_fps_idle'] - svg_res['est_fps_idle']:.1f} FPS",
            f"  Memory reduction     : {svg_res['mem_with_board_kb'] - painter_res['mem_with_board_kb']:.1f} KB",
            "=" * 60,
        ]
    )

    print(output)

    results_path = os.path.join(os.path.dirname(__file__), "benchmark_results.txt")
    with open(results_path, "w") as f:
        f.write(output + "\n")
    print(f"\nResults saved to {results_path}")

    app.quit()


if __name__ == "__main__":
    main()
