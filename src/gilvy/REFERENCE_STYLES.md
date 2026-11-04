# Reference style presets

Opt-in episode styles for two kinds of 9:16 short. They do not change a house
episode. A house episode has no `style` (or `style: house`), a still camera,
and drawn scenes. Set `style: vox-explainer` or `style: history-story` only
when the picture is an image plate.

For editorial cutouts, paper/photo fragments and object-led handoffs, read
[the collage contract](COLLAGE.md) / MCP `collage_notes` first. Opt into
`composition: collage` for explicit fragment placement, per-object transforms,
episode clocks, attached text/annotations and deliberate reading holds.

Workflow for an agent:

1. `download-reference` when the source is a link, then `analyze-reference` on the local file.
2. Watch every motion clip. Read `soft_transitions` as dissolve **candidates**, not as scene cuts.
3. Pick one preset. Do not mix their grades in one episode.
4. `gilvy assets episode.yaml --reference video.mp4` and generate every missing PNG outside the repo. Do not commit the style frames.
5. `preview`, a short `preview-motion`, then `render` and `qc`.

`type: image` is valid only under these two styles. Render fails with the missing path if a plate is absent.

Tags used below:

- **measured** — from `measurements.json` (histogram cuts, whole-frame scale search, phase-correlation pan, k-means color) or from a frame read in this study.
- **observed** — seen on extracted frames or stated by the shot study and not contradicted by those frames.
- **inferred** — a reading of the measurements, not a recovered keyframe.
- **uncertain** — the sources disagree or the frame was not isolated.

The reference files were `ref1` (Vox parallax, 608×1080, 23.976 fps, 37.38 s), `ref2` (Vox articles, 608×1080, 23.976 fps, 28.91 s), and `ref3` (history story, same edit as the 1080×1920 attachment, 25 fps, 31.82 s). No caption VTT was in the upload, so keyword sync was not re-timed against speech.

## What both presets share

Image plates are authored in the 1080×1920 design space and fitted like the house show. The camera is a `from`/`to` scale and pan on the plate. Parallax is separate layers: depth 0 moves at 25% of the camera, depth 1 moves at 100% (**inferred** gain curve; the references were not delivered as layer files).

| Move | How to write it |
|---|---|
| Push / pull | `camera.from.scale` and `camera.to.scale`, both at least 1 |
| Pan | `x` / `y` in design pixels. Positive `x` moves the picture to the right |
| Hard cut | `transition_out: cut` |
| Cross-dissolve | `transition_out: dissolve` and `transition: 0.4` |
| Punch / zoom-through | `transition_out: zoom` and `transition: 0.3` |

A dissolve eases in linear alpha across the overlap. A zoom-through scales the outgoing plate up by about 28% while the incoming plate settles from 1.22. Those two curves are **inferred** from the short spikes below, not copied from an After Effects project.

House crossfades (0.45 s, ease-in-out) stay on house episodes only.

Overlays, in design pixels:

- `text` — `fade`, `pop`, or `slide`. `at` is seconds from the scene start. `keyword` places the word by its index in `vo` (no forced alignment).
- `highlighter` — a bar that grows left to right.
- `circle` — a stroke that draws itself from the top.
- `arrow` — a polyline that draws itself.

`sfx` on an overlay is a cue name for the agent (`pop`, `whoosh`, `paper`, `marker`, `scribble`, `swell`). The renderer does not synthesize it. **Gap.**

Green stays one quantity. These plates default to `green: none`. Do not paint a lime focus on a photo.

## vox-explainer

Use this for a Vox-style explainer: split-photo parallax, or an article page that never sits still, with a paper grade and a yellow marker. Hard cuts are the default. One punch zoom is a transition, not the plate speed.

### Shot length

**Measured** (`measurements.json`):

| Film | Shots the hard detector kept | Average | Median | Body of the list |
|---|---|---|---|---|
| ref1 | 26 in 37.38 s | 1.44 s | 1.21 s | Most plates are 0.71–2.08 s. One opener is 6.17 s. Three flashes are 0.17–0.25 s |
| ref2 | 15 in 28.91 s | 1.93 s | 2.17 s | Content plates are about 2.1–4.3 s. A montage from 18.4–21.6 s is 0.17–0.38 s flashes |

