# Independent review follow-up

Date: 2026-11-05. Starting branch revision: `46506de`.
Scope: three independently reproduced engine issues in the integrated audit/collage changes, plus a read-only assessment of the detector fixture/QC interaction.

## 1. Product publication must not overwrite any input

The renderer previously compared the MP4 destination only to the spec and audio. It subsequently wrote `<stem>.product.json` without checking whether that path was itself the input spec, audio, image or custom font.

`_check_publication_inputs` now checks **both** actual publication destinations (MP4 and product sidecar) against:

- the spec source;
- declared audio;
- image sources at every nested group depth;
- custom font sources at every nested group depth.

Paths are resolved; existing-file identity is also checked so a hard-linked sidecar cannot truncate a differently named input. This runs before render-frame generation, temporary encoder workspace allocation and subprocess creation. The existing destination lock remains held. Product currently deletes no publication sidecars, so the checked set contains its two writes.

Five regressions construct valid inputs colliding with the product sidecar: spec, WAV audio, nested PNG image, custom TTF font, and a hard link to the spec. Each asserts `GilvyError`, forbids encoder startup and verifies all original bytes, including a prior approved MP4, remain intact.

## 2. Numeric effect errors are structured and field-specific

All 16 supported numeric effect parameters now use a common tagged numeric schema preserving their previous defaults and inclusive bounds. Validation rejects strings, explicit null, lists, mappings, booleans and nonfinite floats **before conversion**, raising `EpisodeError` with the exact path, such as `scenes[1].effects[1].amp`.

No blanket exception handling was added. The existing MCP `GilvyError` boundary returns `ok: false`, `code: invalid_input`, and the numeric field path. Three end-to-end MCP regressions specifically verify malformed shake amplitude never reaches preview/rendering. A 16-field × 7-invalid-value matrix verifies the same contract for amplitude, frequency, onset, duration, amount and rotation fields across all effect kinds.

The detector-owned `tests/test_effects.py` was read and two existing template-loading tests were run, but it was not edited. `detect.py` and `test_detector_regressions.py` were not edited or staged.

## 3. Unplaced layer tracks participate in source sizing

Unplaced cover-fitted layers now combine:

- the camera scale envelope with the layer's actual depth gain;
- the layer scale-track peak;
- depth-adjusted camera pan plus the absolute layer x/y envelope;
- a conservative diagonal canvas envelope when local rotation is present.

Track bounds include analytical cubic-bezier extrema and the entire authored track, including episode-clock keys. These are conservative source-generation bounds, not a claim that every key is visible in the current shot. Legacy unplaced local pans are currently measured by the renderer in **output pixels**; manifest sizing converts them back through the delivery fit rather than silently changing the rendering formula.

Regressions cover 1→4→1 scale and intermediate x/y peaks on both scene and episode clocks, combined depth/camera/local cubic-bezier overshoot, and local pan sizing in a nonidentity square delivery fit. Placed fragments and attached-card sizing retain their separate projection contracts.

## RED/GREEN evidence

Logs: `/Users/aaa/.local/share/gilvy-audit/`.

1. `review-followup-red.log`: **124 failed** before implementation. The first image/font product fixtures lacked mandatory layer dimensions; those fixture errors were corrected before production changes.
2. `review-followup-product-red.log`: **5 failed, 119 deselected**, now all for the intended missing publication guard: valid product inputs reached the forbidden encoder startup.
3. `review-followup-green.log`: **124 passed in 0.98s**.
4. `review-followup-focused.log`: **232 passed in 5.30s**, covering the new regressions, prior audit and integration regressions, upstream collage, real product encode/MCP/audio, product cancellation/jobs and existing effect-template loading.

Commands:

```sh
.venv/bin/pytest -q tests/test_review_followup.py

.venv/bin/pytest -q tests/test_review_followup.py tests/test_audit_hardening.py \
  tests/test_upstream_integration.py tests/test_collage.py \
  tests/test_product.py::test_real_encode_window_audio_cli_and_mcp \
  tests/test_composition.py::test_cancel_during_render_preserves_existing_video_and_cleans_encoder \
  tests/test_composition.py::test_job_queue_status_and_cancel_are_observable \
  tests/test_composition.py::test_mcp_job_reaches_completed_with_real_verified_video \
  tests/test_effects.py::test_articles_and_history_templates \
  tests/test_effects.py::test_inventory_pins_and_vox_template
```

No broad/full suite was run. No detector tolerances were changed.

## Detector zoom fixture assessment and actionable handoff

`test_zoom_rate_is_within_five_percent` authors scale 1→1.35 over 1.2 seconds. The endpoint-average **relative** zoom is `100*log(1.35)/1.2 = 25.008716%/s`, which is what its detector assertion measures. That is not its instantaneous peak **absolute frame-scale** speed. `presets.py` explicitly defines the plate speed bands in absolute percent of frame scale per second; the history short-shot ceiling is 40%/s.

Direct evaluation of the current camera metrics and analytic derivatives gives:

| Ease | Sampled peak (%/s) | Analytic peak (%/s) | Expected peak-QC result |
|---|---:|---:|---|
| linear | 29.1667 | 29.1667 | pass |
| easeInCubic | 87.1586 | 87.5 | reject |
| expoIn | 199.4555 | 202.1679 | reject |
| expoOut | 199.4555 | 202.1679 | reject |

These results support the intended peak-QC contract. Numerical peaks are explicitly labeled 256-subdivision estimates; their small underestimates do not cause the fixture failures. The authored nonlinear peak speeds genuinely exceed the limit by large margins. No QC-source repair or relaxation is warranted for these failures.

**Recommendation to the detector owner/controller:** retain these useful out-of-band detector stress fixtures, use `Path(result['video'])` (the retained candidate when rejected), and explicitly assert the expected peak-segment violation / `published: false` for the three nonlinear cases. Keep the linear case QC-passing and published. Keep the existing 5% detector tolerance and the same authored/easing assertions. Do not read the requested final destination after QC rejection or claim the rejected candidate is a publishable film.

This report does not claim the detector owner's independently measured rates or periodic-alignment work as engine test results; the numerical table above comes directly from the current camera metric function and analytic derivatives. The detector test remains under its owner's control.

## Commit boundary and limitations

Only `src/gilvy/product_render.py`, `src/gilvy/effects.py`, `src/gilvy/assets.py`, `tests/test_review_followup.py`, and this report belong to this follow-up commit. Other working-tree edits are preserved.

Checks protect declared inputs at preflight time; they are not a filesystem sandbox against an external process swapping files after validation. Product retains its existing post-video metadata-warning behavior. Source-sizing envelopes may over-request resolution when extreme keys occur outside the current shot; their purpose is to avoid under-sizing, not to infer creative intent.
