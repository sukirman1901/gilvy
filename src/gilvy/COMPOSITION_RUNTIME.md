# Composition runtime and native frame inspection

This change adopts architectural ideas studied in Remotion, independently
implemented for Gilvy's Python compositor. No Remotion code or dependencies
are included. It is a foundation release, not a browser renderer or a claim
that the engine can automatically reproduce a reference's visual design.

## Timing contract

`time_space` is optional on every product layer/group:

- `global` (default): start/end and keyframes retain their existing film-second
  interpretation, even inside a local group. Old films retain their timing.
- `local`: start/end are relative to the declared parent start (the film for
  root layers). Keyframes and particle poses are relative to the layer's own
  start. Omitted end means the parent's declared end, not start + parent length.

For example a local group starts at 3s; its local child starts at .2s; the
child's keyframe at .4s executes at film time 3.6s. Moving the group moves
the child unchanged. Parent visibility always clips its descendants. A global
child does not escape its parent's clipping. A persistent object belongs at
the root, with a global track spanning all scenes.

The compiler records declared and visible intervals, track origin, parent ID,
and integer frame coverage `[first_frame, end_frame)`. Times remain seconds
for authoring compatibility; native seek is `frame_at(index)` at index/fps.
Fractional temporal samples still use the same absolute film clock. Native
seek and export share `ProductFilm.frame`; preview is not a second animation.

```yaml
- id: scene
  type: group
  width: 600
  height: 300
  x: 640
  y: 360
  time_space: local
  start: 3
  end: 6
  children:
    - id: heading
      type: text
      width: 500
      height: 70
      x: 300
      y: 100
      time_space: local
      start: 0.2
      text: A measured next step
      size: 32
      overflow: error
      keyframes:
        opacity: [[0, 0], [0.4, 1, out_cubic]]
```

Reviewed measurement import still receives source/global seconds. It now
subtracts both the supplied source origin and the destination layer's local
origin. Provenance records `track_origin`; it never changes measured times
into a different clock silently.

## Persistent particles

`type: particles` draws equal-count indexed point sets. Required `points` is
1..2048 local `[x,y]` pairs. Optional `poses` is at most 64 entries of
`[time, points, optional_easing]`, with positive, increasing times in the
layer's track clock. Every pose must preserve the count. Point index is the
identity; no matching or randomization occurs while rendering. `dot_radius`
defaults to 2px; `color` defaults to white. Normal layer/group transforms,
opacity, masks and blur apply.

Initial points are at track time zero. Each destination pose controls the
incoming easing, exactly as numeric keyframes do. Seek is pure and holds
the last pose after its time. It does not simulate accumulated motion.

`gilvy.particles.resample_contour(points, count, closed=False)` samples one
polyline evenly by arc length. Sample separate contours independently; do
not join an arm contour to a head with an artificial line. For curves, flatten
with `product_primitives.path_points` and convert each contour to point lists.
`particle_positions(node, time, ease)` can also be used by a custom house
Python scene with its own drawing and easing. Particle correspondence is an
authored decision; equal density does not guarantee a good intermediate pose.

See `examples/technical/composition.yaml`: the same forty points change from
contour to grid to bars; labels have local clocks. This is a native compositor
diagnostic, not the Bojonegoro episode or an approved visual standard.

## Measured layout

Groups optionally accept `layout: {direction: row|column, padding: 12,
gap: 16, align: start|center|end, justify: start|center|end}`. Defaults are row,
zero padding/gap, center cross-axis alignment, start justification. Child
planes retain native dimensions. Overfull layouts fail before encode.

Flow owns direct children's x/y and pivot. Do not author those values/tracks
on a direct flow child: wrap moving content in an unpositioned group and
animate its nested child. Flow positions are computed separately from the
reusable spec, so importing tracks and serializing it does not bake positions.
This is fixed-size flow, not CSS flexbox, automatic responsive reflow, or a
guarantee that transformed children will remain inside their allocated cells.

Text/counter `overflow` also supports explicit `wrap` and `fit`:

- `clip`: legacy default; retain authored dimensions and clip.
- `error`: reject full content outside the padded plane.
- `wrap`: wrap at word boundaries, respect explicit newlines; an unbreakable
  word that cannot fit fails instead of clipping. Whitespace is normalized
  within wrapped paragraphs. `max_lines` defaults to 100 (range 1..100).
