"""Style registry. A style is `render(panel, ctx) -> PIL.Image` at 800x480 RGB;
the caller pushes the result through panel.export(). Add a module here and to
STYLES to make it available to render.py / rotate.py."""

from __future__ import annotations

from . import gallery, journal, mathart, nothing, poster

STYLES = {
    "nothing": nothing.render,   # Nothing UI tiles (info dashboard)
    "gallery": gallery.render,   # full-bleed photo + caption bar
    "poster": poster.render,     # photo + oversized date + AI one-liner
    "journal": journal.render,   # AI morning-paper front page
    "mathart": mathart.render,   # generated fractals / attractors / curves
}
