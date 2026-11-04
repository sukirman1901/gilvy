# Product primitives: engine proof and remaining gaps

The product compositor now exposes reusable typography, masks, counters,
M/L/Q/C/Z paths, ellipses, pivots, independent axis scale, cubic Bezier easing,
directional blur, per-layer temporal sampling and animated Gaussian light
fields. Preset inbox/menu/panel components remain optional. The explainer
renderer and its style constraints are not changed.

The AI authors the composition, functional narrative and object choreography.
The engine executes that authored specification; it does not automatically
infer good design from a video. `PRODUCT_MOTION.md` defines an evidence and
review contract for agents, and the skill routes explicit SaaS work before
the locked explainer instructions.

## Evidence limits

The former five-second Numtera study was a scoped reconstruction with manually
assigned object IDs, substituted fonts, estimated hidden geometry, approximate
blur, and no whole-film correspondence. Its unrelated metric-card composition
proved that operations could execute, not that the visual direction was good.
The builder and its measurements have been retired from creative examples.
Earlier rendered comparisons can be found in Git history; they are not a
current reproduction workflow or a visual master.

The old learning/inbox films and 95-second launch were also demonstrations,
not approved SaaS standards. Only the launch builder needed by existing
shot-boundary tests remains, under `tests/fixtures/product_launch/`.
See [the full audit](examples-audit.md). No technical pass makes those
fixtures suitable references for a new design.

## Technical validation

Behavioral tests check stable child geometry through a group mask, cached-plane
integrity, baseline/reveal alignment, missing font errors, explicit counter
formatting, independent numeric tracks, Bezier timing, pivots, animated lights,
directional spread without a black alpha halo, object-local shutter sampling,
path reveals and quality-gated imports through Python and MCP. Existing product
and explainer tests remain in the full suite.

## Open work

- Generic object tracking, OCR, occlusion handling and independent extraction
  quality estimation are not implemented. The importer consumes reviewed data.
- No automatic font/curve/shutter recovery, reference-to-scene synthesis,
  sound-effect identification or beat synchronization is claimed.
- Masks are rounded rectangles, not arbitrary animated vector mattes. Paths
  flatten curves; fills do not support holes, boolean operations or SVG import.
- Light position/radius/RGB animate; the base color and light alpha remain static.
- Directional blur is a spatial approximation; temporal sampling is CPU-bound
  and may mix states at a cut. Neither setting automatically chooses itself.
- More primitives do not guarantee design judgment. Inspect short proofs and
  revise before extending a film; an integrity pass is not creative approval.
