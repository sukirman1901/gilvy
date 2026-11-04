# Editorial collage: assets, composition and object motion

Use this contract for a reference or brief built from paper, photos, cutouts,
editable type and annotations. Read it before generating assets. The director
chooses what the relationships mean; Gilvy draws the authored composition.

Contents: production order; asset semantics; scene schema; coordinates and
clocks; attached annotations; asset checks; proof and limits.

## Production order

1. Inspect the supplied moving reference. Separate observed composition and
   action from inferred layers/camera/easing. Frame strips alone do not prove
   normal-speed rhythm or sound synchronization.
2. Write each beat as object, action, carry, meaning and consequence. Specify
   beginning/end poses and which object draws attention next. Frame pairs in a
   storyboard are states, not automatically separate scenes of equal duration.
3. Inventory assets by role before writing prompts. Identify background,
   subject/object, printed photo, paper, foreground and editable annotation.
   Pick a static reading hold where the data needs it. Movement is optional
   there; do not add drift just to satisfy a camera-speed metric.
4. Compose native-size keyframes from those parts. Use clean plates and real
   transparent cutouts where needed. Preserve existing approved assets/poses
   when revising; the acceptance of an asset is not approval of every layout.
5. Author local object tracks, camera framing, annotation timing and transitions.
   Seed the next information object before moving attention to it. Reuse asset
   IDs and explicit clocks where continuity is intended.
6. Inspect a 6–8 second encoded proof containing the difficult handoff. Check
   intermediate frames, occlusion, source readability and boundary continuity,
   then playback with sound when available. Record remaining discrepancies.
7. Extend the film and run technical QC. QC and asset integrity cannot certify
   composition, metaphor, factual relationships or reference fidelity.

## Asset semantics and prompts

Distinguish a believable physical setting from a deliberately assembled
editorial collage. Placing two objects in the same photographic environment
asserts co-location. A pump in a rice field therefore requires evidence of
that location; shared subject matter is insufficient. Separate unrelated
materials with paper/photo edges, negative space or a new composition.

The asset manifest keeps the scene brief as metadata. In `composition: collage`,
each generation prompt includes only that layer's subject prompt. It must not
tell the generator to merge every noun from the narrative into a single photo.
Inspect the generated content; no keyword checker understands its geography.

| Role | Preparation | Animation implication |
| --- | --- | --- |
| background/texture | Clean complete surface; fill hidden regions | May move least or remain still |
| subject/object | Complete silhouette, matching pose/light, true alpha when declared | Moves independently; do not cover-fit a person to the whole screen |
| photo | Deliberate crop, printable edge or matte | Rotate/scale as a physical fragment |
| paper | Empty readable surface, consistent light/shadow | Attach native text and annotations to its local plane |
| foreground | Deliberate occluder, complete edges | Covers objects according to list order; not an arbitrary transition prop |

Create a character/style reference first when identities recur. Produce master
keyframes, then derive their clean plates and cutouts while preserving framing.
Generation can redraw detail; masking in an image editor offers more direct
pixel control when exact extraction matters. Check alpha edges, hands, props,
lighting and alignment against the selected master. A drawn checkerboard is
not transparency. Baked typography is unsuitable for editable narrative text.

Keep photo/material colours if already graded appropriately. Collage defaults
to `grade: none`, `grain: 0`; grading an already warm image again can erase
colour separation. Optional paper/grain/grade still need deliberate authoring.

## Scene schema

Use `type: image`, an existing opt-in `style: vox-explainer` or
`style: history-story`, and `composition: collage`. House scenes are unchanged.
See `examples/technical/editorial-collage.yaml` for an asset-intake example.

```yaml
name: editorial
style: history-story
audio_mode: silent
scenes:
  - id: evidence
    type: image
    composition: collage
    min: 4
    caption: [One clear relationship]
    prompt: A photographed subject leads attention to an editorial data page.
    transition_out: cut
    camera: {from: {scale: 1}, to: {scale: 1}}
    layers:
      - id: surface
        role: background
        src: assets/paper.png
        alpha: opaque
        depth: 0
        prompt: One complete warm ivory paper texture, no objects or text.
      - id: photograph
        role: photo
        src: assets/photo.png
        alpha: opaque
        depth: 0.5
        prompt: One photograph of the chosen subject, with no other collage props.
        placement:
          x: 350
          y: 1050
          width: 590
          height: 960
          rotation: -9
          fit: cover
          matte: '#f0e8d5'
          padding: 16
        tracks:
          - property: x
            keys: [{t: 0, v: 0}, {t: 4, v: -100}]
          - property: scale
            keys: [{t: 0, v: 1}, {t: 4, v: 0.75}]
      - id: page
        role: paper
        src: assets/page.png
        alpha: opaque
        depth: 1
        prompt: One blank editorial ivory sheet; no writing, seals or photo scenery.
        placement: {x: 650, y: 940, width: 700, height: 1100, rotation: -3}
        tracks:
          - property: scale
            keys: [{t: 0, v: 0.6}, {t: 3, v: 1, ease: easeOutCubic}]
          - property: opacity
            keys: [{t: 0, v: 0}, {t: 1, v: 1}]
    overlays:
      - kind: text
        parent: page
        at: 1.5
        text: '44,63%'
        layout: line
        font: serif
        size: 120
        x: 350
        y: 420
        hold: 3
      - kind: circle
        parent: page
        at: 2.4
        duration: 1
        cx: 350
        cy: 420
        r: 190
```

