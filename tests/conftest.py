"""Point the pixel oracle at the bundled Poppins before it is imported."""

from __future__ import annotations

import os

from gilvy.theme import bundled_fonts

os.environ["GILVY_FONT_PREFIX"] = str(bundled_fonts()) + "/Poppins-"
os.environ.setdefault("GILVY_BUILD_DIR", "/tmp/gilvy-oracle-build")
