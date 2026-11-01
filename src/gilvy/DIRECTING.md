# Direct the picture

You are the director of this episode. The scene library is a set of performances you already know how to stage. It is not a form to fill by matching keywords. A video feels like a slide deck when each sentence introduces a new chart. A video feels directed when one object stays in frame and each sentence is a verb that object performs.

Do this pass before you write YAML. Call `directing_notes` if you are on MCP, and do not call `list_scene_types` until the verbs exist.

## 1. Verb, then type

For every spoken line, write three words in your plan. They never appear on screen.

- **Object.** The noun in the frame. Prefer the object from the previous scene.
- **Verb.** What it does during this sentence: draws, falls, drains, counts, splits, travels, fills, checks, converges, returns. "Shows", "lists", and "explains" are not verbs. Rewrite the line until a physical verb exists.
- **Carry.** What is already on screen, and the one thing that changes.

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
- A scene longer than about 12 seconds has only one verb. Split it into two beats of the same object. The slow push that starts after 7 seconds keeps a settled frame from looking dead. It does not add a second idea.

When two chains are possible, keep the one where the object survives more cuts. Preview that one. Look at the contact sheet for layout, then ask whether the frame at 80% is mid-verb or already finished. If it is finished, lengthen the verb or split the line.

## 5. Then the usual production pass

Voice first, captions under five words, keys copied exactly, `min` just above the spoken line, preview, render, QC. Fix a failed QC in the episode. Do not restyle the canvas, the easing, or the caption baseline.
