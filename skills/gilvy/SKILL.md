---
name: gilvy
description: Direct and render Gilvy explainers or SaaS/product motion films. Use for creating, editing, studying references, previewing or reviewing motion graphics. Choose the renderer from the brief, design the picture and choreography, and inspect an encoded proof before a full cut.
---

# gilvy

## Choose the production path first

For explicitly requested SaaS/product motion, read
[product motion](../../src/gilvy/PRODUCT_MOTION.md), including its evidence and
review contract, before the explainer directions below. MCP agents call
`product_motion_notes`. Use `style: product` and `preview-product` /
`render-product`; do not impose the explainer's Poppins, dots, green quantity,
caption baseline, fixed camera, mandatory ambient motion or duration ratios.
Use primitive layers for a custom composition. Inbox/menu/panel presets are
optional accelerators, not the universe of possible designs. The AI authors
the visual hierarchy, functional story and choreography; Gilvy executes them.
Do not add an engine template for each new reference. When a necessary drawing
operation is missing, name the capability gap before claiming fidelity.

For the established explainer show, follow the locked system below.

gilvy renders an explainer from a YAML episode. **Default delivery** is one locked vertical master: **1080×1920 (9:16), 60 fps**, 2× supersampling down to 1080p, Poppins, near-black background, white structure, one green quantity. You direct the episode. You do not restyle the renderer, and you do not fill a scene-type form.

## Direct the picture first

Read and follow this before intake, before YAML, and before `list_scene_types`. MCP agents call `directing_notes` and receive the same text.

<!-- directing:start -->
# Direct the picture

You are the director of this episode. The scene library is a set of performances you already know how to stage. It is not a form to fill by matching keywords. A video feels like a slide deck when each sentence introduces a new chart. A video feels directed when one object stays in frame and each sentence is a verb that object performs.

Do this pass before you write YAML. Call `directing_notes` if you are on MCP, and do not call `list_scene_types` until the verbs exist.

## 1. Verb, then type

For every spoken line or caption beat, write five fields in your plan. They never appear on screen.

- **Object.** The noun in the frame. Prefer the object from the previous scene.
- **Verb.** What it does during this sentence: draws, falls, drains, counts, splits, travels, fills, checks, converges, returns. "Shows", "lists", and "explains" are not verbs. Rewrite the line until a physical verb exists.
- **Carry.** What is already on screen, and the one thing that changes.
- **Meaning.** What relationship or feeling the action makes understandable without the caption.
- **Consequence.** What the action changes or leaves behind for the next beat.

A verb alone is not a direction. "Dot travels" can satisfy a form while communicating nothing. "The accumulated trail bends into the wall that blocks the dot" has a visible cause and consequence. Hide the captions mentally: identify what the picture still contributes. Not every sentence must be understandable without words, but the picture must add more than decoration.

Then pick a type whose verb is that verb. If none is, write a `python` scene. That is normal directing, not a fallback for experts.

| Verb you wrote | Performance |
|---|---|
| An object is born, then one price lands | `bowl_hook` |
| One thing falls into the object already there | `coin_drop` |
| A figure turns into a count of the same unit | `ring_drain` |
| The count continues instead of starting over | `ring_drain` with `count_from` |
| Two counts you already showed share one grid | `compare` |
| The object comes back and asks one thing | `bowl_cta` or `coin_cta` |
| A date is the subject, and a marker travels to it | `timeline` |
| The sentence is actually a set of bars | `highlight` |
| The sentence is actually boxes being checked | `checklist` |
| The sentence is actually vessels filling | `jars` |
| Several things become one | `converge` |
| Any other verb | `python` — `draw(ctx, u, duration, params)` |

`highlight`, `checklist`, `timeline`, and `jars` are specific sentences. They are not the default shape of an explainer. Matching the topic word ("tips", "steps", "growth", "history") to one of them is how a cut becomes PowerPoint.

## 2. How a directed cut behaves

Study `examples/ep01-mie-ayam.yaml` for the directing, not for the topic.

1. The bowl draws itself. Chopsticks follow. Steam starts. The price arrives only after the object exists.
2. The same bowl stays. A coin falls into it. The sentence is an assumption. The picture is a fall.
3. The wage drains and is counted in bowls. The number is the motion.
4. The next wage does not reset the grid. `count_from` carries the previous count forward.
5. Those same dots become the comparison. No new chart.
6. The bowl returns. One question.