**Conformance band: 0.70–5.00 s.** The 6.17 s opener and the sub-0.4 s flashes are measured exceptions, not the plate to author. QC fails outside the band.

### Camera

**Measured**, whole frame, so layered parallax often reads as still:

- ref2 shots 1, 4, and 6 hold a steady push of **+1.0, +1.4, and +1.0 %/s**. The samples stay flat across each shot, which is why the plate ease is **linear** (**inferred** from that flatness, not from a curve fit).
- ref2 shot 5 is **measured static** (−0.1 %/s) for 4.17 s. Treat that as a held graphic, not as permission to freeze an image plate. Authored plates in this preset must move.
- ref2 shots 3 and 14 spike above **+40 %/s** and hit the search limit. Those numbers are **unreliable**. They are punch transitions. Put them on `transition_out: zoom` (~0.30 s, **inferred**), and keep the plate inside the band.
- ref1 shot 25 pans about **−73 px/s** on the 608-wide frame with a **+2.1 %/s** push (**measured**). At 1080 that pan is about −130 px/s. Many other ref1 shots measure near 0 %/s because one scale for the whole frame cannot see layers moving apart (**measured limitation**, called out in the measurement notes).

**Conformance:** push or pull **0.80–3.50 %/s**, or a pan of at least **8 px/s** in design pixels when the zoom is under 0.4 %/s. A faster punch belongs on the transition.

**Parallax (observed, ref1).** The picture is one photo cut into foreground, mid, and background, holes filled, then moved at different rates. Author that as `layers` with `depth` from 0 to 1 and a real alpha cutout. Gilvy does not split a photo or fill holes.

**ref3-style parallax is not part of this preset** and was **not verified** on ref3.

### Grade, texture, type

- Article plates: `grade: paper`. The map aims at the **measured** ref2 poles `#131313` and `#dadada`. It is not a recovered LUT.
- `paper: 0.12–0.20` is a fiber overlay. **Observed** on ref2. The amount is a preset choice, **not measured**.
- `grain: 0.04–0.08`. Light. **Inferred**. ref2 is not the heavy grain of ref3.
- Highlighter `#b9a80a` (**measured** k-means yellow on ref2), swept in about **0.40 s** (**inferred**; the sweep duration was not timed frame by frame). Marker SFX is **observed** and not generated.
- Type is mixed (**observed** in the shot study): a sans label in a colored box, serif for a numbered point. This preset defaults overlay text to **Poppins Medium** (`font: sans`). Serif is available (`font: serif`, Liberation Serif) when the word is a title, not the default.
- Entrance is `pop` or `slide`, finishing in about **0.16–0.28 s** (**inferred** from “pop-in with overshoot or decelerating slide”). The overshoot peaks near 1.08 and settles. House episodes still have no overshoot.
- `keyword` places text **0.10 s before** that word’s share of `vo` (**observed** in the shot study as “~0.1 s before or at the spoken keyword”; **uncertain** because no VTT was attached and this was not re-aligned). `at` overrides it.
- Hold until the cut on the reference (**observed**). Default `hold` is 1.6 s if you omit it; set `hold` to the plate length when the word should stay up.

### Sound

**Measured:** ref1 −19.7 LUFS integrated, loudness range 4.6, speech-band ratio 0.34. ref2 −16.7 LUFS, range 2.3, speech-band 0.44. No silence gap at or above 0.25 s / −40 dB. Voice sits on a music bed. Gilvy already ducks the bed under `voiceover`. SFX cues from the shot study: pop, whoosh, paper, marker. **Observed. Not synthesized.**

## history-story

Use this for a painterly sepia story: one still per beat, slow push or pull, heavy grain, red centered emphasis, and a dissolve between beats. The sample is not the Victor Lustig film and must not reuse its frames.

### Shot length

**Measured** hard cuts on ref3: 3.68, 5.68, 23.80, 27.68, 28.80, then end flashes at 31.36 / 31.52 / 31.68. That detector reports 9 shots, average 3.54 s, median 2.52 s, but the 5.68–23.80 span is **one 18.12 s bin that hides several pictures**.

**Observed** on frames extracted every 0.2 s, and **measured** again with the blend test:

