# Delivery profiles and safe zones

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the same YAML episode to more than one canvas, with the locked 9:16 drawing placed inside each platform safe zone, while the default 1080×1920 file stays byte-identical to today.

**Architecture:** Scene functions keep writing the proven 1080×1920 design coordinates (`cx=513`, focal y `780`, caption y `1290`). A `DeliveryProfile` describes the output canvas and a safe rectangle. `Ctx` maps every design point through one uniform scale and offset into that rectangle, and fills the rest of the canvas with the background. Default profile `vertical_9x16` uses scale 1 and offset 0, so golden frame tests do not move. Other profiles are a second render of the same scenes, not an ffmpeg crop of the master.

**Tech Stack:** Python 3.11+, Pillow, existing gilvy package (`src/gilvy`), pytest, ffmpeg QC.

## Global Constraints

- Default output stays 1080×1920, 60 fps, scale 2, Poppins, palette `(10,10,10)` / `(236,236,236)` / `(218,255,89)`.
- Do not change scene formulas in `scenes.py` to “fix” a profile. Mapping lives in `Ctx`.
- `vertical_9x16` insets are 0. Caption baseline stays y=1290 in design space. Do not silently lift it into a Meta safe zone.
- Circles stay circles: one uniform scale, never separate x/y scale.
- QC runs on each rendered file against that file’s width and height.
- No new dependencies.

## Decision this plan locks

Fitting the whole show into the safe rectangle keeps strokes, coins, and captions intact. A square or 16:9 file therefore shows the vertical composition centered in the safe area, with background around it. It does not reflow objects into a new landscape layout. A later plan can add reflow. This plan does not.

`vertical_9x16_safe` is a separate profile on the same 1080×1920 canvas. It shrinks the design into a safe rectangle so the caption clears typical Reels, TikTok, and Shorts chrome. It is opt-in. The default show look does not change.

Starting insets (output pixels, tune with a contact sheet, do not treat as a spec from the platforms):

| Profile | Canvas | Safe insets L,T,R,B |
|---|---|---|
| `vertical_9x16` | 1080×1920 | 0,0,0,0 |
| `vertical_9x16_safe` | 1080×1920 | 80, 160, 120, 420 |
| `portrait_4x5` | 1080×1350 | 60, 80, 60, 220 |
| `square_1x1` | 1080×1080 | 60, 80, 60, 160 |
| `landscape_16x9` | 1920×1080 | 80, 60, 80, 140 |

Fit math, design size `DW,DH = 1080,1920`, safe rect `(L, T, R, B)` on an output of `(OW, OH)`:

```text
safe_w = OW - L - R
safe_h = OH - T - B
scale = min(safe_w / DW, safe_h / DH)
ox = L + (safe_w - DW * scale) / 2
oy = T + (safe_h - DH * scale) / 2
output_x = ox + design_x * scale
output_y = oy + design_y * scale
```

For `vertical_9x16`, `scale=1`, `ox=0`, `oy=0`.

## File structure

- Create `src/gilvy/formats.py` — profile table, `Fit`, `DeliveryProfile`.
- Modify `src/gilvy/theme.py` — `Theme.profile` and design size constants.
- Modify `src/gilvy/draw.py` — `Ctx` maps design coordinates through `Fit`.
- Modify `src/gilvy/episode.py` — optional `format` field, default `vertical_9x16`.
- Modify `src/gilvy/render.py` — frame size and sidecar meta from the profile.
- Modify `src/gilvy/qc.py` — expect the profile size already stored in meta.
- Modify `src/gilvy/cli.py` — `--format` override.
- Test `tests/test_formats.py`.
- Modify `skills/gilvy/SKILL.md` and `AGENTS.md` after the command exists.

---

### Task 1: Profile table and fit math

**Files:**
- Create: `src/gilvy/formats.py`
- Test: `tests/test_formats.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `DESIGN_W, DESIGN_H = 1080, 1920`
  - `@dataclass(frozen=True) class Fit` with `scale: float`, `ox: float`, `oy: float`, and `map(self, x: float, y: float) -> tuple[float, float]`
  - `@dataclass(frozen=True) class DeliveryProfile` with `name: str`, `width: int`, `height: int`, `insets: tuple[int, int, int, int]`
  - `PROFILES: dict[str, DeliveryProfile]`
  - `def get_profile(name: str) -> DeliveryProfile` raises `KeyError` listing known names
  - `def fit_of(profile: DeliveryProfile) -> Fit`

- [ ] **Step 1: Write the failing test**

```python
from gilvy.formats import fit_of, get_profile

