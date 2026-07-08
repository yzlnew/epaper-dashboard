"""Style registry. A style is `render(panel, ctx) -> PIL.Image` at 800x480 RGB;
the caller pushes the result through panel.export(). Add a module here and to
STYLES to make it available to render.py / rotate.py."""

from __future__ import annotations

from . import comic, gallery, journal, mathart, nothing, pokemon, poster

STYLES = {
    "nothing": nothing.render,   # Nothing UI tiles (info dashboard)
    "gallery": gallery.render,   # full-bleed photo + caption bar
    "poster": poster.render,     # photo + oversized date + AI one-liner
    "journal": journal.render,   # AI morning-paper front page
    "mathart": mathart.render,   # generated fractals / attractors / curves
    "comic": comic.render,       # American comic-book front page
    "pokemon": pokemon.render,   # daily Pokémon + time & weather
}
