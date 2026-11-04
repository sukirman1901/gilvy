---
name: gilvy
description: Use when creating, editing, previewing, reviewing or studying motion graphics with Gilvy, including explainers, kinetic typography, abstract brand motion, editorial collage and SaaS/product films.
---

# Gilvy

Choose the renderer by required capabilities, then choose a visual style. Technical QC is not creative approval.

## Route the brief

| Brief | Production path | Read next |
|---|---|---|
| Custom kinetic type, abstract/brand motion, UI or product film | General compositor; existing schema identifier `style: product` | [Compositor](references/compositor.md) |
| Established Gilvy explainer show | House episode renderer | [House](references/house.md); MCP `directing_notes` |
| Photographic Vox/history or editorial collage | Image episode renderer with explicit photo profile | [Image/reference work](references/image-reference.md); MCP `reference_styles`, and `collage_notes` for collage |
| Analyze an existing reference only | Acquisition/analysis, without authoring a film | [Image/reference work](references/image-reference.md) |

`product` is a schema name, not a restriction to SaaS. Do not invent `style: generic`. House palette, fitted canvas, fixed camera and caption rules apply only to house films. Read MCP `product_motion_notes` for the installed compositor's full schema; the bundled guide works when MCP is unavailable.

## Workflow

1. Establish delivery dimensions, duration, audience, audio mode and source material. Assume reasonable defaults when unspecified; do not add an approval checkpoint unless requested.
2. Check installed capabilities and [integration](references/integration.md). Never infer downloader/model readiness from a tool name. Use absolute input/output paths; examples are relative to this skill's directory, not shell cwd.
3. Direct each beat: object, physical verb, carry, meaning, consequence. For house, call `directing_notes` before `list_scene_types`. For custom composition, author primitives rather than forcing a UI template.
4. Validate inputs/assets. Design stills, then render a short encoded proof covering the hardest transformation and a boundary. Fixture TTS is layout-only estimated timing; narrated timing approval needs the actual voice.
5. Inspect motion at normal speed and native typography. Record the artifact, time range, weakest beat, changes and remaining gaps using [creative review](references/creative-review.md). If playback/audio inspection is unavailable, say so; do not claim viewing from screenshots or QC.
6. Revise, render, inspect technical QC for the selected renderer, then deliver. Preserve approved sources and compare revisions with aligned ranges. Failed QC means diagnose, not rewrite style rules to force a pass.

## Delivery contract

Return output paths, renderer/profile, dimensions/FPS/duration, audio source/mode, actual QC result, review evidence and unresolved limitations. Report job states truthfully. A queued job, successful tool call, synthetic fixture, or passing pixel test is not a finished creatively approved film.

## Starting point

[Bundled kinetic example](examples/kinetic.yaml) is a small executable syntax example, not an approved visual standard. Copy it into the project before editing. [Behavior scenarios](evals/cases.md) cover routing, missing capabilities and honest review.
