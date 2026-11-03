# Ruang: a long product-film proof

This is an original 95-second concept for a fictional support product. It uses
Numtera's observed storytelling mechanisms as a study: problem, introduction,
product interaction, shared knowledge, repeatable workflow, benefit and close.
It does not copy Numtera's assets, narration or soundtrack and does not claim
to reproduce its exact motion. Ruang is not a functional SaaS shipped by Gilvy.

```bash
# Generate original raster surfaces, 21 shot YAMLs, a timeline and storyboard:
PYTHONPATH=src python examples/product/launch/build.py --out out/ruang-launch
# Render each shot through Gilvy, concatenate, and add an original ambient bed:
PYTHONPATH=src python examples/product/launch/build.py --out out/ruang-launch --render --workers 4
```

The result is `Ruang_Product_Film_95s.mp4`: landscape 1280x720, 30 fps, 2,850
frames, Indonesian on-screen copy, synthesized ambient music and no voiceover.
Assets are generated from code using the inbox design system and measured UI
text. They are not fetched from the network. The raster layers keep their own
aspect ratio/alpha; workflow frame and steps are independently composed.

The builder writes intermediate assets and shot specs beneath the selected
output directory. Each shot uses its own local timeline; `timeline.json` maps
it into the complete film. Rendering runs in independent worker processes and
each shot must pass the product renderer's integrity validation before concat.

## Direction

- Repeated panels surround one question; typography interrupts the pattern.
- Product introduction gives way to a tilted inbox, then a close view of the
  actual conversation. Cropping is an explicit focus move, not responsive UI.
- A source panel enters beside the conversation, followed by approval and a
  learning bar that travels upward into a knowledge-card composition.
- The answer is reused for a second fictional question. The next section
  moves from menu navigation to configuration and step-by-step workflow build.
- Save feedback changes at the pointer action, then the overview returns.
- Bright and dark typography sections separate explanations from product UI.

The seven-second workflow shot can be rendered/reviewed independently with
`gilvy render-product out/ruang-launch/shots/15.yaml --out out/workflow-proof.mp4`.
Inspect a storyboard first and the encoded motion proof next. Full-film review
must check concatenation boundaries, clipping, text at the focus/overview sizes,
decode integrity, total duration and audio. The example is a visual proof for
review before merging, not an automatic creative approval.
