# Visual vocabulary and motion reference

Use this after naming object, verb, carry, meaning, and consequence. An element
supplies a shape and a local performance. The scene supplies the relationship.
More available shapes does not mean more simultaneous subjects.

## Choose an element

| Element | Useful performance | Direction still needed |
|---|---|---|
| `person` | Stand, walk with opposite limbs | Route, goal, obstacle, destination |
| `people` | Five faceless people, staggered gait | Whether the group is illustrative or counted |
| `flame` | Draw a flame, let its tip sway | Ignition, source, containment, consequence |
| `smoke` | Draw and drift three wisps | Verified context; no automatic pollution claim |
| `drop` | Form a droplet | Move it along a meaningful path; label oil/water |
| `tree` | Draw trunk, canopy, branches; sway | What grows, shades, or is lost |
| `sprout` | Grow a stem before leaves | What enabled or prevented growth |
| `house` | Build roof, walls, doorway | Arrival, access, shelter |
| `building` | Draw outline before windows | Identify the institution through context |
| `pipe` | Connect rails through an elbow | Supply, destination, direction |
| `flow` | Move four beads on one curved path | Illustrative transfer; no implied exchange rate |
| `sun` | Draw disk then rays, small local radiance | Temperature requires actual measurements |
| `book` | Open outline, turn a leaf at the spine | Education/access rather than a decorative icon |
| `road` | Draw fixed edges, move lane markings | Journey or connection, not a chart axis |

List the same registry with `gilvy elements` or MCP `list_visual_elements`.
These names are **not YAML scene types**. Use them inside a `python` scene.
They compose the unchanged Ctx primitives, palette, stroke language, and fit.
No photos, detailed faces, random particles, bounce, or camera motion.

## API

```python
from gilvy.elements import draw_element
from gilvy.easing import R, eo, eio, lerp

def draw(ctx, u, duration, params):
    appear = eo(R(u, 0, .6))
    travel = eio(R(u, .4, duration * .65))
    position = lerp((360, 780), (620, 780), travel)
    draw_element(ctx, "person", center=position, size=110,
                 progress=appear, phase=u, activity=1-travel)
```

- `center` and `size`: design pixels; fit to the chosen output profile happens
  through Ctx. Size is a nominal square; pipe collars extend to 0.55×size.
- `progress`: draw-on fraction [0,1]. At 0 nothing is drawn. At 1 the shape is
  complete. Pass Gilvy's eased ramp, not a second easing system.
- `phase`: absolute seconds. Pass `u + offset` across scene cuts for the same
  continuing object. The renderer can request frames out of order in workers.
  Helpers have no mutable animation state, random seed, or wall-clock dependence.
- `activity`: local motion amount [0,1], default 0 (still). It animates applicable
  limbs, flame tips, wisps, foliage, rays, pages, flow beads, and road dashes.
  `drop`, `house`, `building`, and `pipe` use draw-on only. Direct travel outside
  the helper; never make every object idle merely because it can.
- `alpha`: [0,1]. `col`: RGB triple; default theme white. Explicit green is for
  the single counted quantity, never to make fire orange or trees green.
- Helpers do not add captions, labels, audio, shadows, or background grids.

Preview `examples/elements.yaml` for all 14 shapes. Its four specimen grids are
an inventory comparison, **not a narrative layout template**. A story keeps one
hero, its supporting action, and sufficient whitespace.

## Approved study: Bojonegoro, 41 seconds

The creator approved the 8-second worker proof and praised the finished piece
for smoothness, precision, and visual quality. Its limitation was a narrow
vocabulary of dots, lines, and circles. Preserve that craft while extending the
range of objects. Approval is for this piece; it does not certify new elements.

Reproduce the sources with `examples/bojonegoro/episode.yaml`. It is a historical
2025 data story, not a current-data template. Read its `SOURCES.md` before reuse.
The original worker drawing is preserved in `pekerja.py`; the continuation is
in `cerita.py`. No rendered MP4 or private workspace path is required.

| Time | Object → action | What the motion contributes |
|---|---|---|
| 0–4.5s | Reservoir stroke → rising droplet | Establishes the resource beneath the place |
| 4.5–7.5s | One origin → 100 equal dots | Introduces the denominator before the share |
| 7.5–12.5s | Same dots → 45 highlighted, two groups | Counts and classifies without inventing people |
| 12.5–17s | Workers settle below; public-funds ring draws above | Distinguishes jobs from government receipts |
| 17–23s | Separate rupiah amount → measuring rail | Counts money in its own unit, not per-worker income |
| 23–29s | Region node → service branches → citizens | Illustrates channels of benefit, not allocations |
| 29–35s | Two zero-based poverty bars → modest decline | Shows progress at its actual visual scale |
| 35–41s | Region outline → citizens inside | Returns the question to lived conditions |

## Transfer these motion patterns

1. **Establish the denominator before highlighting.** Map each unit by stable
   index. Build target positions with the same identities. Interpolate source
   and target coordinates with `eio`. Stagger nearby units slightly; do not
   respawn them as a new chart. Decide what one unit represents before drawing.
2. **Use color for the count.** In the worker example only agricultural dots
   turn green. Other dots become dimmer white but remain visible. Counters and
   labels stay legible and never become a second green idea.
3. **Keep quantity and label synchronized.** One eased variable drives both the
   selected count and the visual. The final 45 is a rounded representation of
   44.63%, explicitly noted. Do not claim these are 45 surveyed individuals.
4. **Separate incompatible units spatially.** Workers remain below while a
   money ring forms above. No worker transforms into a rupiah. A symbolic link
   between budgets and services is not a measured allocation or causal result.
5. **Change the relationship before adding effects.** Gathering, separating,
   connecting, and enclosing do the storytelling. Glow, motion intensity,
   opacity change, and a new icon cannot rescue a weak relationship.
6. **Keep the action alive until its resolution.** Introduce the hero, run the
   verb through roughly the first two thirds, then leave time to read. Small
   label/stroke delays support the hero. Keep the camera fixed and the easing
   family unchanged; no bounce, overshoot, or long diagonal entrance.
7. **Preserve approved sources and clocks.** Keep source, authored duration,
   captions, and keys. Align comparisons if the segment moved. A standalone
   outro may disappear in a full cut; codec differences are expected. Six raw
   sampled frames matched in this continuation; this is not an all-frame proof.
8. **Respect graph scales and attribution.** Poverty bars share a zero baseline
   and a 0–15% range. A 0.20 percentage-point decline stays small. Do not
   exaggerate it, mix employment and population denominators, or imply DBH
   caused the observed decline. Date sources on screen.

For a new subject, transfer the sequencing, identity, clock, and unit discipline.
Do not transfer Bojonegoro's numbers or make every story a dot-and-ring story.
Use a walking person only when travel, effort, or access matters; use a flame
only when burning, energy, or containment matters. Each new element must change
what the viewer understands, rather than decorate the caption.

## Review

Render a short playable proof. Inspect the entrance, mid-action, resolution,
and the scene boundary. Check shape recognition, uncluttered silhouettes,
phone-size text, and the relationship with captions hidden. Inspect the actual
encoded output, not only source stills. Technical QC is separate from creative
judgment. Do not call new work user-approved until the user approves it.