def test_default_profile_is_identity():
    fit = fit_of(get_profile("vertical_9x16"))
    assert fit.scale == 1
    assert fit.map(513, 780) == (513, 780)
    assert fit.map(0, 1290) == (0, 1290)

def test_square_fits_inside_safe_rect_uniformly():
    profile = get_profile("square_1x1")
    fit = fit_of(profile)
    assert fit.scale < 1
    x0, y0 = fit.map(0, 0)
    x1, y1 = fit.map(1080, 1920)
    left, top, right, bottom = profile.insets
    assert left - 0.01 <= x0 <= x1 <= profile.width - right + 0.01
    assert top - 0.01 <= y0 <= y1 <= profile.height - bottom + 0.01
    assert abs((x1 - x0) / (y1 - y0) - 1080 / 1920) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_formats.py -q`
Expected: FAIL, `gilvy.formats` missing.

- [ ] **Step 3: Write `formats.py` with the five profiles and the fit formula above**

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_formats.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/gilvy/formats.py tests/test_formats.py
git commit -m "Add delivery profiles and uniform safe-zone fit"
```

---

### Task 2: Map design coordinates inside Ctx

**Files:**
- Modify: `src/gilvy/theme.py`
- Modify: `src/gilvy/draw.py` (`Ctx.__init__`, every method that multiplies by `theme.scale`)
- Test: `tests/test_formats.py`

**Interfaces:**
- Consumes: `Fit`, `get_profile`, `fit_of`
- Produces: `Theme.fit: Fit`. Default `Theme()` uses `vertical_9x16`, so `fit.map` is identity. `Ctx` canvas is `theme.width * theme.scale` where width/height come from the profile. Design points pass through `fit.map` before the supersample multiply.

- [ ] **Step 1: Write the failing test**

```python
from gilvy.draw import Ctx
from gilvy.theme import Theme

def test_default_ctx_is_1080x1920():
    ctx = Ctx(Theme())
    assert ctx.im.size == (2160, 3840)  # 2x supersample

def test_square_point_lands_inside_safe_rect():
    theme = Theme.from_profile("square_1x1")
    ctx = Ctx(theme)
    assert ctx.im.size == (theme.width * 2, theme.height * 2)
    x, y = theme.fit.map(513, 1290)
    left, top, right, bottom = theme.profile.insets
    assert left <= x <= theme.width - right
    assert top <= y <= theme.height - bottom
```

Add `Theme.from_profile(name: str) -> Theme` that copies palette and timing from the defaults and sets `width`, `height`, `profile`, and `fit`.

- [ ] **Step 2: Run the new tests and confirm they fail**

- [ ] **Step 3: Implement the mapping in `Ctx`**

Every user-space point `(x, y)` becomes:

```python
x, y = self.theme.fit.map(x, y)
s = self.theme.scale
# then existing x * s, y * s
```

Stroke widths and font sizes multiply by `fit.scale` as well as `theme.scale`, so a fitted frame is the same drawing, smaller, not a full-size stroke on a shrunken shape. Glow buffer stays in output pixels (`width // 4`, `height // 4`).

- [ ] **Step 4: Run golden tests and the new tests**

Run: `pytest -q`
Expected: existing byte compares still pass, because the default fit is identity and stroke scale is 1.

- [ ] **Step 5: Commit**

```bash
git add src/gilvy/theme.py src/gilvy/draw.py tests/test_formats.py
git commit -m "Map design coordinates through the delivery fit in Ctx"
```

---

### Task 3: Episode field and CLI override

**Files:**
- Modify: `src/gilvy/episode.py` (`Episode` gains `format: str = "vertical_9x16"`)
- Modify: `src/gilvy/cli.py` (`render` and `preview` gain `--format`)
- Test: `tests/test_episode.py`

**Interfaces:**
- Consumes: `get_profile`
- Produces: `Episode.format: str`. Unknown names raise `EpisodeError` with the known list. CLI `--format` overrides the YAML field for that run only.

- [ ] **Step 1: Write the failing test**