A video about rent, coffee, or a subscription uses the same chain with different nouns. It does not become a checklist of three reasons unless the spoken line is literally three checks.

## Motion craft

Gilvy has one personality. Entrances decelerate (`eo`). Travel eases both ways (`eio`). A coin impact uses `eexp`. There is no bounce, no squash, and no second easing family. Do not import a playful overshoot from a UI motion guide. The show is closer to a quiet premium piece: one curve, strokes near 1.6, white structure, one green quantity.

Every scene needs three layers. A frame with only the primary action looks like a slide.

- **Primary.** The verb the eye follows. One hero. It enters first or travels farthest.
- **Secondary.** Something that follows 0.1–0.2 seconds later: chopsticks after the bowl, steam after the rim, a label after the number, a glow that grows as the object lands. Smaller than the hero.
- **Ambient.** Life that continues after the pose settles: steam, a small pulse on the object that already landed, a grid that keeps a faint life. It never introduces a new idea. The camera stays still.

Stage the sentence as a short story, not a state change.

| Share of the scene | What the viewer gets |
|---|---|
| First ~0.6s | Setup. The object is born or is already there from the previous scene. |
| Until 65% | Action. The verb is still happening. The 45% preview frame must not match the 12% frame. |
| After 65% | Resolution. The pose is readable. Secondary parts finish. Ambient continues. |

Paths say something. A fall is vertical. A count grows in place. A continuation does not fly in from a new corner. All parts of one scene share one origin. If the hero moves, a trailing part is later and shorter, not a second hero moving the other way.

Reject the scene when:

- The only change is opacity.
- The hero travels in a straight line across more than a third of the frame with no change of pace.
- Two objects are both the hero.
- Nothing follows the hero. The landing has no steam, glow, label, or trailing stroke.

## 3. Write the motion when the library has no verb

`entry: scene.py:draw`. The function is `draw(ctx, u, duration, params)`.

Use Ctx primitives or the composed `gilvy.elements.draw_element` helpers. Discover them with `list_visual_elements`; read `motion_reference` for the API and Bojonegoro study. An element is a component, not a scene type or a reason to add another hero. Available primitives: `line` (pass `p` to draw on), `circ` (`p` draws the ring), `arc`, `poly`, `rect`, `dot`, `coin`, `glow`, `text`, `money` (this one is green), `label`, `check`, `bar`, `fillrect`, `coins_flow`. Travel with `lerp` and `eio`. Fade in with `eo`. Time with `R(u, start, end)`.

Stage it like the library:

- One or two objects. Focal point `(513, 780)`. Strokes near 1.6.
- The entrance finishes in about a second: `eo(R(u, 0, 0.6))`.
- The verb itself lasts the sentence: `eio(R(u, 0.4, duration - 0.6))`. A move that ends at 1.5 seconds and then sits is a still with a voice-over.
- Green is one quantity, the same one the voice is counting. Everything else is white. Captions stay white.
- Carry the previous object in. If the last scene was a coin, this scene starts from that coin.

```python
from gilvy.easing import R, eio, eo, lerp

def draw(ctx, u, duration, params):
    c0 = (ctx.theme.cx, 780)
    appear = eo(R(u, 0, 0.6))
    travel = eio(R(u, 0.4, max(1.2, duration - 0.6)))
    ctx.glow(c0, 140, appear * 0.5)
    pos = lerp((ctx.theme.cx, 420), c0, travel)
    ctx.coin(pos, appear, r=18)
```

Replace the coin with the verb you actually wrote. Do not ship this sample unchanged.

## 4. Reject your own cut before preview

Read the scene list back as verbs. Throw it out when any of these is true:

- Two scenes in a row each bring a new object.
- A verb is "display", "list", or "text on screen".
- `checklist`, `highlight`, `timeline`, or `jars` got picked because of a topic word.
- Pausing the frame at one second would already tell the whole sentence.
- Green means two different things.
- A scene longer than about 12 seconds has only one verb. Split it into two beats of the same object. A camera zoom does not replace that second beat.

When two chains are possible, prefer the one with the clearest cause and consequence, then preserve its objects across cuts. Use stills to inspect layout. The 80% frame is expected to be settled; it does not establish how long the action lived. Watch a motion clip to judge that.

