# General compositor

Use `style: product` for custom typography, abstract/brand motion and UI films. The name is retained for schema compatibility. No compulsory green, fixed house caption, stationary camera, ambient movement, numerical CTA or application template.

MCP: read `product_motion_notes`; use `preview_product`, `inspect_product_frame`, `render_product`, or `start_product_render` with `product_render_status`/`cancel_product_render`. Discover actual tool signatures before calling. CLI: `gilvy product-notes`, `preview-product`, `inspect-product`, `render-product`.

## Minimal schema

The [bundled example](../examples/kinetic.yaml) is complete and requires no external assets. `size` is two even integers 160..1920; `fps` an integer 1..60; `duration` >0 and <=120 seconds. Layers have unique IDs, type, width, height, x/y center and optional keyframes. Supported types include text, rect, ellipse, path, particles, image and group; UI presets are optional.

Numeric tracks use `property: [[time, value], [time, value, ease]]`; the destination key controls its incoming easing. Times default to global film seconds. `time_space: local` makes start/end parent-relative and keys relative to the layer's start. Parent visibility clips children. Do not transfer image-episode keyframe grammar directly: that path uses dictionaries and outgoing easing.

Text can specify size, weight, color, local font path, reveal, align, valign, padding and overflow (`clip`, `error`, `wrap`, `fit`). Inspect native text; choose a readable `min_size` when fitting. Image `src` and font resolve relative to the YAML. Images are static raster assets, not video textures. Groups contain children and can transform/clip together.

Default audio is silent. Optional `audio` is a local file trimmed/padded to the film/window; no implicit TTS. Preview stills do not validate rhythm. A `render_product` start/duration window preserves the film clock. Read the installed notes before advanced fields, masks, particles, custom curves or imported measurements.

## Limits and review

CPU renderer, projected planes rather than full 3D, up to 100 layers and 32M combined layer pixels. MP4 export is not alpha-master export. The frame inspector is a silent exact-seek viewer, not real-time audio playback. Inspect an encoded proof; neither effects nor a technical PASS establishes reference fidelity.
