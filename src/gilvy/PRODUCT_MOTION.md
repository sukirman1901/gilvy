# Product motion: an explicit alternate renderer

Use this path only when the requested direction is a product/UI film. The
existing `render`, Episode, Ctx, caption baseline, palette, delivery fits and
house QC remain unchanged. A product film uses `style: product`, native canvas
coordinates and its own timeline. It does not run the explainer green-ratio QC.

## Direct, then build

The engine is a drawing/animation tool. The AI is responsible for design and
direction. Preset UI is optional; build a custom application surface from
general primitives rather than adding a special engine component per client.

### Evidence and review contract

1. State whether the brief requests close reconstruction or transfer of visual
   principles to a different product. Inspect actual moving reference clips;
   never claim the title, transcript or contact sheet establishes its motion.
2. Record observed, measured, inferred and unknown separately, with source
   times. Inspect cut candidates; a word-to-bar cut is not automatically a
   morph. Mark cropped, occluded or ambiguous measurements unresolved.
3. Design delivery-size key frames before animation: grid, margins, hierarchy,
   font metrics, palette and coherent product content. Do not add arbitrary
   dashboards, badges, empty cards or fake statistics to make the image busy.
4. Write choreography per object: initial pose, trigger, start/end, trajectory,
   overlap, landing and consequence. Keep the primary focus clear. Effects
   serve that action; no compulsory glow, 3D tilt, ambient movement or slide.
5. Render a 3–5 second proof covering the difficult transformation. Inspect
   native typography, clipping and spacing, then normal-speed timing. When
   matching a reference, align source and candidate times and compare video
   plus sampled overlays. Pixel scores and successful encode are not taste.
6. Record the weakest beat and the revision or remaining discrepancy. Check
   source state and continuity at boundaries. Extend only after revising a
   failed proof; this is self-review, not a new user permission gate.
7. Report what actually ran through Gilvy. A standalone experiment is evidence
   for an engine change, not proof that the engine supports it. Do not invent
   fidelity percentages or claim recovered fonts, layers, shutters or easing.

Use `examples/product/study/build.py` for the scoped 30–35s measurement study
and an unrelated metric-card exercise. Both render via ProductFilm; neither
is an approved visual standard or automatic reconstruction.

Read the supplied reference as a sequence of actions before choosing effects.
Name the object, action, carry, meaning and consequence for each beat. Keep UI
state changes legible: a menu opens before its destination enters; a learning
process produces something reusable; a workflow assembles before it is saved.
Do not describe a generated proof as a replica or recover source keyframes.

The example `examples/product/learning.yaml` is an original twelve-second
capability demonstration informed by the Numtera study: question -> knowledge
statement -> learning progress -> reusable workflow -> save. It uses code-drawn
UI, not extracted Numtera artwork. It does not reproduce the entire reference.

## Commands and MCP

For the revised UI visual reference, start with `examples/product/inbox.yaml`
and [the design review](../../docs/product-design.md). The older learning proof
is a renderer diagnostic, not the product design standard.

```bash
gilvy product-notes
gilvy preview-product examples/product/learning.yaml --out out/product-stills --times 1.3 4.8 6.5 9.8
gilvy render-product examples/product/learning.yaml --out out/product-proof.mp4 --start 4 --duration 4
gilvy render-product examples/product/learning.yaml --out out/product.mp4
```

MCP: `product_motion_notes`, `preview_product(spec_path, output_dir, times)`,
`render_product(spec_path, output, start=0, duration=None)`. The motion window
keeps the absolute film clock, including locally timed children; it does not replay entrances.
Use `inspect_product_frame(spec_path, frame, output)` for a native indexed PNG,
compiled layer timing/state and measured text. `gilvy serve-product film.yaml`
opens a local silent frame-seeking viewer; it is not a real-time/audio player.
MCP `start_product_render`, `product_render_status`, `cancel_product_render`
provide process-local observable jobs. Read [composition runtime](../../docs/composition-runtime.md)
for clocks, flow layout, particles, caching and job lifecycle limits.
Preview directories must be new. Video files are published atomically only
after encoding and integrity validation; an existing output is replaced only
by a validated result. Sidecars use `.product.json`.