```python
def test_format_defaults_to_vertical():
    episode = load_episode("examples/ep01-mie-ayam.yaml")
    assert episode.format == "vertical_9x16"

def test_unknown_format_is_rejected(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("name: bad\nlanguage: en-US\nformat: poster\nscenes: []\n")
    with pytest.raises(EpisodeError, match="format"):
        load_episode(path)
```

- [ ] **Step 2: Run it and confirm failure**

- [ ] **Step 3: Parse `format`, default it, and thread `--format` from argparse to the loader or a copy of the episode**

- [ ] **Step 4: `pytest tests/test_episode.py tests/test_cli.py -q` passes**

- [ ] **Step 5: Commit**

```bash
git add src/gilvy/episode.py src/gilvy/cli.py tests/test_episode.py
git commit -m "Select a delivery profile from YAML or --format"
```

---

### Task 4: Render and QC at the profile size

**Files:**
- Modify: `src/gilvy/render.py` (theme built with `Theme.from_profile(episode.format)`)
- Modify: `src/gilvy/qc.py` only if meta width/height are not already written by render
- Test: `tests/test_formats.py`

**Interfaces:**
- Consumes: `Theme.from_profile`, `Episode.format`
- Produces: mp4 dimensions equal to the profile. Sidecar meta `width` and `height` match. QC size check uses that meta.

- [ ] **Step 1: Write the failing test**

Render one scene with `--tts fixture` and `--format square_1x1` into `tmp_path`. Probe the file with ffmpeg and assert `1080x1080`. Assert `vertical_9x16` is `1080x1920`.

- [ ] **Step 2: Run it and confirm the square file is still 1080×1920**

- [ ] **Step 3: Build the theme from the profile in the render and preview paths. Write `width` and `height` into the QC meta that render already emits.**

- [ ] **Step 4: Run the test and `gilvy qc` on both files. Square QC must check 1080×1080, not 1080×1920.**

- [ ] **Step 5: Commit**

```bash
git add src/gilvy/render.py src/gilvy/qc.py tests/test_formats.py
git commit -m "Render and QC at the selected delivery size"
```

---

### Task 5: Several profiles from one episode

**Files:**
- Modify: `src/gilvy/cli.py`
- Modify: `src/gilvy/episode.py` if a `formats:` list is easier than repeated CLI flags

**Interfaces:**
- Consumes: `Episode.format`, `get_profile`
- Produces: `gilvy render ep.yaml --format vertical_9x16 --format square_1x1` writes `out/<name>-vertical_9x16.mp4` and `out/<name>-square_1x1.mp4`. One `--format` keeps today’s single path `out/<name>.mp4`.

- [ ] **Step 1: Test that two flags produce two files with the two sizes**

- [ ] **Step 2: Confirm only one file exists before the change**

- [ ] **Step 3: Loop render once per profile. Shared voice cache. Separate video encode.**

- [ ] **Step 4: Both files pass `gilvy qc`**

- [ ] **Step 5: Commit**

```bash
git add src/gilvy/cli.py tests/test_formats.py
git commit -m "Render one episode to several delivery profiles"
```

---

### Task 6: Document the intake

**Files:**
- Modify: `skills/gilvy/SKILL.md`
- Modify: `AGENTS.md`

Replace the “ffmpeg derivative” section with the profiles that actually render. Keep the intake checklist. State explicitly:

- Default `vertical_9x16` is the show, insets 0, caption at design y=1290.
- `vertical_9x16_safe`, `portrait_4x5`, `square_1x1`, and `landscape_16x9` redraw that same design into the safe rectangle.
- They do not invent a second composition. Landscape is the vertical show fitted inside the safe area.
- Agent asks which profiles to ship before writing YAML. Silence means `vertical_9x16` only.

- [ ] **Commit**

```bash
git add skills/gilvy/SKILL.md AGENTS.md
git commit -m "Document rendered delivery profiles and safe zones"
```

## Self-review

- Spec “gambar ulang per ukuran” is Task 2 and Task 4: `Ctx` redraws into the safe rect. It is not an ffmpeg crop.
- Spec “paham safe zone” is the inset table and `vertical_9x16_safe`. Default show look stays out of that opt-in on purpose.
- Golden bytes: Task 2 requires `pytest -q` on the identity fit before any other profile is trusted.
- Out of scope: per-aspect reflow, reading live platform UI specs, moving the default caption up.
