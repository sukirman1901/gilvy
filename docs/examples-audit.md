# Examples audit: function and visual suitability

Audit baseline: main `3a4efe5`, including the photographic remake of the salt
film. The earlier cleanup considered only incoming code/doc references. That
was insufficient: a file can be required by a test and still be a poor creative
reference. This revision audits both purpose and visual suitability.

## Evidence inspected

Generated and inspected 153 rendered frame samples across all 13 directly
runnable YAMLs available at the start of this review: three samples per scene
for episode films and five timeline samples per product YAML. These establish
visible composition, cropping, text competition, and state differences. They
do not establish normal-speed rhythm, soundtrack quality, or source-reference
fidelity. No new full-film approval is claimed.

The collage diagnostic was separately rendered and inspected as a four-second
mechanical proof during its implementation. It remains labelled as placeholder
art. The long launch builder and measured Numtera builder were audited as code
and dependencies; their full outputs were not replayed in this audit. Neither
is promoted to an approved reference. Connection JSON and asset/source files
were checked through their consumers and local paths.

## Decisions

| Material at the old path | Finding | Action |
| --- | --- | --- |
| `examples/bykirman/` | Photo-first montage: repeated full-frame crops, captions competing with keyword chips, repeated tags, and cork cards do not establish the requested editorial collage direction. Adding licensed photos/cutouts did not prove the choreography. No external tests or guides consume this personal film. | Delete the complete current package, including the newly merged YAML, photographs, cutouts, cards, and its now-unneeded credits. No orphan images remain. |
| `examples/product/learning.yaml` | Generic words-to-bar-to-panel capability demonstration; gradient field, preset panel, and cursor do not establish a coherent reference-matched SaaS film. | Delete. Remove guidance recommending it. |
| `examples/product/inbox.yaml` | Product task is represented, but sparse overview text and large moves of a preset workspace do not establish the requested SaaS visual standard. | Delete the film. Keep separately tested engine components documented as optional APIs, not a design master. |
| `examples/product/study/` | Scoped five-second reconstruction with substituted fonts, estimated/ambiguous geometry, and manual measurements; not a reusable full-film visual standard. No test consumes the builder or its measurement dataset. | Delete builder, dataset, and showcase README; retain accurate engine capability/limitation documentation. |
| `examples/product/launch/` | Unapproved fictional 95-second film. Length and a successful encode do not establish quality. Two existing tests execute its shot builder. | Delete showcase README; move only the executed builder into `tests/fixtures/product_launch/` with an explicit regression-only label. |
| `examples/styles/{vox-explainer,history-story}.yaml`, plates and generator | Clearly procedural stand-ins (block person, bars, silhouettes). They test rendering/QC but are visually far from photographic or editorial references. | Move to `tests/fixtures/episodes/styles/`, update tests, and stop presenting them as style exemplars. |
| `examples/elements*` | Catalog grids and isolated outline shapes demonstrate glyph behavior, not story composition or a creative master. Required by element tests. | Move into `tests/fixtures/episodes/`; keep the element API and label the catalogs technical. |
| `examples/{ep01-mie-ayam,day30-january}.yaml` | Historical house episodes underpin original-renderer byte comparisons and CI. They are not current-data publishing inputs or evidence for Vox/SaaS quality. | Move into `tests/fixtures/episodes/`; preserve all test assertions. Bundle only the CI smoke YAML in Docker. |
| `examples/bojonegoro/`, `examples/reflection*` | Earlier accepted house studies with a defined scope; not current Vox/SaaS masters. | Preserve under `references/house/` with source provenance and explicit scope. |
| `examples/product/composition.yaml`, collage diagnostic | Particle/local-clock and fragment/annotation API mechanics; intentionally placeholder art and no real data. | Retain under `examples/technical/`, labelled mechanics rather than creative direction. |
| `examples/custom*`, `examples/mcp/` | Minimal extension API and connection configurations. No claim of finished visual quality. | Retain and document their narrow purpose. |

## Guidance corrected

README quick start creates a new episode instead of promoting a historical
fixture as publishable content. Product notes no longer route new SaaS work to
learning/inbox/launch demos. The authoring skill and AGENTS.md distinguish
mechanical samples, test fixtures, earlier accepted house studies, and an
actual supplied reference. There is no bundled approved Vox or SaaS master.
Removed showcase commands and obsolete comparison-image links are not retained
as a current reproduction workflow.

## Limits

This cleanup removes misleading defaults and unrelated artwork; it does not
make the engine or agent automatically good at design. A new Vox/SaaS film
still needs an authored composition, appropriate assets, object choreography,
and actual encoded-reference comparison. A style name, orange label, shadow,
3D tilt, cutout, or passing QC is not sufficient evidence.
