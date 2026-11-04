# gilvy

Minimalist motion graphics, a caption, and a voice-over. The look is locked (1080×1920, 60 fps, 2× supersampling, Poppins, one green idea per screen) so an agent can change the script without changing the picture.

Coding agents (opencode, Claude Code, Cursor) get a CLI and an MCP server. The production recipe is `skills/gilvy/SKILL.md`. Start with `AGENTS.md`.

![Six scenes from the Indonesian example](docs/ep01-sheet.png)

## Install

ffmpeg is the only system dependency. Python packages are pinned.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Poppins (SIL Open Font License) ships in `src/gilvy/fonts` with its `OFL.txt`. The rest of the project is MIT.

To fetch reference videos from supported sites or direct HTTP(S) media links,
install the optional extra in the same environment as Gilvy/MCP:

```bash
pip install -e '.[download]'
gilvy download-reference 'https://www.youtube.com/watch?v=awUYikrGsKk' --out out/reference-download
```

Use the returned `video` path with `gilvy analyze-reference` or MCP
`analyze_reference`. MCP acquisition is `download_reference`. This is not
YouTube-only or a universal web downloader: unsupported/auth-blocked pages can
fail. See [reference acquisition and analysis](docs/reference-analysis.md) for
limits, output provenance and the local-file fallback. Default installs and
the default Docker image do not include the optional downloader.

## Make a video

```bash
gilvy preview examples/ep01-mie-ayam.yaml --tts fixture
gilvy render examples/ep01-mie-ayam.yaml
gilvy qc out/ep01-mie-ayam.mp4
```

`--tts edge` (the default) calls edge-tts. `--tts fixture` is an offline tone so you can check layout without the network. Publish with the real voice.

| Command | What it does |
|---|---|
| `gilvy new ep02` | Scaffold `ep02/ep02.yaml` and a custom-scene stub |
| `gilvy preview ep.yaml` | One still per scene at 80%, plus a contact sheet |
| `gilvy render ep.yaml` | Render the selected voiceover, ambient, or silent mode. Then technical QC |
| `gilvy preview-motion ep.yaml --duration 7` | Watch a short timeline window, including scene boundaries |
| `gilvy compare approved.mp4 candidate.mp4` | Inspect paired frames and pixel differences; no automatic creative approval |
| `gilvy qc out.mp4` | Green ratio, silence gaps, blank and dark frames. Exit 1 on a violation |
| `gilvy mcp` | MCP server on stdio |

A scene is a type from the library (`bowl_hook`, `coin_drop`, `ring_drain`, `compare`, `highlight`, `bowl_cta`, `timeline`, `checklist`, `jars`, `converge`, `coin_cta`) or `python: file.py:draw` when the library cannot say it. Examples:

- `examples/ep01-mie-ayam.yaml` — Indonesian, `id-ID-ArdiNeural`
- `examples/day30-january.yaml` — English, no green
- `examples/custom.yaml` — the escape hatch
- `examples/reflection.yaml` — an offline caption-and-ambient metaphor, no numerical beat or CTA

Voice, language, output path, palette, and font directory are fields on the episode. Nothing is monkeypatched.

## Visual elements and approved motion study

Compose people, flames, smoke, drops, trees, sprouts, houses, buildings, pipes,
flow, sun, books, and roads inside Python scenes. These helpers use the existing
Ctx primitives and the locked style. Their local motion is deterministic at
absolute time, so frame order and worker count do not change the pose.

```bash
gilvy elements
gilvy motion-reference
gilvy preview examples/elements.yaml
gilvy preview-motion examples/elements.yaml --duration 7
```

The MCP exposes `list_visual_elements` and `motion_reference`. See the
[API and Bojonegoro motion study](src/gilvy/MOTION_REFERENCE.md) for usage,
meaning, and misuse notes. The 41-second approved data story is reproducible
from `examples/bojonegoro/episode.yaml`; read its dated sources before reuse.
More vocabulary should add meaning while preserving whitespace and one hero.

## Review motion before the full cut

Stills check layout; a short video checks rhythm. Name the object, action, carry,
meaning, and consequence before choosing a scene type. Watch a 5–8 second proof
before the full render. When continuing an approved cut, compare matching-size
clips and inspect intended changes such as the removal of a sample's outro.

```bash
gilvy preview-motion examples/reflection.yaml --duration 7.2 --out out/proof.mp4
gilvy render examples/reflection.yaml
gilvy compare out/proof.mp4 out/revised-proof.mp4 --duration 7.2
```

Set `audio_mode: voiceover` (default), `ambient`, or `silent` in YAML. Ambient
and silent scenes require explicit `min` reading durations, may omit `vo`, and
never call TTS. Voiceover mode still requires a spoken line on every scene.
There is no automatic switch of audio modes after a TTS error.

The MCP exposes `preview_motion` and `compare_versions` alongside the existing
tools. Motion previews keep the original scene clock and frame rate, then
optionally downscale the encoded picture. Their default fixture voice is a
layout tone and `timing_estimated` is true; narrated delivery uses real TTS.
Comparison produces sampled reference/candidate/difference images and raw pixel
measurements. Encoding noise is also a difference; these are not quality scores.
Preview sidecars record audio mode and frame dimensions for `gilvy qc` as well.
Without a sidecar, `gilvy qc clip.mp4 --audio-mode ambient` selects audio expectations explicitly.

`QC PASS` means technical checks passed for the selected audio mode. Results
explicitly report `scope: technical` and `creative_review: not_evaluated`.
Creative quality still requires watching and evaluating the piece. See
[creative-review.md](skills/gilvy/references/creative-review.md) for examples.

## Extract a motion reference

```bash
gilvy analyze-reference reference.mp4 --out out/reference-study
```

