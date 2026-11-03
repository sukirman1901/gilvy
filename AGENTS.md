# gilvy

Explicit SaaS/product motion uses the opt-in `style: product` compositor.
Read `src/gilvy/PRODUCT_MOTION.md` / MCP `product_motion_notes`; use
`preview-product` and `render-product`. House palette, fitted canvas, caption
baseline and stationary-camera rules below apply to the existing explainer
path. Product films have a separate native canvas and technical integrity QC.
Inspect a short encoded proof; effects alone do not establish reference fidelity.

Read `skills/gilvy/SKILL.md` and `src/gilvy/DIRECTING.md` before writing or rendering an episode. Direct the picture (object, verb, carry, meaning, consequence) before you pick a scene type. This file is the short version.

gilvy makes faceless 9:16 explainers. You write a YAML episode. The picture system (canvas, easing, glow, caption position, encode) is fixed so every video looks like the same show.

## Order

0. **Intake.** See `skills/gilvy/SKILL.md` → *Intake* and *Delivery profiles*. Default master is **1080×1920 (9:16)**. Reels, TikTok, and Shorts use that same file. Other aspects are derivatives until a format preset exists.
1. Choose `audio_mode`: `voiceover` (default), `ambient`, or `silent`. Write the line for each scene. Ambient/silent scenes require explicit `min` reading durations and do not call TTS.
2. Captions: 1–2 lines, ≤5 words, punctuation attached to the word. `key` copies those words exactly.
3. One scene type from `list_scene_types`. One idea. Green is one quantity or nothing.
4. `gilvy preview ep.yaml` and look at the contact sheet.
5. `gilvy preview ep.yaml` and read `motion.png` (12% entrance, 45% mid-verb, 80% settled).
6. Render and watch a 5–8 second `gilvy preview-motion ep.yaml` before the full cut. Review meaning, consequence, pace, and phone-size readability. When extending an approved cut, inspect `gilvy compare` evidence at matching resolutions. Then `gilvy render ep.yaml`. Repeat `--format` for another canvas. Default is `vertical_9x16`.
7. `gilvy qc` is technical only, not a creative-quality verdict. It must pass for the chosen audio mode. `render` runs it and exits non-zero when it does not.

Use `--tts fixture` only to check layout without the network. The voice you ship on a narrated cut is edge-tts (`--tts edge`, the default). Ambient/silent are legitimate explicitly selected deliverables.

## Do not

- Monkeypatch the voice, the paths, or the palette. They are fields on the episode.
- Paint a second idea green. Caption keys stay white. A word is green only when it starts with `$`, and that should be the same quantity as the one green figure.
- Move the caption up to chase a safe zone. The baseline is y=1290.
- Edit `src/gilvy/draw.py` or the scene formulas to fix one episode. Change the YAML, or add a `python` scene that uses the same primitives.
- Leave a long voice on a scene whose motion already finished. Past 7 seconds the landed object can idle, but a second beat of the same object is the better cut. Chain objects the way `examples/ep01-mie-ayam.yaml` does. Do not zoom the camera to fake motion.
- Put secrets, account ids, or personal data in an episode, a voice cache, or a commit.

## Tools

For a supplied reference, run `gilvy analyze-reference` / MCP `analyze_reference`
on a local video and follow `docs/reference-analysis.md`. Inspect all motion
clips before describing its style; a title or contact sheet is insufficient.
Separate observations from inferred camera/easing/layers. Reference study does
not apply the house palette or certify fidelity; name unsupported capabilities.

`gilvy render`, `gilvy preview`, `gilvy preview-motion`, `gilvy compare`, `gilvy qc`, `gilvy new`, `gilvy mcp`.

Visual components: `gilvy elements` / `list_visual_elements`. Read `gilvy motion-reference` / `motion_reference` for the API and approved Bojonegoro study. Components are used inside Python scenes; they are not new scene types.

MCP tools: `list_visual_elements`, `motion_reference`, `render_video`, `preview_frames`, `preview_motion`, `compare_versions`, `qc_report`, `directing_notes`, `list_scene_types`. Config samples live in `examples/mcp/` and `opencode.json`.

The color rule with the original measured ratios is `docs/color-rule.md`.
