import sys
import os
import time
import chess
import tracemalloc
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QImage, QPainter

# Add parent project root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import implementations
from src.board import BoardView
from painter_chessboard_backup import PainterChessboard as PainterBackup
from vector_chessboard import VectorChessboard


def benchmark_widget(widget_class, name: str, iterations: int = 1000):
    _ = QApplication.instance() or QApplication(sys.argv)

    # 1. Measure Memory Allocation during Initialization
    tracemalloc.start()
    widget = widget_class()
    widget.resize(600, 600)
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Sample game positions (FENs)
    fens = [
        chess.STARTING_FEN,
        "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 1 5",
        "rnbq1rk1/ppp1ppbp/5np1/3p4/2PP4/5NP1/PP2PPBP/RNBQ1RK1 b - - 1 6",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    ]

    image = QImage(600, 600, QImage.Format_ARGB32)

    # 2. Measure Render Time (paintEvent / scene rendering)
    start_time = time.perf_counter_ns()
    for i in range(iterations):
        fen = fens[i % len(fens)]
        if hasattr(widget, "set_fen"):
            try:
                widget.set_fen(fen, animate=False)
            except TypeError:
                widget.set_fen(fen)
        else:
            widget.set(fen=fen)

        # Force a full paint render into an offscreen image buffer
        image.fill(0)
        p = QPainter(image)
        widget.render(p)
        p.end()

    end_time = time.perf_counter_ns()

    total_time_ms = (end_time - start_time) / 1e6
    avg_render_us = ((end_time - start_time) / 1e3) / iterations
    fps = (iterations * 1e9) / (end_time - start_time)

    print("==================================================")
    print(f" Benchmark Results: {name}")
    print("--------------------------------------------------")
    print(f" Total Time ({iterations} renders) : {total_time_ms:.2f} ms")
    print(
        f" Avg Render Time per Frame   : {avg_render_us:.2f} µs ({avg_render_us / 1000:.3f} ms)"
    )
    print(f" Max Theoretical Throughput  : {fps:.1f} FPS")
    print(f" Init Peak Memory Allocated  : {peak_mem / 1024:.2f} KB")
    print("==================================================\n")

    return {
        "name": name,
        "avg_render_us": avg_render_us,
        "fps": fps,
        "peak_mem_kb": peak_mem / 1024,
    }


def main():
    print("\nRunning Chessboard Performance Benchmark...\n")
    res1 = benchmark_widget(BoardView, "gchessboard (QGraphicsView)", iterations=500)
    _ = benchmark_widget(
        PainterBackup, "PainterBackup (Single-Glyph Merida)", iterations=500
    )
    res3 = benchmark_widget(
        VectorChessboard, "VectorChessboard (Approach D Vector Cache)", iterations=500
    )

    speedup = res1["avg_render_us"] / res3["avg_render_us"]
    print("Summary:")
    print(
        f"-> 'VectorChessboard (Approach D)' is {speedup:.2f}x faster per frame than 'gchessboard'."
    )


if __name__ == "__main__":
    main()