## Film schema

```yaml
style: product
size: [1280, 720]
fps: 30
duration: 4
samples: 3
shutter: 0.6
audio: null
background:
  base: '#287af3'
  lights:
    - {x: 0.5, y: 0.3, radius: 0.8, color: '#f8fcff'}
layers:
  - id: statement
    type: text
    width: 1100
    height: 120
    x: 640
    y: 360
    text: One clear next step.
    size: 54
    reveal: words
    keyframes:
      progress: [[0, 0], [1.2, 1, linear]]
      scale: [[0, 1.4], [0.7, 1, out_cubic]]
      blur: [[0, 9], [0.7, 0, out_cubic]]
```

Film fields: `style`, `size`, `fps`, `duration`, `samples`, `shutter`,
`background`, `layers`, `audio`. Size contains two even integers 160..1920.
FPS is 1..60, duration >0 and <=120s. Background lights use normalized x/y and
radius (.05..3); Gaussian color fields are smoothly interpolated from a low
resolution image. Lights optionally carry numeric `keyframes` for `x`, `y`,
`radius`, `red`, `green`, `blue` (RGB channels 0..255), using the same global
clock/easing syntax as layers. Base color and alpha remain static. A static
background is cached; moving fields are evaluated at sample time.

Layers are drawn in list order, back to front. Each requires a unique `id`,
`type`, integer `width` and `height`. Defaults: center x/y = 0, scale 1, opacity
1, rotation/tilt/blur 0, progress 1; start 0 and end film duration. End is
exclusive. There are no implicit scene fades, fixed captions or hidden cuts.
Use `shadow: true` for a soft projected-plane shadow. Colors are Pillow hex
strings, including alpha such as `#ffffffdd`. Plane width/height define clipping;
text deliberately larger than its plane will crop. Inspect at delivery size.

## Components

| Type | Content fields | Use |
|---|---|---|
| `text` | text, size, weight, color, reveal | Centered multiline Poppins; reveal none/words/characters |
| `rect` | radius, fill, border | Rounded surfaces, highlights and click feedback |
| `progress` | label, accent | Label and progress track; progress is 0..1 |
| `cursor` | color | Code-drawn pointer; animate position and click scale explicitly |
| `menu` | title, items, selected, accent | Dropdown surface; progress reveals rows |
| `panel` | variant, brand, mark, badge, title, items, accent, fill | Shared UI frame; variants inbox/form/workflow |
| `group` | children | Compose child planes, then transform/clip the whole group |
| `image` | src | Local raster asset, aspect-contained and centered in its plane with alpha preserved |
| `inbox-part` | part, content | Native inbox surfaces: shell, sidebar, conversations, thread, customer, knowledge, reply |
| `counter` | value, prefix, suffix, decimals, decimal_separator; text controls below | Independent numeric track, unrelated to progress/fill |
| `ellipse` | fill, stroke, stroke_width | General ellipse in its local plane |
| `path` | commands, fill, stroke, stroke_width | M/L/Q/C/Z contours; progress reveals cumulative stroke length |
| `particles` | points, poses, dot_radius, color | Persistent indexed dots; equal-count pose interpolation |

Detailed inbox panels accept `content` fields documented in the design review.
They use the same measured layout as independently animated inbox parts. Use
native 1280x760 for a full reference; smaller planes scale it and do not reflow.

Image `src` resolves relative to the film YAML (including inside groups). URLs
are rejected; missing files fail before encoding. A decoded raster's first
frame is used; animated images do not become video textures. The caller's spec
is not mutated when paths are resolved. Images are cached by layer like other
static components. The native integer-translation path avoids unnecessary
projective resampling of aligned UI child planes.

