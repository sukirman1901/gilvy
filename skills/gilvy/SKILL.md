---
name: gilvy
description: Produce a faceless 9:16 explainer with gilvy. Use when asked to make, edit, preview, render, or QC a gilvy episode, a motion-graphic short, or a YAML scene list for opencode, Claude Code, or Cursor.
---

# gilvy

gilvy renders a vertical explainer from a YAML episode. The picture is already decided: 1080×1920, 60 fps, Poppins, near-black background, white structure, one green quantity. An agent writes the episode. It does not restyle the renderer.

## Recipe

Do the steps in this order. Preview is cheap. A full render is the whole timeline at 60 fps.

1. **Write the voice-over first.** One spoken sentence per scene. Read it aloud. The scene will last `max(min, spoken seconds + 0.6)`.
2. **Compress each sentence into captions.** One or two lines. At most five words per line. Width under 780 px at Poppins 52 (the renderer refuses longer lines). Punctuation stays on the word: `lebih.` is one word, `lebih .` is two and will not match a key.
3. **Mark key words** by copying those words exactly, punctuation included. Keys are SemiBold white. They are not green.
4. **Pick one scene type** from `gilvy` / `list_scene_types`. One idea on screen.
5. **Set `min`** just above the spoken line so the drawing can finish and the next voice is not late. A `min` far above the real speech leaves a silence hole. QC fails internal gaps of 2 seconds or more.
6. **Preview.** `gilvy preview ep.yaml` (or `preview_frames`). Open the contact sheet. Stills are at 80% of each scene, which is the color-rule measurement point.
7. **Render.** `gilvy render ep.yaml` (or `render_video`). Default voice is edge-tts at `-8%`.
8. **QC.** `gilvy qc out/<name>.mp4` exits non-zero on a violation. `render` already runs it. Fix the YAML and repeat from preview. Do not edit `draw.py`, easing, or the canvas to force a scene to pass.

Offline layout checks use `--tts fixture`. Fixture is a tone, not a voice. Publish with `--tts edge`.

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
- A six-beat short is enough: hook, setup, one number, the comparison or second number, the punchline, the CTA.
- Ask for one comment, one number, or one follow. Do not stack three asks.

## Scene choice

| You need | type | Green |
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
| Something the list cannot draw | `python` | you keep the rule yourself |

`ring_drain` and `compare` use a 22×26 dot grid (572 dots). Do not ask for more.

`python` points `entry` at `file.py:draw` next to the episode. The function is `draw(ctx, u, duration, params)` and may only use `Ctx` primitives (`line`, `circ`, `arc`, `poly`, `rect`, `dot`, `coin`, `text`, `money`, `label`, `glow`, `check`). `ctx.money` is green. Everything else stays on `ctx.theme.white` unless it is the same quantity.

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

- **opencode.** `opencode.json` at the repo root starts `gilvy mcp`. Install the package in that environment first (`pip install -e .`). Tools: `list_scene_types`, `preview_frames`, `render_video`, `qc_report`.
- **Claude Code.** `.mcp.json`:

```json
{ "mcpServers": { "gilvy": { "command": "gilvy", "args": ["mcp"] } } }
```

- **Cursor.** The same JSON in `.cursor/mcp.json`.

Call `list_scene_types` before inventing a type name. After `render_video`, read `ok` and `qc.violations`. A failed QC is a script problem: a second green idea, a caption that went green, a `min` that left a hole, or a focus that never appeared. Change the episode and render again.

Examples: `examples/ep01-mie-ayam.yaml` (Indonesian), `examples/day30-january.yaml` (English, no green), `examples/custom.yaml` (python escape hatch).