| Study time | What the frames show | Detector (`soft_transitions`, hard cuts excluded) |
|---|---|---|
| ~5.7 s | Portrait cuts to the seated man on **one frame** near 5.64–5.68 s. Scene score **0.313** (**measured**). No frame in that window is a balanced mix of the two pictures | Left as a **hard cut**. The shot study called it a 0.3–0.5 s dissolve. **Uncertain** as a dissolve; the pixels support a cut |
| ~8.5 s | Seated man gives way to the cork board across roughly **8.6–9.4 s** (**observed**) | **9.00–9.80 s** (score 0.68, endpoint delta 39) |
| ~14.3 s | Board gives way to the table across roughly **14.6–15.0 s** (**observed**). A red circle is still drawing on the board through ~14.4 s | **14.16–14.88 s** (score 0.62, endpoint delta 48) |
| ~18.0 s | The table is already dark (~42 gray). The bright window picture arrives about **18.8–19.2 s** (**measured** mean luminance). Not a fade to black | Not confirmed as a cross-dissolve. A later candidate at **19.72–20.08 s** is a different hit. **Uncertain** |

**Conformance band: 1.10–7.00 s.** A 31.9 s voice recreation needed the 1.12 s measured fragment inside the band. The 0.12–0.16 s end flashes stay outside it.

The detector also returns other candidates (about 15.0, 19.7, 20.4, 23.2, 29.9, 31.3 s on this file). Some are end-card flashes or motion inside a shot. **Watch the clip** before promoting one to `--boundaries`. A synthetic 0.4 s crossfade is detected. A one-frame cut and a slow zoom are not.

Author dissolves at **0.40 s** (**observed** order of magnitude 0.3–0.5 s; the detector’s windows on this file run about 0.36–0.80 s). Ease is linear alpha (**inferred**). A consistency test locks a detected 0.40 s crossfade to **±0.10 s**.

### Camera

**Measured** on the bins the hard detector trusted, ignoring samples pinned at the search limit (±30 to ±44 %/s), which are unreliable:

- Steady pushes sit around **+1 to +5 %/s** inside the long bin’s quieter samples.
- One pull reads about **−13 %/s** (shot 6, 2.56 s).
- Pans on those bins are a few pixels per second (**measured** “essentially none”).
- Spikes of **+22 to +32 %/s** near 10–14 s are the zoom-throughs, same caveat as vox: do not author them as the plate. Use `transition_out: zoom` when a beat actually punches.

The shot study calls the push **slow and linear**. Combined with the flat stretches in the zoom samples, plate ease defaults to **linear** (**inferred**). It is not proven for every beat.

**Conformance:** push or pull **0.80–26 %/s**. A shot of **1.5 s or less** may punch up to **40 %/s**. Scale may reach **2.4**. Ease defaults to **exponential** so a measured constant %/s matches the authored rate; `ease: linear` is the old scale lerp, which reads about 0.7–0.85× that rate in the middle of a push. A pan of at least 8 px/s can carry a plate whose zoom is under 0.4 %/s. Zoom does not grow to make room for that pan: the window shifts, and a plate that runs out of pixels repeats its edge. QC fails a static plate. There is no intro fade from black. A dissolve may last up to **2.0 s**. The alpha is linear across that whole overlap. A 10%–90% measurement is 80% of the authored seconds, so 1.4 s reads as 1.12 s. That is the clock, not an ease and not a shortened blend. The dissolve detector used to keep the tightest-fitting span, which landed on that same 1.1 s core; it now keeps the longest span that is still a linear blend. House crossfades still use ease-in-out.

### Grade, grain, type, circle

