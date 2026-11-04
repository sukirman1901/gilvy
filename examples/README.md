# API examples, not a visual gallery

This directory demonstrates configuration and renderer mechanics. None of these
files is a finished creative standard or a Vox/SaaS reference reconstruction.

| Files | What they demonstrate |
| --- | --- |
| `custom.yaml`, `custom_scene.py` | Minimal Python scene entry point. Used by CLI/engine tests. The circle and price are API placeholders. |
| `mcp/claude.mcp.json`, `mcp/cursor.mcp.json`, `mcp/opencode.json` | MCP connection configuration. No visual output. |
| `technical/composition.yaml` | Indexed particles and local clocks. A geometry diagnostic, not real data or a narrative model. |
| `technical/editorial-collage.yaml`, `technical/build_collage_demo.py` | Placement, shared clocks, matte borders, and parent annotations. The builder makes placeholder assets in a new directory. |

Earlier accepted house studies are preserved in
[references/house](../references/house/README.md). Legacy plates, glyph catalogs,
and episodes used by regression tests are in `tests/fixtures/`; they must not
be used as creative references. The personal salt film and generic SaaS demo
films have been removed rather than endorsed because they rendered.

Read [the complete audit](../docs/examples-audit.md) for findings and decisions.
New examples must have one explicit API purpose and a runnable command. Put
regression-only data in test fixtures; keep personal content, downloaded art,
rendered videos, caches, and unapproved showcase films out of this directory.
