# Established house explainer

Read installed MCP `directing_notes` (CLI `gilvy` notes are available through MCP) before selecting scenes. This guide is an offline authoring summary, not a claim that every house API is listed.

Default master: 1080x1920, 60 fps, Poppins, near-black background, white structure/captions, one green quantity. Keep the camera still. Other delivery formats fit that design; they do not automatically recompose it. Custom generic motion belongs to the [compositor](compositor.md).

Plan object, physical verb, carry, meaning and consequence for every beat. Keep objects through cuts. A scene type is a performance: bowl_hook introduces bowl/price, coin_drop drops a coin, ring_drain counts, compare compares established counts. Checklist/highlight/timeline/jars are only appropriate when the actual verb requires them. Use `list_scene_types` for required parameters; use `python` scenes with Ctx primitives for other verbs, not engine monkeypatches.

Episode fields include name, audio_mode, language, voice, rate, format and scenes. Scene fields include type, caption (one/two lines, <=5 words per line), key (exact caption words), vo and min. `python` uses `entry: file.py:draw`, with `draw(ctx,u,duration,params)` and paths relative to episode YAML.

Voiceover requires vo on every scene. Indonesian defaults: language id-ID, voice id-ID-ArdiNeural, rate '-8%'. English voice en-US-AndrewNeural. Ambient/silent require explicit positive min durations and do not call TTS. Narrated final delivery needs real voice; fixture is a diagnostic tone.

Primary action, smaller delayed secondary action and restrained ambient support should express meaning, not add decoration. Caption baseline remains y=1290; focus near (513,780). Keys stay white. Green represents one quantity, not two unrelated ideas. Dot grid holds at most 572.

MCP preview_frames produces 12%,45%,80% stills and motion sheet. preview_motion produces a bounded clip; review motion and audio before render_video. Read returned QC violations and publishable_audio. Run renderer-appropriate QC; passing technical checks never certifies metaphor, rhythm or originality.