CLI `analyze-reference` / MCP `analyze_reference` produce provisional cut
boundaries, dissolve candidates (`soft_transitions`), timestamped frames,
paginated contact sheets, full-coverage motion clips with transition handles
and source audio, plus a JSON manifest and review worksheet. Manual boundaries
can override the heuristic. Dissolves are listed and do not become cuts until
you pass `--boundaries`. This studies local video; it does not download URLs,
understand a style automatically, or recover editable layers/keyframes. Watch
all clips and separate observation from inference before reconstructing. See
[reference analysis](docs/reference-analysis.md).

## Opt-in reference presets

`style: vox-explainer` and `style: history-story` are image-plate episodes.
House explainers stay on the still camera and the drawn scenes. The measured
ranges, what was only observed, and the gaps are in
[REFERENCE_STYLES.md](src/gilvy/REFERENCE_STYLES.md).

```bash
gilvy download-reference 'https://www.youtube.com/watch?v=...' --out out/reference-download
gilvy analyze-reference out/reference-download/<video> --out out/reference-study
gilvy reference-styles
gilvy assets examples/styles/history-story.yaml
gilvy render examples/styles/history-story.yaml --tts fixture
gilvy qc out/history-story-sample.mp4
```

`gilvy assets episode.yaml --reference video.mp4` lists every PNG, the fixed
prompt template, an overscan size so pan and zoom stay inside the picture, and
style frames from the video. When a PNG is already there it compares brightness,
contrast, and colour and adds a regen hint on a miss. Render fails if a path is
missing. Generate the art outside the repo. Do not commit frames from the
reference. Samples under `examples/styles/` use procedural stand-in plates.
MCP `asset_manifest` takes the same optional reference. `history-story` uses
pad/lead 0, a 0.15 s text fade, 216 px emphasis type, and a two-pole sepia
(`#261c15` to `#d3c0aa`). edge-tts is pinned to 7.3.1.

## Opt-in product motion

For SaaS/UI films use a separate `style: product` YAML, not a restyled explainer:

```bash
gilvy product-notes
gilvy preview-product examples/product/inbox.yaml --out out/product-stills
gilvy render-product examples/product/inbox.yaml --out out/product.mp4
```

The CPU compositor supports code-drawn inbox/form/workflow/dropdown UI, text
reveals, groups, gradient light fields, projected perspective planes, shadows,
layer blur and linear-light temporal supersampling. MCP exposes
`product_motion_notes`, `preview_product` and `render_product`. Local audio is
optional; silent is the default. See the [schema and limits](src/gilvy/PRODUCT_MOTION.md).
The existing explainer renderer and its style/QC are unchanged. Product renders
use decoded frame-count/dimension/duration/audio integrity checks, not house
green-ratio rules or a creative-quality score.

The revised [inbox visual system](docs/product-design.md) provides a coherent
four-column product screen with independently staged source and reply states,
measured text layout and explicit design tokens. The first learning proof is
a renderer diagnostic, not the standard for UI visual quality.

## Color

Green is one number: the money figure, or a count and the counter that repeats it. Rings, bowls, tracks, and captions stay white. Setup and the CTA may use no green at all. Measurements and the full rule are in `docs/color-rule.md`.

`gilvy qc` fails when a frame is too green, a focus scene never went green, a caption went green, the voice leaves a hole longer than two seconds, or a content frame has no drawing.

## Docker

```bash
docker build -t gilvy .
docker run --rm -v "$PWD:/work" -w /work gilvy render examples/ep01-mie-ayam.yaml --out out/ep01.mp4
docker run --rm -v "$PWD:/work" -w /work gilvy qc out/ep01.mp4
```

The image already contains the examples at `/opt/gilvy/examples`. CI renders `ep01-mie-ayam.yaml` there with `--tts fixture` and requires QC to pass. Fixture keeps the job deterministic; a published video uses edge-tts.

## Agents

`opencode.json` registers the MCP server as `gilvy mcp`. Claude Code and Cursor samples are in `examples/mcp/`. Install the package in the same environment the agent uses, then ask it to preview before it renders.

## Tests

```bash
pytest -q
```

Frame tests redraw the original episodes and compare bytes with the vendored renderer in `tests/fixtures`. A drift in easing, glow, captions, or a scene type fails that compare.

## Bahasa Indonesia

gilvy membuat video penjelasan 9:16 tanpa wajah: gambar gerak, teks, dan sulih suara. Naskahnya satu berkas YAML.

Contoh bahasa Indonesia: `examples/ep01-mie-ayam.yaml`, suara `id-ID-ArdiNeural`.

Urutannya: tulis voice-over dulu, pilih jenis adegan, `gilvy preview`, `gilvy render`, lalu `gilvy qc`. Hijau hanya untuk satu angka di layar. Caption tetap putih. Kalau QC gagal, perbaiki YAML-nya. Jangan mengubah mesin gambarnya.

```bash
gilvy render examples/ep01-mie-ayam.yaml
gilvy qc out/ep01-mie-ayam.mp4
```

## Composition and native frame inspection

Product compositions now support opt-in local timelines, persistent indexed
particles, measured row/column groups and explicit text wrap/fit. Existing
product films keep their global timing and legacy typography. The house show
keeps its established rendering and style.

```bash
gilvy serve-product examples/product/composition.yaml --port 8765
gilvy inspect-product examples/product/composition.yaml --frame 90 --out out/frame-90.png
gilvy render-product examples/product/composition.yaml --out out/composition.mp4
```

The local viewer seeks exact frames with the same native renderer as export;
it is silent and does not promise real-time playback. MCP adds
`inspect_product_frame`, `start_product_render`, `product_render_status` and
`cancel_product_render`. Jobs are process-local, not a persistent queue.
Read [the composition contract and limits](docs/composition-runtime.md).