## 5. Timing, preview, delivery

A library verb runs until 65% of the scene, then holds the pose. The frame at 80% is the settled picture, which is what QC measures. The first 0.6 seconds stay the entrance. On a scene longer than 7 seconds, the object that already landed keeps a small local idle after that 65% mark. The camera does not zoom.

`gilvy preview` writes three frames per scene: `sNN-t12.png` (entrance), `sNN-t45.png` (the verb), `sNN-t80.png` (the read), plus `motion.png` in that order. If the 12% and 45% frames look the same, the verb died early. Lengthen it, or stage it in `python` with `eio(R(u, 0.4, duration * 0.65))`.

`format` on the episode, or repeatable `--format`, redraws the same design into a safe rectangle. Profiles: `vertical_9x16` (default, full frame), `vertical_9x16_safe`, `portrait_4x5`, `square_1x1`, `landscape_16x9`. One `--format` keeps the output path. Several write `name-<profile>.mp4`. QC runs on each file. This is a fitted show, not a new landscape composition.

## 6. Prove the motion before the full cut

Choose a narrative shape before applying a template. A numerical explainer may use setup, quantity, comparison, and question. A reflective piece may use conflict, pressure, change, and an open ending. Do not add an arbitrary number or a comment CTA to fit the explainer recipe.

Render a 5–8 second `preview_motion` window containing the defining transformation and, when possible, a scene boundary. Watch it at normal speed and phone size. Review:

- Does the action communicate the intended relationship with captions hidden?
- Does something happen because of the previous action, rather than another symbol appearing?
- Do pace, pauses, contrast, and scale support the sentence?
- Is the secondary motion supporting the action, or disguising an otherwise static picture?

Revise a failed motion proof before rendering the full cut. This is a self-review requirement, not an extra permission gate. If the user explicitly requests sample approval, deliver the sample and wait; otherwise continue within the task's authorization.

When continuing an approved cut, keep the approved scene source and authored timing. Use `compare_versions` on matching-resolution videos, aligning their time ranges. Inspect paired frames and differences; codec noise and the removal of an old sample's outro may be intentional. Sampled equality is not proof that every frame is unchanged. Explain intended changes instead of claiming a comparison automatically approves the revision.

Technical QC checks the output's integrity and style constraints. It does not assess metaphor, emotional impact, rhythm, or originality. A `QC PASS` is never a creative-quality verdict. Do not invent an anti-slop score from motion energy, pixel change, glow, or number of effects.

## 7. Then the usual production pass

Choose audio mode first: `voiceover` (default), `ambient`, or `silent`. For voiceover, write the spoken line before the caption and time against the actual voice. For ambient/silent, set explicit scene `min` durations for reading; TTS is not called. Keep captions under five words per line, keys copied exactly, inspect stills, watch the motion proof, render, then run technical QC. Diagnose the reported failure; fix episode inputs or custom scene logic as appropriate, rather than changing the locked drawing engine.

## 8. Opt-in photo presets

The sections above are the house explainer. The camera stays still, and the picture is drawn.

`style: vox-explainer` and `style: history-story` are opt-in exceptions for photographic and painterly plates. They do not change a house episode. Read `reference_styles` before writing one. Those episodes use `type: image` for Ken Burns, parallax layers, dissolves, grade, and overlays. Do not fake them by zooming a house scene.
<!-- directing:end -->

## Creative references and examples

Read [references/creative-review.md](references/creative-review.md) when choosing a new metaphor or when a cut feels generic. It contains a weak/strong comparison, reference-study prompts, and the reflective `examples/reflection.yaml` motion proof. Transfer the relationship and timing principles; do not copy a third party's artwork or force every topic into a dot-and-circle story.

Read [the visual vocabulary and Bojonegoro study](../../src/gilvy/MOTION_REFERENCE.md)
when choosing people, fire, nature, buildings, or infrastructure, or continuing
a data story. Use `gilvy elements` / MCP `list_visual_elements` to discover the
14 composable helpers; `gilvy motion-reference` / MCP `motion_reference` returns
the same guide. Draw them inside a `python` scene with `gilvy.elements.draw_element`.
Keep one hero; the vocabulary specimen is not an editorial grid template.

## Intake (do this before writing YAML)