For a longer staged example see [the 95-second product-film builder](../../examples/product/launch/README.md).

Inbox panels accept `navigation` and `subtitle`. Form `items` use
`Label: Value` strings and accept `button`. Workflow items are numbered steps
revealed by progress and optionally accept `button`. Menu selected is a
nonnegative integer (not animated). These are presentation components, not a
browser or a functional application. Compose rect/text/groups for a custom UI.

Bundled weights: Light, Regular, Medium, SemiBold. Word reveal adds complete
words; character reveal adds characters. The currently visible text is centered
within its plane. For fixed word positions or independent word travel, use a
text layer per word inside a group. No automatic
text morph or font identification is implied. Explicit `overflow: wrap` is
available for metric-based text; legacy text does not wrap automatically.

For custom typography set `font` to a local TTF/OTF path relative to the spec.
An explicit missing/unreadable font fails before encode; there is no silent
substitution. Omit it to use bundled Poppins. Text/counter controls: `align`
(left/center/right), `valign` (top/center/bottom), `padding` (pixels), `baseline`
(first baseline in local pixels), `line_height` (font-size multiple),
`letter_spacing` (pixels) and `overflow` (clip/error/wrap/fit), `max_lines`
(1..100), `min_size` (1..size). Opting into these controls
uses font metrics, retains full-string alignment during reveal, and never
automatically shrinks/wraps unless the explicit fit/wrap policy is selected.
Fit preserves authored line breaks and requires the chosen minimum size; wrap
breaks at words and fails on overfull unbreakable content. Legacy text specs
retain their rendering.
Counter `decimals` is 0..6; `decimal_separator` is `.` or `,`; prefix/suffix are
literal strings. It formats the numeric `value` track without coupling to fill.

Path commands are lists such as `[[M, 5, 40], [C, 30, 0, 70, 80, 115, 40]]`.
Start contours with M; L/Q/C add lines/quadratic/cubic segments; Z closes.
Curves are flattened to 32 segments. Closed contour fills appear in full;
`progress` draws the cumulative stroke. This is not an SVG parser, boolean
path engine or editable text-to-path converter. Fill holes are not supported.

## Timeline and transforms

`keyframes` maps an animatable property to `[global_seconds, numeric_value,
optional_easing]` entries by default. Times are unique/increasing and within the film.
Opt into `time_space: local` to make start/end parent-relative and keyframes
relative to this layer's own start. A local track must fit its layer duration.
Global remains the default, including for children of local groups. Parent
visibility always clips descendants. See the composition runtime for examples.
The easing on the **destination** entry controls that segment; default is
`smooth` (smoothstep). Other choices: `linear`, `out_cubic`, `in_cubic`, or a
four-number cubic Bezier `[x1,y1,x2,y2]` with x controls in 0..1. The x curve is
inverted numerically; it is not an interpolation of the four control values.
Before/after a track, its first/last value holds. Properties:

- x/y (center in pixels), scale (.01..8), rotation (degrees).
- tilt_x/tilt_y (-65..65 degrees): projected 2.5D plane, not a 3D mesh.
- opacity (0..1), blur (0..40 pixels), progress (0..1).
- value (-1e15..1e15), independent counter value.
- clip_x/clip_y/clip_width/clip_height (0..1 of local plane), clip_radius (pixels).
- pivot_x/pivot_y (0..1): the local pivot placed at x/y; defaults .5/.5.
- scale_x/scale_y (.01..8) multiply scale along the local axes.
- blur_length (0..128 parent-plane pixels), blur_angle (degrees, 0 horizontal).

Clipping is applied before projection to any layer or group. It changes visible
area, not the dimensions or font size of children. Bezier overshoot is allowed
for numeric tracks; normalized states are clamped to 0..1 and scale/blur to
their positive domain at evaluation. Keep your authored curve within the
intended resource range. Directional blur is a sampled spatial kernel, not an
automatic velocity estimator; filtering and resampling use premultiplied alpha.

