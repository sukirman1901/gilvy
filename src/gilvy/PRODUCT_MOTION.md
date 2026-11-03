# Product motion: an explicit alternate renderer

Use this path only when the requested direction is a product/UI film. The
existing `render`, Episode, Ctx, caption baseline, palette, delivery fits and
house QC remain unchanged. A product film uses `style: product`, native canvas
coordinates and its own timeline. It does not run the explainer green-ratio QC.

## Direct, then build

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

```bash
gilvy product-notes
gilvy preview-product examples/product/learning.yaml --out out/product-stills --times 1.3 4.8 6.5 9.8
gilvy render-product examples/product/learning.yaml --out out/product-proof.mp4 --start 4 --duration 4
gilvy render-product examples/product/learning.yaml --out out/product.mp4
```

MCP: `product_motion_notes`, `preview_product(spec_path, output_dir, times)`,
`render_product(spec_path, output, start=0, duration=None)`. The motion window
keeps global time, including group children; it does not replay entrances.
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
resolution image. The background is static in this version.

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

Inbox panels accept `navigation` and `subtitle`. Form `items` use
`Label: Value` strings and accept `button`. Workflow items are numbered steps
revealed by progress and optionally accept `button`. Menu selected is a
nonnegative integer (not animated). These are presentation components, not a
browser or a functional application. Compose rect/text/groups for a custom UI.

Bundled weights: Light, Regular, Medium, SemiBold. Word reveal adds complete
words; character reveal adds characters. The currently visible text is centered
within its plane. For fixed word positions or independent word travel, use a
text layer per word inside a group. No automatic
text morph, line wrapping or font identification is implied.

## Timeline and transforms

`keyframes` maps an animatable property to `[global_seconds, numeric_value,
optional_easing]` entries. Times are unique/increasing and within the film.
The easing on the **destination** entry controls that segment; default is
`smooth` (smoothstep). Other choices: `linear`, `out_cubic`, `in_cubic`.
Before/after a track, its first/last value holds. Properties:

- x/y (center in pixels), scale (.01..8), rotation (degrees).
- tilt_x/tilt_y (-65..65 degrees): projected 2.5D plane, not a 3D mesh.
- opacity (0..1), blur (0..40 pixels), progress (0..1).

Children use coordinates relative to their group's untransformed plane and
share the global clock. Each group clips at its own bounds, then projects as
one image. All rotations use the center of the plane. Projection uses a fixed
camera distance of three times the larger unscaled plane dimension, adjusted
for scale. No auto camera tracking or scene graph z-sorting is performed.

`samples` (1..8) and `shutter` (0..1 frame) enable temporal supersampling of
the complete composite, averaged with the sRGB transfer function in linear
light. It is real sampled motion blur, but increases CPU cost and can mix
states around hard cuts. Use one sample or zero shutter for crisp diagnostics.
Layer Gaussian blur is a separate artistic control, not a motion estimator.

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
extraction, arbitrary Bezier easing or physically simulated depth of field.
Describe those as future capabilities rather than implying they are present.