Treat every job like a small production brief. Confirm or assume defaults; only skip a step when the user already answered it in the same thread.

| Step | Question | Default if silent |
|---|---|---|
| 1 | **Delivery profile** — which master? | `vertical_9x16` → 1080×1920 (see table below) |
| 2 | **Platforms** — where will this ship? | Same as profile (usually Reels + TikTok + Shorts from one vertical master) |
| 3 | **Audio mode, language and voice** | `id-ID` / `id-ID-ArdiNeural` or `en-US` / `en-US-AndrewNeural`, `rate: "-8%"` |
| 4 | **Length** — beats or target seconds | Six-beat short (~25–35 s) unless the user asks otherwise |
| 5 | **Topic and CTA** — one idea, one ask | One fitting ending; a reflective piece may end without a CTA |
| 6 | **Filename** — episode id for `out/` | `gilvy new <slug>` or copy an example YAML |
| 7 | **QC bar** | `gilvy qc` must pass before calling the cut “final” |

**Agent todo (copy into your plan and check off):**

- [ ] Delivery profile chosen (default `vertical_9x16`)
- [ ] Platforms listed; derivatives noted if not all 9:16
- [ ] Voice and language set on the episode
- [ ] Narrative shape selected for the topic; no forced numerical beat or CTA
- [ ] Object, verb, carry, meaning, and consequence named for each beat
- [ ] `directing_notes` read; verbs named before types
- [ ] `preview` with `--tts fixture` reviewed, including `motion.png`
- [ ] 5–8 second motion proof watched; creative review recorded in concrete terms
- [ ] Approved material compared when extending an existing cut
- [ ] `render` with the chosen audio mode; real voice for narrated delivery
- [ ] Technical `qc` result recorded separately from creative judgment

## Delivery profiles

Set `format` in the episode or pass repeatable `--format`. The design stays 1080×1920 and is fitted, uniformly, into the safe rectangle. Circles stay circles. `vertical_9x16` is identity: no inset, byte-for-byte the show.

| Profile | Pixels | Insets L,T,R,B | Where it ships |
|---|---|---|---|
| `vertical_9x16` (default) | 1080×1920 | 0,0,0,0 | Reels, TikTok, Shorts, the master |
| `vertical_9x16_safe` | 1080×1920 | 80, 160, 120, 420 | Same apps, kept clear of the buttons and the caption chrome |
| `portrait_4x5` | 1080×1350 | 60, 80, 60, 220 | Instagram and Facebook feed |
| `square_1x1` | 1080×1080 | 60, 80, 60, 160 | Square feed |
| `landscape_16x9` | 1920×1080 | 80, 60, 80, 140 | YouTube wide, LinkedIn, X |

```bash
gilvy render ep.yaml --format vertical_9x16 --format square_1x1
```

One profile writes `out/<name>.mp4`. Several write `out/<name>-<profile>.mp4`. QC runs on each file. Landscape is the vertical show fitted in the safe area, not a recomposed frame.

## Recipe

Do the steps in this order. Preview is cheap. A full render is the whole timeline at 60 fps.

1. **Choose audio mode and write the line first.** For `voiceover`, write one spoken sentence per scene; duration is `max(min, spoken seconds + 0.6)`. For `ambient` or `silent`, set explicit `min` reading durations; `vo` may be omitted and no TTS runs. Ambient/silent total duration is the sum of scene `min` values; lead, crossfade, and fades live inside that time, not in additional seconds.
2. **Compress each sentence into captions.** One or two lines. At most five words per line. Width under 780 px at Poppins 52 (the renderer refuses longer lines). Punctuation stays on the word: `lebih.` is one word, `lebih .` is two and will not match a key.
3. **Mark key words** by copying those words exactly, punctuation included. Keys are SemiBold white. They are not green.
4. **Pick one scene type** from `gilvy` / `list_scene_types`. One idea on screen.
5. **Set `min`** just above the spoken line so the drawing can finish and the next voice is not late. A `min` far above the real speech leaves a silence hole. QC fails internal gaps of 2 seconds or more.
6. **Preview.** `gilvy preview ep.yaml` (or `preview_frames`). Open `motion.png`: 12% is the entrance, 45% must still be mid-verb, 80% is the settled read and the color-rule point. `sNN.png` is that 80% frame.
7. **Watch the motion proof, then render.** `gilvy preview-motion ep.yaml --duration 7` (or `preview_motion`). Choose a start that includes the key transformation or a boundary. Render the full cut only after evaluating the motion. Default voice is edge-tts at `-8%`.
8. **QC.** `gilvy qc out/<name>.mp4` exits non-zero on a violation. `render` already runs it. Diagnose the violation and repeat from preview. Fix the episode or its custom scene; do not edit `draw.py`, easing, or the canvas to force a pass. Technical PASS does not replace creative review.

