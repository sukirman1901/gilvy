# Runnable examples and motion studies

These files are source examples, test inputs, and reproducible motion studies.
They are not imported by the installed renderer as a library. Tests, CI, and
authoring guides use the paths below; deleting them can break those workflows.
The Docker image also copies this directory for its example render job.

| Files | Purpose and repository consumer |
| --- | --- |
| `ep01-mie-ayam.yaml` | House directing example; README, directing guides, format/engine/hold tests, and the Docker CI render. |
| `day30-january.yaml` | English episode without green emphasis; README and episode/engine regression tests. |
| `custom.yaml`, `custom_scene.py` | Python scene entry point; README and CLI/engine tests. The YAML loads the Python file. |
| `reflection.yaml`, `reflection_scene.py` | Reflective object-to-object storytelling; README and the skill's creative review. The YAML loads the Python file. |
| `elements.yaml`, `elements_scene.py` | Animated visual vocabulary catalog; README, motion guide, and element preflight/render tests. |
| `elements-refined.yaml`, `elements_refined_scene.py` | Refined human, water, and fire motion diagnostic; motion guide and element regression tests. |
| `bojonegoro/episode.yaml`, `cerita.py`, `pekerja.py`, `SOURCES.md` | Dated Bojonegoro dot-motion study, its Python entry points, and data provenance; README, motion guide, and element tests. Recheck the dated data before reuse. |
| `mcp/*.json` | Claude, Cursor, and OpenCode connection configuration samples; README and AGENTS.md. |
| `styles/history-story.yaml`, `styles/vox-explainer.yaml` | Opt-in image-style examples; README, skill, consistency/style/round-2 tests, and CLI/MCP asset checks. |
| `styles/history/*.png`, `styles/vox/*.png`, `styles/make_plates.py` | Procedural assets used by those two YAMLs and their offline tests; the script rebuilds them. These are stand-ins, not source-reference artwork. |
| `styles/editorial-collage.yaml`, `styles/build_collage_demo.py` | Collage placement, shared clocks, and parent annotations; COLLAGE.md links the YAML and reproduction command. The builder creates assets in a new output directory. |
| `product/inbox.yaml` | Revised product UI example; README and product design/motion guides. |
| `product/learning.yaml` | Earlier twelve-second renderer diagnostic; product motion guide. It is not the approved UI design standard. |
| `product/composition.yaml` | Particle handoff, native clocks, and frame inspection diagnostic; README and composition runtime guide. |
| `product/study/build.py`, `README.md`, `measurements.json` | Scoped measured Numtera study and independent transfer exercise; product motion/primitives guides. The builder reads the measurement file. Source video and external fonts are not bundled. |
| `product/launch/build.py`, `README.md` | Reproducible 95-second product-film builder; product motion guide and shot-boundary regression tests. Generated output is written outside the source directory. |

## Retention

Keep a sample when a test, workflow, guide, or another retained sample consumes
it. Keep its local scene code, assets, measurements, and provenance together.
These are implementation references and diagnostics, not automatic approval of
visual quality or current factual claims.

One-off personal episodes without a repository consumer belong outside this
directory. Do not commit rendered MP4s, caches, downloaded references, or build
output here. Before removing a sample, search its paths and basename across
tests, `.github`, Dockerfile, guides, and other examples, then check local asset
and Python-entry dependencies.
