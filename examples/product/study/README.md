# General-tool motion proofs

These two five-second films use only Gilvy's reusable product layers. They do
not add a ticket-specific renderer, paste reference screenshots or call an
external drawing callback. The AI/example builder authors the layout and
choreography; ProductFilm handles text, shapes, paths, masks, transforms,
independent counters and effects.

## Reproduce

Provide a local URW Base35 font directory containing NimbusSans-Regular.otf,
NimbusSans-Bold.otf and NimbusMonoPS-Bold.otf. Fonts are external inputs and
are not redistributed in this repository. On Debian-family installations they
are commonly under `/usr/share/fonts/opentype/urw-base35` after installing the
URW Base35 fonts package. Use your actual directory, not that assumption.

```bash
PYTHONPATH=src python examples/product/study/build.py \
  --font-dir /path/to/urw-base35 --out out/primitive-study --render
```

The output directory must be new because preview evidence must not mix runs.
The builder copies the three chosen fonts into the output and writes portable
JSON specs, measurement provenance, preview sheets, integrity sidecars and MP4s.
Use the fonts according to their accompanying license. These are substitutions,
not an identification of the reference's original fonts.

## Numtera scope

Reference supplied by the user: ObiN Studio's Numtera product launch film,
https://www.youtube.com/watch?v=awUYikrGsKk. Source frames 900..1049 at 30fps:
30.000..34.9667 seconds, five seconds of playback at 1920×1080. Raw measured
positions are stored in measurements.json. Object IDs were assigned manually;
color masks/projections measured visible bounds. No general tracker/OCR runs.

Source video/artwork/audio is not bundled. The scene reconstructs words,
oversized bar, independent counter, opening card and scanline using text,
rectangles, ellipses and groups. The shot changes with a cut at source 31.4s;
it is not a recovered word-to-bar morph. The counter and fill do not share a
numeric track. Mask height reveals panel content without changing glyph size.

Hidden bar geometry, cropped-word positions, fill normalization, carrier offset,
font substitutions, background, card opening and blur are estimates. Import
opts into estimated samples explicitly and writes provenance. The raw
mono_label_visible_bbox can select a percentage or fragment; it is not used as
a trusted clean label track. Confidence numbers are reviewer declarations.

## Transfer exercise

`metric-exercise.mp4` is an unrelated dark card with a fictional capacity
counter and a curved path reveal. It demonstrates custom composition using the
same tools, not reference fidelity or a real economic measurement.

## Review

See [engine review](../../../docs/product-primitives.md) for paired evidence,
technical results and the remaining discrepancies. A decodable render does not
certify visual quality, and these proofs are not user-approved design masters.
