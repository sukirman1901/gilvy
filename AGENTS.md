# gilvy

Read `skills/gilvy/SKILL.md` before writing or rendering an episode. This file is the short version.

gilvy makes faceless 9:16 explainers. You write a YAML episode. The picture system (canvas, easing, glow, caption position, encode) is fixed so every video looks like the same show.

## Order

0. **Intake.** See `skills/gilvy/SKILL.md` → *Intake* and *Delivery profiles*. Default master is **1080×1920 (9:16)**. Reels, TikTok, and Shorts use that same file. Other aspects are derivatives until a format preset exists.
1. Spoken line for each scene.
2. Captions: 1–2 lines, ≤5 words, punctuation attached to the word. `key` copies those words exactly.
3. One scene type from `list_scene_types`. One idea. Green is one quantity or nothing.
4. `gilvy preview ep.yaml` and look at the contact sheet.
5. `gilvy render ep.yaml`
6. `gilvy qc` must pass. `render` runs it and exits non-zero when it does not.

Use `--tts fixture` only to check layout without the network. The voice you ship is edge-tts (`--tts edge`, the default).

## Do not

- Monkeypatch the voice, the paths, or the palette. They are fields on the episode.
- Paint a second idea green. Caption keys stay white. A word is green only when it starts with `$`, and that should be the same quantity as the one green figure.
- Move the caption up to chase a safe zone. The baseline is y=1290.
- Edit `src/gilvy/draw.py` or the scene formulas to fix one episode. Change the YAML, or add a `python` scene that uses the same primitives.
- Put secrets, account ids, or personal data in an episode, a voice cache, or a commit.

## Tools

`gilvy render`, `gilvy preview`, `gilvy qc`, `gilvy new`, `gilvy mcp`.

MCP tools: `render_video`, `preview_frames`, `qc_report`, `list_scene_types`. Config samples live in `examples/mcp/` and `opencode.json`.

The color rule with the original measured ratios is `docs/color-rule.md`.
