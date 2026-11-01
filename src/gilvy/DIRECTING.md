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

Use the primitives only: `line` (pass `p` to draw on), `circ` (`p` draws the ring), `arc`, `poly`, `rect`, `dot`, `coin`, `glow`, `text`, `money` (this one is green), `label`, `check`, `bar`, `fillrect`, `coins_flow`. Travel with `lerp` and `eio`. Fade in with `eo`. Time with `R(u, start, end)`.

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
