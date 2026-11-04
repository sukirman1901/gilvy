# Engine audit fixes: F1–F9

Work date: 2026-11-04/05. Branch: `fix/audit-hardening`.
Starting engine revision: `7d5c4c2`. No commit, push, merge, or rebase performed by this worker.

## Scope and handoff

Implemented the nine engine findings in `/Users/aaa/.local/share/gilvy-audit/REPORT.md`, with regressions in `tests/test_audit_hardening.py`. Production changes are limited to `assets.py`, `episode.py`, `errors.py`, `image_scene.py`, `keyframes.py`, `mcp_server.py`, `presets.py`, `qc.py`, `render.py`, `tts.py`, and `voxlook.py`. The existing synthetic-house QC test in `tests/test_qc.py` now explicitly requests voiceover checks; its original assertions remain intact.

Concurrent skill/package changes and `tests/test_cli.py` changes visible in the shared working tree belong to other workers; this worker did not edit them. Preserve them.

**Upstream integration is still pending.** The controller reported `origin/main` advancing to `ad76ea9` with editorial collage/shared-clock changes. These fixes deliberately remain based on the pre-merge engine. After merging, integrate the new collage dependencies and clocks into the collector/timing paths; preserve upstream absolute episode time for negative dissolve handles. The upstream duplicate/offset shared SFX and attached-annotation alpha-compositing findings were explicitly deferred to the controller and are not claimed fixed here.

## Fixes and evidence

### F1 — Safe house publication

- Each invocation receives a unique sibling workspace. Encoding, muxing, contact-sheet/poster generation, timeline/camera metadata, and QC operate on that candidate.
- QC rejection returns `published: false`, `requested_output`, and paths to the retained rejected candidate for diagnosis. Existing final output and sidecars remain intact.
- Success publishes metadata/poster and finally the MP4 under a destination-specific nonblocking advisory lock. Same-destination house writers are rejected across processes.
- Before replacing any file, publication stages backups. Ordinary replacement failures roll back files already replaced. Old product/preview sidecars and an obsolete poster are removed as part of the same rollback-capable operation, preventing stale QC routing.
- `RenderControl` cancellation is checked before work, after mux, and before publication; publication serializes against cancellation. Input/output aliases are rejected using the dependency inventory.
- Fault-injection regressions cover encode, mux, contact sheet, poster, timeline, QC exceptions, explicit QC rejection, publication replacement failure, cancellation, lock contention, success paths, stale metadata, and input alias rejection.
- A real FFmpeg regression recreates the audit publication probe: an approved product MP4 and sidecar retain identical SHA-256 hashes after a house candidate fails green-focus QC. The rejected candidate remains available at its returned path.

### F2 — Full camera-path metrics and actual shot timing

- Metrics retain legacy signed net zoom/pan rates for compatibility and add scale/x/y/rotation travel, peak push/pull/zoom/pan speeds, and an explicit measurement-method label.
- Segment-local samples include every in-window key and cubic-bezier extrema. Round trips and delayed motion are no longer classified from endpoint displacement alone.
- Parser validation uses the authored shot minimum, or the authored track span when no minimum is present. `build_state` validates motion again against the actual render duration.
- Explicit camera-track conformance uses segment peak speeds rather than allowing a short fast punch to disappear into its shot-wide average. Shorthand camera band semantics remain unchanged.
- Camera sidecars now report actual track endpoints and full-path travel/peaks, rather than misleading `from`/`to` fallback values when explicit tracks override them.
- Regressions cover round trips, delayed starts, a short over-speed segment, a track that becomes static under a shorter actual duration, and sidecar endpoint/travel correctness.

### F3 — Shared visual/audio overlay timing

- SFX scheduling now calls the same `overlay_start` resolver used by visual rendering, with the same scene duration, narration, style and explicit-`at` precedence.
- Timeline sidecars expose overlay events, their scene-local onset, SFX name, and `keyword_estimate` versus `explicit` timing provenance.
- Regressions cover keyword timing and explicit `at` overriding a keyword. This is an estimated narration-word clock, not forced alignment to measured speech boundaries.

### F4 — Dependency manifest and early card validation