Offline narrated layout checks use `--tts fixture`. Fixture is a tone, not a voice. Publish narrated cuts with `--tts edge`; ambient/silent cuts use their explicit audio mode.

## Style

Read `docs/color-rule.md`. The rules that get videos rejected:

- **Green is one focus idea.** The money figure, or the counted unit and the counter that repeats that same quantity. Two different ideas never share green. On `examples/ep01-mie-ayam.yaml`, QC reads about 2%, 0%, 10%, 8%, 29%, 0% at the six scenes. That spread is the rule, not a target to beat.
- **White is structure.** Bowls, rings, tracks, dots that are not the count, labels, captions. Glow is white light, not a second green shape.
- **Setup and CTA may be entirely white.** A focus scene must actually show its green by 80% of the scene.
- **Caption baseline is y=1290**, second line y=1368. That sits below the usual Meta safe zone on purpose. Do not move it.
- **Focal point is (513, 780)**, not the geometric center. One or two objects. Stroke about 1.6, hairline 1.2, rings 2.
- **No title card, no face, no photos, no extra paragraph.** The caption is the hook.

Palette, if you must override it in YAML: background `(10,10,10)`, white `(236,236,236)`, green `(218,255,89)`.

## Writing

- Spoken line and caption say the same thing. The spoken line can be a little longer. Numbers in the voice are words (`dua ratus enam puluh delapan`), numbers on screen are digits (`268`).
- Hypothetical money wears a small note: `example` in English, `contoh` in Indonesian. Pass it as `note` on `bowl_hook`, or leave `ex` on in a custom scene.
- Indonesian episodes use `language: id-ID` and `voice: id-ID-ArdiNeural`. English uses `en-US-AndrewNeural`. Keep `rate: "-8%"`.
- Choose the narrative structure for the subject. The six-beat numerical explainer is one option; reflection, metaphor, and narrative may need a different progression.
- If a CTA serves the piece, use one ask. An open or reflective ending needs no marketing CTA.

## Long scenes stay in motion

A library verb runs until 65% of the scene, then holds. The entrance still finishes in about 0.6 seconds. `ring_drain`, `timeline`, and `coin_cta` already follow the scene length. The pose at 72% and at 80% is the finished pose, so the color rule is measured on the same picture as before.

When one scene is longer than 7 seconds, a small idle on the object that already landed starts only after that 65% mark. Compare dots, the highlighted bar, the jar levels, the converged ring, and the checklist each keep a local motion in that tail. The camera stays put.

Prefer two beats of the same object over one 20-second scene. A hold is a pulse, not a new idea. Chain the picture the way `examples/ep01-mie-ayam.yaml` does: the bowl stays, the coin falls into it, the count continues with `count_from`, the same dots become the comparison, the bowl returns for the ask. Do not score a long sentence as `checklist`, `highlight`, or `timeline` unless the sentence is actually a list, a set of bars, or a date.

## Scene choice

Use this only after the directing pass above. The first column is a verb, not a topic.

| Verb | type | Green |
|---|---|---|
| Object hook plus one price | `bowl_hook` | the price |
| One coin, a white explanation | `coin_drop` | none |
| A figure draining into a count of dots | `ring_drain` | the figure and its counter |
| Two quantities, one of them highlighted | `compare` | the highlighted count and its label |
| Bars, one of them brighter | `highlight` | none (brighter white, not green) |
| Bowl and a short ask | `bowl_cta` | none |
| A date on a line | `timeline` | none |
| A finished list | `checklist` | none |
| Jars filling | `jars` | none |
| Several icons becoming one | `converge` | none |
| A coin and more coins falling in | `coin_cta` | none |
| The verb you wrote is not in this table | `python` | you keep the rule yourself |

`ring_drain` and `compare` use a 22×26 dot grid (572 dots). Do not ask for more.

