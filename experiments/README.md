# Experiments: Chessboard Implementations

This directory holds alternative implementations of the chessboard widget.

## 1. Merida Font + QPainter / QPainterPath Approach

Located in `experiments/painter_chessboard.py`.

### Key Technical Details:
- **Font-based Glyph Rendering**: Uses Merida TTF font (`MERIFONT.TTF`).
- **QPainterPath Conversion**: Converts font glyphs into `QPainterPath` vector outlines using `QPainterPath.addText()`.
- **Glyph Caching**: Caches path renderings into `QPixmap` instances per square size for fast drawing performance.
- **Pure QWidget / QPainter**: Built directly on `QWidget` using `paintEvent` without `QGraphicsView` overhead.

### How to Run:

```bash
python experiments/main.py
```