- A common `collect_dependencies` inventory supplies manifest/preflight/publication input checks. It covers image layers, card sources, declared audio, custom Python entry files, the episode source and known fonts.
- Card entries include scene identity and precise `overlays[i].src` location; missing and invalid images are reported separately.
- Preflight performs image verification **and pixel decoding**. JPEG `verify()` alone did not catch a truncated body; a new RED regression proved timing/TTS was reached, and the fix now rejects the card first.
- Known fonts are checked for readability before timing. Missing custom entry files are caught for house episodes too.
- Regressions cover missing cards, corrupt cards, truncated JPEGs, exact manifest location, and custom-code/audio/font dependency inventory.

### F5 — Artifact-aware standalone QC

- A `.product.json` sidecar routes standalone QC to product technical integrity checks. Cached QC verdicts are not trusted.
- The recheck counts decoded frames and checks dimensions, duration, frame rate, metadata frame clock, stream presence and ffprobe decode diagnostics. It does not impose house green/blank/speech rules.
- With no timeline/preview/product metadata and no explicit audio mode, QC returns `ok: false`, `status: needs_context`, and `audio_mode: unknown`, rather than silently assuming house voiceover.
- Explicit house `audio_mode` remains available for synthetic or externally produced house artifacts. The existing house QC fixture was adapted to pass that context without weakening its green/blank/silence assertions.
- Real-encode regressions verify a green silent product passes standalone QC, altered frame-count metadata fails, and removed metadata requires context.

### F6 — Structured input errors

- `GilvyError` carries `code` and optional `field`; `EpisodeError` uses `invalid_input`. MCP error envelopes retain the existing string `error` and add `code`, `field`, and a remediation suggestion.
- Missing highlighter/circle fields and malformed arrow points now fail validation instead of leaking `KeyError`/`IndexError`.
- Overlay errors carry scene/overlay location; numeric missing-field errors include the exact leaf, e.g. `scenes[0].overlays[0].x`.
- Wrong-type tagged fields, invalid camera/transition numbers, nonfinite pan key values and malformed bezier coordinates are rejected before rendering. Bezier x coordinates must be within `[0,1]` while finite y overshoot remains supported.
- Main house render/preview and QC MCP boundaries normalize expected OS/subprocess failures. Programming exceptions are not indiscriminately swallowed.
- Regressions cover missing fields, wrong types, nonfinite values, invalid YAML and expected IO failures; corrupt-image preflight is covered under F4.

### F7 — Transform-aware asset envelope

- Plate sizing now evaluates the full camera path, including intermediate scale/pan extrema and cubic-bezier overshoot, rather than only `from`/`to`.
- Rotation uses a conservative diagonal envelope to cover bounding-box maxima between samples.
- Fixed-duration shots use their authored duration. Before voice synthesis, a stretchable VO shot conservatively includes its full authored track span, because its minimum is not its final duration.
- Regressions cover scale 2.4 / pan 400 intermediate peaks, bezier overshoot with rotation, and a track extending past a VO minimum.

### F8 — Percent-only speech rate and selective retries

- Episode and EdgeTTS validation accept signed percentage rates, not Hz. EdgeTTS validates rate before allocating output/retrying.
- Constructor `ValueError`/`TypeError` becomes a structured parameter failure immediately. Retries are limited to aiohttp network errors, timeouts and EdgeTTS no-audio responses.
- Regressions prove `+0Hz` fails preflight and an invalid constructor parameter is attempted once, not five times. No live TTS service was contacted.

### F9 — Signed tilt

- Positive tilt foreshortens the top edge; negative tilt foreshortens the bottom. Zero retains the unwarped image.
- Pixel/alpha geometry regressions prove the two signs differ and narrow opposite edges. Locked house drawing formulas were not edited.

## TDD and commands

Logs are retained outside the repository at `/Users/aaa/.local/share/gilvy-audit/`.

Initial RED: `fixes-red.log` recorded 21 failures / 3 passes. One product fixture initially had no layers and therefore failed for an invalid fixture; this was corrected before production changes, and `fixes-red-product.log` then demonstrated the actual product-QC mismatch. Three already-passing cases were explicit timing precedence and pre-mux publication failures, retained as compatibility guards.

Initial GREEN: `fixes-green-initial.log` — **24 passed**.