- `grade: sepia` remaps luminance from shadow **#1a1411** to highlight **#ead0b3** (darker and warmer than the first `#261c15` / `#d3c0aa` pair). QC skips the green-tint check on this style.
- `grain: 0.16–0.24`. Heavy grain and a canvas weave are **observed** on the stills. The 0–1 amount is **not** a measured noise sigma.
- Emphasis text is centered, one short phrase, red. A frame at 5.0 s (“Victor Lustig”) is **serif** (**observed**). Pixels that passed a red threshold there have median about **(178, 74, 66)** (**measured**, antialiasing included). That is the default overlay color. Whether “DISAPPEARED” is serif or sans was **not** isolated. **Uncertain.** Default remains serif; set `font: sans` if the phrase is the blunt one.
- Default size is **216** design pixels. Several words stack one per line (`IN` / `1925`, `DEAL` / `WAS` / `REAL`) and the block shrinks until it fits the frame.
- Entrance fade is **`text_fade_s: 0.15`** (scene or overlay). The old 0.45 s fade reached full opacity about **0.32 s late**. A consistency test locks full opacity to **±0.20 s** of `at + text_fade_s`. `keyword` still starts **0.15 s after** that word’s share of `vo` (**observed** lag; the 0.15 s offset is a preset choice, **uncertain**).
- The red circle on the documents draws itself from about **13.2 s to 14.4 s** (**observed** on the 0.2 s strip), so about **1.2 s**, with a scribble cue (**observed**, not synthesized). Author `kind: circle` with `duration` near 0.8–1.2 s. The shot study’s “~13 s” matches the start, not a 0.3 s flick.
- A brown card with white sans (“And the strangest part?”) is **observed** in the shot study and was not re-cropped here. Use `font: sans` and a paper-colored plate if you cut that beat. **Uncertain** on the exact wording’s timing.
- The film ends by fading out. House outros already fade. The music swell is **observed** and not generated.

### Sound

**Measured:** −21.0 LUFS integrated, loudness range 2.1, speech-band ratio 0.26, no silence gap at the measurement’s threshold. No VTT. Speech-vs-music was **not** re-checked by ear in this pass. **Uncertain** how dry the voice is. Use `voiceover` plus the existing ducking when there is narration; `silent` is only for a layout proof.

Voice length: the house show adds `pad` 0.4 s and `lead` 0.2 s after every spoken line. On a pure voice recreation that extra 0.6 s per scene, plus edge-tts leading and trailing silence, made **35.6 s** out of the **31.9 s** reference. `history-story` sets both to **0**. edge-tts clips are trimmed at both ends before the duration is measured. Vox keeps the house 0.4 / 0.2 until it has its own timing pass. A consistency test locks an authored zoom rate to **±20%** of the rate the camera math reports.

## QC

For these two styles, technical QC adds three checks on each `type: image` scene, read from the timeline the renderer writes:

- duration inside the shot band above
- the plate is not static
- zoom, when it is the move, stays inside the plate band (a punch stays on `transition_out`)

`history-story` does not run the green-tint check. House QC is otherwise unchanged. Passing QC is still not a creative verdict. Compare a proof against the reference with `gilvy compare` when you are matching a beat. Equality of pixels is not the goal: the references are not the asset library.

## Assets

`gilvy assets episode.yaml --reference video.mp4` writes four interior frames (style refs, not committed plates) and prints one fixed prompt template per style. `--frames N` samples that many (1–32). `--per-shot` takes the midpoint of each image scene and compares that plate to its own frame. history-story’s template is **archival photo, sepia, grain, vignette, framing**. Each plate’s pixel size is the 1080×1920 frame plus the camera’s pan, multiplied by the tightest zoom, so the move does not run out of picture. When the PNG already exists, the manifest compares its brightness, contrast, and colour to the reference frame in the nearest brightness bucket (not one average of every shot) and, on a miss, sets `image_qc.regen`.

Render writes `<video>.camera.json` beside the mp4: authored scale, zoom %/s, and pan next to the scale and pan the camera math actually applies. `vo_overrun` that runs a line into the next spoken line is a QC warning, not a failure.

`gilvy.measure.motion` reads that same log zoom and the pan in source pixels per second (+x right, +y down). Scale is the factor that lines the earlier frame up with the later one, chosen by pixel error after the shift is taken out. Scoring the scale by a phase-correlation peak locks onto grain and compression at scale 1, so a real plate comes back near 0%/s with a pan of a hundred pixels per second. A plate bigger than 1080×1920 is not shrunk to a cover fit; the extra pixels are the pan and zoom margin the manifest asks for.

## Gaps

- No automatic layer split, hole fill, or face track.
- No film LUT, no measured grain sigma, no synthesized SFX.
- Keyword timing is a share of the line, not phoneme alignment.
- Emphasis at 216 px is 3× the old default and still short of the reference titles, which read about 9× the old 72 px.
- Dissolve detection misses a one-frame join (ref3 at 5.68 s) and can add extra candidates inside a moving shot. Confirm on the clips.
- Image plates are drawn at delivery resolution. House scenes stay 2× supersampled. That difference is visible on type edges if you mix a house scene into a photo episode; keep a photo episode on `type: image`.
- ref3 parallax was not shown to be more than the push.