`python` points `entry` at `file.py:draw` next to the episode. The function is `draw(ctx, u, duration, params)` and uses `Ctx` primitives or the composed helpers in `gilvy.elements` (`line`, `circ`, `arc`, `poly`, `rect`, `dot`, `coin`, `text`, `money`, `label`, `glow`, `check`). `ctx.money` is green. Everything else stays on `ctx.theme.white` unless it is the same quantity.

## Commands

```bash
gilvy new ep02
gilvy preview ep02/ep02.yaml --tts fixture
gilvy render examples/ep01-mie-ayam.yaml
gilvy qc out/ep01-mie-ayam.mp4
gilvy mcp
```

ffmpeg must be on `PATH`. Poppins ships inside the package (OFL). Do not point fonts at a machine-local directory unless you are replacing the family on purpose.

## Agents

- **opencode.** `opencode.json` at the repo root starts `gilvy mcp`. Install the package in that environment first (`pip install -e .`). Tools: `directing_notes`, `list_scene_types`, `list_visual_elements`, `motion_reference`, `reference_styles`, `asset_manifest`, `preview_frames`, `preview_motion`, `compare_versions`, `render_video`, `qc_report`, `analyze_reference`, `download_reference`.

## Reference presets

For an editorial collage with PNG cutouts, paper, photos and movable data
pages, first read [the collage contract](../../src/gilvy/COLLAGE.md) / MCP
`collage_notes`. Plan object/action/carry and asset roles before generation;
keep narrative context out of each isolated asset prompt. Use
`composition: collage` with placement, independent tracks and attached
annotations. Inspect native pose pairs and a boundary-spanning motion proof;
a storyboard or a colour metric does not establish playback quality.

House episodes stay on the directing notes above. To match a Vox explainer or a sepia history short, use the opt-in path and do not zoom a house scene:

1. `gilvy download-reference <url> --out <new dir>` when the source is a link, then `gilvy analyze-reference <video> --out <new dir>`.
2. Read `soft_transitions` as dissolve candidates. Watch every clip. Pass `--boundaries` only after you agree the join is real.
3. Pick `style: vox-explainer` or `style: history-story`. The numbers, tags (measured, observed, inferred, uncertain), and gaps are in `gilvy reference-styles` / MCP `reference_styles`.
4. `gilvy assets episode.yaml --reference <video>`. The manifest carries the fixed prompt template (history-story: archival photo, sepia, grain, vignette, framing), an overscan pixel size, and style frames. `--frames N` sets the count. `--per-shot` compares each plate to that scene's own frame. Generate every missing PNG from that prompt. Run `assets` again; a colour, contrast, or brightness miss includes a regen hint. Do not commit reference frames.
For `composition: collage`, use each asset's own prompt and the separate scene brief; compare the rendered composition rather than histogram-matching each fragment to a complete reference frame.

5. Preview, watch a short motion proof, `gilvy render`, then `gilvy qc`. Legacy image plates must sit in the preset's shot-length and zoom band, and they must move. Zoom does not increase to make room for a pan. `history-story` has no intro fade, stacks emphasis words, allows a dissolve up to 2.0 s, and warns when a voice line is longer than its shot unless `vo_overrun: true`. A line that then overlaps the next voice is a warning too. Render writes `<name>.camera.json` (authored zoom and pan beside the values the camera applies). `gilvy compare` rescales different frame sizes and can cover the whole cut.

Samples: `examples/styles/vox-explainer.yaml`, `examples/styles/history-story.yaml`. Their plates are procedural stand-ins.
- **Claude Code.** `.mcp.json`:

```json
{ "mcpServers": { "gilvy": { "command": "gilvy", "args": ["mcp"] } } }
```

- **Cursor.** The same JSON in `.cursor/mcp.json`.

Call `list_scene_types` before inventing a type name. After `render_video`, read `ok` and `qc.violations`. A failed technical QC needs diagnosis: a second green idea, a caption that went green, a `min` that left a hole, or a focus that never appeared. Fix the episode or custom scene as appropriate and render again. A successful output is not automatically creatively approved.

Examples: `examples/ep01-mie-ayam.yaml` (Indonesian), `examples/day30-january.yaml` (English, no green), `examples/custom.yaml` (python escape hatch).
