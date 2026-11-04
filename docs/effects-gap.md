# Effects gap, re-checked against main after the overlay and template passes

Inventory: the 2026-11-04 Farneback pass on ref1, ref2, and ref3 (source
608×1080). px are source pixels. “Ready” means the episode can author the
measured values and the renderer draws them. A detector exists where noted.
Items the inventory marked BELUM DICEK were not seen as motion in the three
films; the library may still draw them.

| Effect | ref1 | ref2 | ref3 | Status |
| --- | --- | --- | --- | --- |
| Hard cut | 25 | 14 | 8 | Ready |
| Pan x/y, named eases, multi-key | 9 | 21 | 15 | Ready. Tracks. Largest move is about 147 px (ref2). |
| Zoom in/out, expo and quad/cubic eases | 6 | 11 | 11 | Ready. Biggest single shot is 100%→140% (scale 1.40, ref2). `scale_max` allows 4. |
| Rotation, about −0.6° to 5.5° | 5 | 0 | 2 | Ready via a rotation track. |
| Shake ~5–12 Hz, 1.5–3.6 px std | 1 | 1 | 3 | Ready. Confidence in the inventory is low. |
| Whip pan, 42.6 px/frame | 1 | 0 | 0 | Ready. Blur is opt-in on the whip window. |
| Flash, luma jumps to ~130–235 | 5 | 1 | 0 | Ready. |
| Dissolve ≤2.5 s, eased | 4 | 5 | 14 | Ready. Length is the full overlap, tolerance ±0.15 s on the replica table. |
| Dissolve 3.71 s (ref1, low confidence, alpha stalls near 0.47) | 1 | 0 | 0 | Partial. An eased dissolve may now last 4 s, so it can be authored. The stall is not a single ease; it is one low-confidence window, not a second curve type. |
| Parallax, centre vs edge | 15 | 7 | 14 | Partial. Per-layer tracks can author it. The inventory’s split is a region proxy, and true depth segmentation of one plate is not measured. |
| Text pop / fade / slide / per-word | many | many | many | Ready. Pop `overshoot` sets the peak above 1. Typewriter is per word. Which blob is text vs a graphic was not classified per event. |
| Highlighter, circle, arrow, strike, mask | not classified | not classified | slow reveals | Ready. Sweeps take a named `ease`. Arrowhead and a freehand curve are not a separate tool. |
| Stamp | not classified | not classified | not classified | Ready. |
| SFX onsets | 34 | 28 | 28 | Partial. `overlays[].sfx` is mixed on cue. The inventory onsets are not all tied to a visual event. |
| Paper / sepia grade | measured | measured | measured | Ready as a per-shot grade. Colour animation is a separate track. |
| Vignette, flicker, light leak, dust, glitch, wipe | not measured | not measured | not measured | Ready in the library, absent from the inventory. |
| Match cut | — | — | — | Ready. `transition_out: match` with `match.tracks` of scale, x, y, rotation. The outgoing frame aligns, then the next shot cuts in with no blend. |
| Animated colour | not measured | not measured | not measured | Ready. `color.tracks` of hue, sat, and bright, with the same keyframe eases. The plate `grade` still runs first. |
| Grain calibrated to hf std | measured | measured | measured | Ready. `grain` is unchanged. `grain_std` is the high-frequency std after a 1.5px blur. |

Templates: `templates/vox.yaml` (ref1), `templates/articles.yaml` (ref2),
`templates/history.yaml` (ref3). Replica tables, all rows passing:
`tests/fixtures/vox_replica_table.json`, `ref2_replica_table.json`,
`ref3_replica_table.json`. Dissolves are ±0.15 s. Zoom refs on ref2 and ref3
are log rates of the authored endpoints.