- `fit`: choose the largest integer font size <= size that fits the authored
  lines without wrapping, and >= `min_size` (default 1). Set a deliberate
  readable minimum; failure is an error. It never enlarges text.

All strict modes check the full text before reveal, using final font metrics,
tracking, advance width and glyph ink bounds. The inspector returns final
size, line baseline, width, and local ink bounds for metric-based text. Legacy
unconfigured text keeps its existing component rendering and is not reported
as if it used the measured layout. Static metric text and images are prepared
before encoding. A counter's future values still require checking its authored
range; it is measured at each rendered/inspected frame.

## CLI preview and MCP inspection

```bash
gilvy serve-product examples/technical/composition.yaml --port 8765
gilvy inspect-product examples/technical/composition.yaml --frame 90 --out out/frame-90.png
gilvy render-product examples/technical/composition.yaml --start 3 --duration 2 --out out/proof.mp4
```

`serve-product` blocks until Ctrl+C and binds only to 127.0.0.1. Open the printed
URL on that machine. It provides a silent slider, previous/next frame, selected
layer state/timing and parent-plane quadrilateral, a downscaled display and
native inspection. There is no real-time playback or audio synchronization.
Frame rendering happens at native resolution before optional display scaling;
large films can therefore be slow. This first viewer prioritizes exact seek.

The session caches up to 16MiB of encoded frame PNGs in memory. Refresh/source
requests invalidate caches when spec/assets/fonts change by content. Failed
reloads are errors, never stale previews. Font caches are cleared on reload.
Python source changes require restarting the process to load new code; this
is not a Python hot-reload system. Nothing is saved into the source directory.
The local HTTP surface serves only the viewer, metadata, frames and inspection,
not arbitrary filesystem paths. It is a local authoring tool, not public hosting.

MCP `inspect_product_frame(spec_path, frame, output)` returns one new native
PNG, the compiled timeline and evaluated layer properties. `frame` is a
zero-based integer. Output must be a new `.png` path. Bounds are explicitly
in the parent's plane, not projected world-space hit testing. Inspector data
does not establish artistic quality, reference fidelity, or absence of overlap.

## Observable product render jobs

MCP `start_product_render(spec_path, output, start=0, duration=None)` returns
a job ID immediately. Poll `product_render_status(job_id)`; cancel with
`cancel_product_render(job_id)`. Existing synchronous `render_product` works
unchanged. These tools use the same renderer and integrity checks.

Stages: queued → preparing → rendering → encoding → verifying → published →
completed; failed/cancelled are terminal alternatives. Progress reports
rendered/total frames and slowest render/write frame. It does not invent an
encoding percentage. Cancel checks between frames and while waiting for the
encoder. Verification can take until ffprobe returns (bounded at 120s); a
cancel request still prevents publication afterward. Publication and cancel
are serialized: once committed, cancel returns false and preserves the video.

Jobs are in-memory and belong to the current MCP process. One worker, up to
eight active jobs, at most 32 retained records. Restart loses status; this is
not a persistent distributed queue. Active jobs cannot share an output path.
Inputs are read when the worker starts, so do not edit queued inputs if their
exact version matters. Use a source snapshot for an immutable render request.

Product video publication is atomic after verification. Cancellation or a
pre-publication failure preserves an existing output and removes temporary
encoding files. A sidecar write failure after committing a valid video is a
`metadata_warning`, not a falsely reported failed/cancelled video render.

## Scope and next work

This PR does not change house render/QC, transition overlap policy, audio track
format, or add a React backend. Existing house scene-local timing remains.
The new generic particle geometry can be reused by house Python scenes without
changing its style. Unifying house publication, explicit overlap/overlay and
cut sampling, audio tracks, and a measured browser-backend experiment remain
separate work. They must not silently change existing dubbing or master files.

Behavioral acceptance tests cover nested and legacy clocks, persistent objects,
strict layout, indexed morphs, imported measurements, exact native seek,
source/asset invalidation, local HTTP endpoints and cancellation preserving an
existing output. These are technical guarantees, not an automated anti-slop score.