Children use coordinates relative to their group's untransformed plane and
retain the global clock by default; local timing is explicit. Each group clips at its own bounds, then projects as
one image. Rotations use the configurable local pivot. Projection uses a fixed
camera distance of three times the larger unscaled plane dimension, adjusted
for scale. No auto camera tracking or scene graph z-sorting is performed.

`samples` (1..8) and `shutter` (0..1 frame) enable temporal supersampling of
the complete composite, averaged with the sRGB transfer function in linear
light. It is real sampled motion blur, but increases CPU cost and can mix
states around hard cuts. Use one sample or zero shutter for crisp diagnostics.
Layer Gaussian blur is a separate artistic control, not a motion estimator.

Each layer/group can also set `samples` (1..8) and `shutter` (0..1 frame).
Only that object/subtree is sampled into transparent planes, averaged in
premultiplied linear light and composited at its existing stack position.
Do not double-sample the same movement through both parent and child/global
sampling unless intentional; nested layer samples are limited to eight per
branch. Per-layer sampling costs full canvas planes and may straddle cuts.

### Import reviewed measurements

`gilvy.product_tracks.apply_measured_tracks(spec, report, time_origin=30)`
returns a new spec and provenance without mutating inputs. Report structure:
`{source: "study name", tracks: [{layer: "bar", property: "x", samples:
[{time: 30, value: 100, status: measured, confidence: 0.95}, ...]}]}`.
Statuses measured/reviewed are accepted; estimated requires explicit
`allow_estimated=True`. Rejected/unknown/null or confidence below .8 fail.
Confidence is the reviewer's declaration, not a certified model score. Times
must be unique, increasing, and land within the destination clock after
subtraction of source origin plus any local track origin.
Import creates linear tracks and validates the complete result. Preserve the
returned provenance beside the film. It does not run tracking/OCR or clean
ambiguous detections; those remain explicit analysis work.
MCP `import_product_tracks(spec_path, measurements_path, time_origin=0,
allow_estimated=False, minimum_confidence=.8)` returns the imported spec and
provenance without writing files. Returned asset paths are absolute, resolved
from the original spec; save the returned spec explicitly before rendering.

Resource guards: at most 100 planes, nesting up to six group levels, 32 million
total local-plane pixels. The compositor uses Pillow/NumPy on CPU. Render a
short low-resolution proof before a large/high-sample master.

## Audio and verification

Default audio is silent. Set `audio` to a local file relative to the YAML for
music or a finished mix; the render window seeks the same source time, pads
short audio with silence and trims it to video length. No TTS, music generator
or automatic beat synchronization runs in this path. Files are encoded H.264,
yuv420p, with AAC only when audio is supplied.

Validation decodes/counts frames using ffprobe, checks dimensions, duration and
expected audio presence, then publishes the output. Duration rounds up to a
whole frame. QC reports `scope: technical_integrity`; it does not apply house
color rules, establish reference fidelity or approve creativity. Preview
stills check layout; also inspect an encoded short window for pace, clipping,
readability, continuity and consequences before a full render.

This first product compositor does not import Figma, SVG, HTML, video textures,
or editable layers from a reference; it has no GPU, 3D mesh, automatic asset
extraction, automatic object tracking or physically simulated depth of field.
Describe those as future capabilities rather than implying they are present.

## Composition tools

Read [composition-runtime.md](../../docs/composition-runtime.md) for compiled
frame coverage, local/global timing, root particles, measured row/column groups,
strict text fit/wrap, the local frame viewer and MCP render job lifecycle.
Try `examples/product/composition.yaml` as a six-second technical diagnostic.
These are independently implemented Python capabilities, without a Remotion
dependency. They do not automatically design coherent UI or certify creativity.