The number in this schema demonstrates typography; choose source/period/units
and a visible source label for the actual editorial story. A static schema
example is not a verified factual reconstruction or a completed film.

## Coordinates, transforms and clocks

Layers draw back-to-front in list order. Collage layers require unique `id`
within each scene and explicit `role`. `alpha` is `any` (default), `opaque` or
`transparent`. Declare transparency for cutouts whose opaque backdrop would
otherwise occlude the scene. The renderer cannot infer correct alpha from a
`.png` extension.

`placement` opts a layer into a bounded fragment plane. Required width/height
are 1..4096 design pixels. x/y are its centre, defaults 540/960, within ±8192.
Static scale .05..4, rotation ±180 degrees and opacity 0..1 are optional.
`fit: contain` (default) preserves the complete source inside the plane;
`cover` crops it. A matte colour and padding 0..128 can create a photo border.
Padding must leave a positive inner plane. Material remains rectangular; this
is not a mesh, paper bending or a freeform clipping-mask API.

Layer `tracks` use the existing `{property, keys: [{t,v,ease,...}]}` syntax.
Properties are x/y offsets from placement, scale multiplier, additive rotation,
and opacity multiplier. Fragment scale keys support .05..4 (the camera
retains its own existing scale bounds). The easing on a key controls the following segment.
The camera acts about the design-frame centre with the existing depth gain,
then adds its pan. Placement units and offsets follow delivery fitting.
Sources retain aspect under contain/cover; no full-screen cover fit is applied
to the fragment. Layers without placement retain legacy plate sizing. Their
accepted rotation/opacity tracks now actually affect rendering.

`clock: scene` (default) samples local seconds, with keys 0..30.
`clock: episode` samples actual film seconds, with keys 0..600. This clock uses
the final scene starts, including voice-length changes, rather than summing
unverified min values. Preview windows and incoming dissolve handles retain
absolute time. To continue an object, reuse its source, placement and episode
track values on both sides of the boundary. An ID alone does not create a
global object registry or guarantee matching framing. Camera changes, matte,
occluders and differently authored poses can still make a discontinuity.

Collage permits a static camera and reading holds. Existing shot duration
limits still apply, and a moving camera still receives its normal rate checks.
Image plate scenes without the opt-in retain the existing movement rules.

## Attached annotations and layering

`overlays[].parent` names a layer with placement. Overlay x/y/cx/cy coordinates
are local to that untransformed plane, from its top-left corner. Text, circle,
highlighter and other existing overlays paint on the plane before projection:
they inherit its opacity, rotation, scale and camera motion. Later layers can
cover them naturally. Overlays without parent remain screen-space overlays.

Overlay `clock` is explicitly scene or episode, independently of its parent.
To continue an annotation across scenes, reuse it and select episode clock;
do not assume inheriting geometry also inherits entrance timing. Episode-clock overlays require explicit `at` in 0..600 seconds; hold/draw durations retain existing limits.
`text.layout: line` keeps an editable phrase on one line. Existing default
`stack` retains one word per line. Text fitting and readability still require
native inspection; a successful fit is not a hierarchy decision.

## Asset checks and evidence

`gilvy assets` / MCP `asset_manifest` returns ID, role, clock, placement,
per-asset prompt, separate scene brief, and estimated source dimensions. A
fragment needs resolution for its authored dimensions and peak scale, not
full-frame pan overscan. Plate overscan now includes intermediate camera keys.
These estimates use key extrema; Bezier overshoot and unusual framing need
additional margin and inspection.

Existing collage assets are decoded and checked for empty alpha, required
transparency/opacity, file decodability and a 16-megapixel budget per asset. Invalid
collage assets fail render preflight before encoding. A fully opaque fake
checkerboard cutout is caught when transparency is declared; a checkerboard
inside a partly transparent image still needs visual inspection.

Whole-reference histogram QC is not applied to individual collage fragments:
a dark subject cutout and a light complete scene have different pixel
distributions by design. The manifest marks them not comparable. Compare the
rendered composition with aligned reference evidence instead. No automatic
checker certifies that the pump belongs in a particular field or that the
depicted relationship is justified.

Available operations are independent fragments, shared clocks, camera framing,
matte borders, editable attached annotations and back-to-front occlusion.
The separate `gilvy cutout` command can prepare a subject mask with the optional
`cutout` extra. Its background fill is a blur, not recovered scene geometry.
This collage mode does not perform segmentation during rendering. Inpainting,
anatomy repair, 3D cameras, joint rigs, global object reuse by ID, automatic
scene matching and a creative-quality score are not supplied. Expose those as gaps rather than claiming a storyboard
or list of vocabulary has implemented them.

Reproduce the procedural four-second diagnostic (not a reference reconstruction):

```bash
python examples/technical/build_collage_demo.py --out /tmp/collage-demo
gilvy assets /tmp/collage-demo/editorial-collage.yaml
gilvy preview-motion /tmp/collage-demo/editorial-collage.yaml --start 0 --duration 4 --out /tmp/collage-demo/proof.mp4
```