Additional RED/GREEN cycles:

- `fixes-red-adjacent.log`: 7 failures / 30 passes; separate direct RED run additionally demonstrated nonfinite x keyframes being accepted when accompanied by scale motion. `fixes-green-adjacent.log`: **37 passed**.
- `fixes-red-contracts.log`: 6 failures / 1 pass / 37 deselected. `fixes-green-contracts.log`: **44 passed**.
- `fixes-red-tagged.log`: 5 failures / 5 passes / 44 deselected.
- `fixes-red-camera-metadata.log`: actual explicit-track start 1.2 was incorrectly reported as 1.0.
- `fixes-red-vo-envelope.log`: manifest scale 1.7 omitted the authored 2.4 peak past the VO minimum. A preliminary fixture used `src` instead of `image`; the fixture was corrected and the intended 1.7-vs-2.4 RED was observed before production changes.
- `fixes-red-truncated-card.log`: corrupt JPEG reached `prepare_timing`, proving header-only verification insufficient.

Final focused command:

```sh
.venv/bin/pytest -q tests/test_audit_hardening.py tests/test_episode.py \
  tests/test_qc.py tests/test_engine.py tests/test_voxlook.py
```

Result: **75 passed, 1 skipped in 17.10s**, exit 0 (`fixes-focused-final.log`). This includes all 58 audit regression cases and the real FFmpeg preservation/product-QC tests.

Compatibility command earlier in the task:

```sh
.venv/bin/pytest -q tests/test_episode.py tests/test_styles.py tests/test_voxlook.py \
  tests/test_qc.py tests/test_motion_review.py tests/test_round4.py
```

Result: 34 passed / 1 skipped / 1 failed in 196.51s. The sole failure was the intentionally changed missing-context QC contract in `test_qc_pass_blank_green_and_silence`; that fixture now explicitly selects house voiceover checks and passes in the final focused run. Log: `fixes-compatibility.log`.

Final image-style/motion compatibility command:

```sh
.venv/bin/pytest -q tests/test_styles.py tests/test_motion_review.py tests/test_consistency.py
```

Result: **29 passed in 27.09s**, exit 0 (`fixes-compatibility-final.log`).

`git diff --check` passed. No full suite was started by this worker; the controller owns that run after integration.

## Baseline distinction and caveats

- Controller's original full suite: **3 failed, 246 passed, 2 skipped, 607.8s**. The failures were the two signed small-zoom measurement cases and the typewriter word-time measurement case in `tests/test_effects.py`. This worker neither edited those tests nor pursued their measurement implementation. The Pillow `mode` deprecation in `product_primitives.py` was also left to the controller.
- Publication is rollback-capable for ordinary exceptions, but multiple filesystem directory entries cannot be power-loss/SIGKILL-atomic. The MP4 replacement is the final commit step; unlocked readers may briefly observe sidecar transitions. The advisory lock is Unix `fcntl` and currently coordinates house writers; product rendering has its own existing lifecycle. Cross-renderer simultaneous writes are not newly unified here.
- House cancellation checks prevent publication after cancellation; they do not interrupt every encoded frame immediately. Successful and QC-rejected workspaces are retained for their sheet/candidate evidence, so callers should apply their normal artifact retention policy. TTS now runs in per-invocation workspaces rather than reusing a destination's old cache.
- Camera peaks are explicitly labeled numerical segment-local derivative estimates (256 subdivisions), not analytic derivative guarantees. Exact cubic-bezier extrema are included for sizing; rotation sizing is conservative and may request larger plates than strictly necessary.
- Arbitrary dynamic assets imported/opened inside a custom Python scene cannot be inferred by the static dependency collector. Declared entry files and standard fonts are covered; this is not a sandbox or hermetic input snapshot.
- Keyword timing remains an estimate. Neither live neural TTS nor perceptual/creative-quality review is claimed by these tests.
- Expected malformed input paths covered by these regressions are normalized; this is not a claim that every possible malformed shape across every tool has been exhaustively fuzzed.
- Reconcile all overlapping upstream collage changes during merge, then run the full suite. In particular, do not overwrite upstream episode-clock handling with this pre-collage scene-clock implementation.
