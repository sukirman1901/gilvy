# Detector fixes — 2026-11-05

## Scope and diagnosis

Only `src/gilvy/detect.py`, `tests/test_effects.py`, this document, and new
`tests/test_detector_regressions.py` were edited. No staging or commits.

Reproduced the three reported failures before editing production code:

- Tiny push: 1.776 %/s versus 1.650218941, existing 5% tolerance.
- Tiny pull: -1.807 %/s versus -1.683558943, existing 5% tolerance.
- Typewriter: only two arrival times; indexing the third failed.

The resize matcher rounded image dimensions, cropped with integer offsets,
and quantized luma to uint8. Nearby scale candidates therefore shared samples
and alternated center offsets. An independent analytic-image regression
measured 0.567 mean pixel error at scale 1.002 before the fix. A read-only
experiment substituting `measure._numpy_scale` on encoded baseline clips gave
1.719 and -1.693 %/s. This supports fixing sampling, rather than forcing the
rate estimator to use endpoints. `_zoom_rate` is unchanged.

Noise controls also exposed phase-whitening shifts that lowered correlation
for nearly identical smooth images. Translation now compares whitened phase,
bounded unwhitened correlation, and zero-shift candidates by overlap NCC.
See the follow-up evidence below: zero translation alone was insufficient.

Decoded typewriter evidence (96px analysis width, 20fps):

| Frame | Net white pixels | Newly white | Persist through next 2 frames | Persistent bbox (x0,y0,x1,y1) |
|---|---:|---:|---:|---|
| 2 | 265 | 265 | 265 | 33,76,77,91 |
| 8 | 245 | 473 | 472 | 25,66,78,101 |
| 12 | 161 | 563 | 561 | 19,59,78,109 |

The third arrival's net growth is below the old 168.75 threshold, despite
substantial persistent new ink. The detector now uses localized persistent
additions with abrupt luma change, retaining a positive net-growth floor.
The synthetic layout-shrink regression independently reproduces this failure.

## RED / GREEN

Baseline command:

```sh
.venv/bin/python -m pytest tests/test_effects.py -k 'small_zoom or typewriter_word_times' -q
```

RED: **3 failed, 26 deselected**, 38.94s.

New regression file before production edits: **6 failed, 4 passed**, 0.41s.
Failures: subpixel image accuracy, signed noisy analytic zooms, layout shrink,
flash rejection, and fade rejection. Additional controls cover persistent
scattered noise and full-frame brightening. Existing numeric assertions and
tolerances remain unchanged; the encoded word test additionally requires
exactly three arrivals.

Initial focused command (before the translation repair below):

```sh
.venv/bin/python -m pytest tests/test_detector_regressions.py tests/test_effects.py \
  -k 'detector_regressions or small_zoom or typewriter_word_times or shake_does_not_inflate' \
  -q --basetemp=/private/var/folders/9k/zgmpxlms40529k533yssmfsh0000gn/T/opencode/detector-verification
```

Result: **16 passed, 25 deselected, 2 xfailed**, 80.12s. This includes all three
original failures and the existing shake/zoom interaction assertion.

## Follow-up: repair smooth periodic texture with pan

The initial xfails were not accepted as a completion boundary. Removed the
markers and reran `pytest tests/test_detector_regressions.py -k translation -q`:
**2 failed, 1 passed, 11 deselected**. The same 0.001 scale tolerance remains.

Root cause: at true scale 0.98 the whitened/windowed FFT suggested (0,0)
translation and NCC was only 0.801939. The unwhitened approach in
`measure._corr_shift` suggested (2.806185,-1.990652), close to the actual
inverse translation after scaling. At 1.02 phase suggested (-2,0), missing
vertical pan; unwhitened correlation suggested (-2.999983,1.999876).
This is a failed translation proposal, not intrinsic scale ambiguity.

The fix adds the bounded unwhitened peak (same 12px bound as `measure`) as
a translation candidate, retaining the phase and zero-shift candidates.
Actual overlap NCC chooses among them. The mean-subtracted raw FFT is not
windowed or whitened. Integer translation is retained; subpixel translation
is not claimed. This avoids importing `measure` back into `detect` (the former
already imports the latter).

Both original pan regressions now pass with no xfail:

| True scale | Estimated | NCC at true scale | NCC at reciprocal |
|---|---:|---:|---:|
| 0.98 | 0.980152622 | 0.999921739 | 0.973404765 |
| 1.02 | 1.019982916 | 0.999997437 | 0.975520313 |

Initial post-repair file check: **14 passed**, 0.95s. Added six further
analytic controls: scales 0.98/1/1.02, translations (-3,2)/(4,-2), and seeded
0.2-standard-deviation luma noise. These evaluate the continuous field at
translated coordinates, with no wrapped border or detector resampler used
to generate expected images. Signed cases require the true-scale NCC to beat
the reciprocal by >0.01, explicitly establishing identifiable test evidence.

For contrast, an affine brightness ramp (`40 + .5*x + .3*y`) gives NCC
approximately 1 at scales 0.98, 1, and 1.02. Normalization removes its gain and
offset differences; it cannot identify scale from this objective. This is
an actual identifiability limit, unlike the repaired sinusoid-plus-localized-
feature cases. No universal scale accuracy or confidence/abstention API is
claimed.

## Exact limitations and integration checks

- Unwhitened translation proposals are bounded to 12 analysis pixels;
  phase proposals still use the existing 40%-of-frame bound. Large pans,
  subpixel pan accuracy, featureless signals, and repeated-texture aliasing
  are not established by these regressions.
- Before the reviewed fixture update, a broader targeted run returned
  **15 passed, 3 failed, 21 deselected**:
  `test_zoom_rate_is_within_five_percent` for easeInCubic/expoIn/expoOut fails
  at `result['qc']['ok']`, before detection. Current QC rejects peak segment
  zoom 87.16 / 199.46 / 199.46 %/s against the plate band. No QC/renderer
  source was changed here. Direct inspection of retained encoded candidates
  gave rates 24.973 / 24.952 / 24.813 %/s, correct ease names, within 5% of
  authored 25.0087 %/s. The later reviewed fixture update is recorded below.
- The initial full-file attempt exceeded 240s and yielded no complete result.
  The timeout-free background follow-up completed: **45 passed, 4 failed**,
  533.36s (three expected-QC fixture mismatches and the error-message mismatch
  below). No repository-wide suite or performance benchmark ran.
- Word arrival remains a white-ink heuristic, not OCR. It needs two future
  frames, misses arrivals in the final two frames, requires net growth >20,
  and rejects additions spanning more than 35% of the frame. Persistent
  compact bright graphics can resemble text. Colored text and gradual
  entrances are outside this detector's tested coverage.
- Verification occurred in a shared working tree while another agent owns
  integration/merge work. No renderer/QC/other-source changes were made here.

## Reviewed fixture integration and final GREEN

Engine handoff `bef9051`, documented in
`docs/plans/2026-11-05-review-followup.md`, verified that the nonlinear stress
fixtures genuinely exceed peak-speed limits. Checked the renderer return
contract: rejected video candidates remain available at `result['video']`.

Updated only `test_zoom_rate_is_within_five_percent`:

- Linear still requires QC success, publication, and the requested destination.
- The three nonlinear cases require QC rejection, `published is False`, and
  exactly one violation specifically describing peak segment zoom exceeding
  the plate band. They also require no requested final output to be published.
- Every case asserts that `result['video']` exists and detects that artifact.
  All original 5% rate tolerances and easing assertions remain intact.

The completed full-file run then reported **48 passed, 1 failed**, 546.12s.
The remaining failure was `test_eased_dissolve_may_last_four_seconds`: the
parser correctly rejects 4.1 but formats its upper bound as `4`, while the
old message regex expected `4.0`. Updated that test to accept either numeric
spelling, additionally require the structured `transition` error field, and
explicitly verify that exactly 4.0 is accepted. This preserves and strengthens
the numeric boundary rather than relaxing it. Focused check: **1 passed**, 0.55s.

Final completed command (foreground timeout 1,200,000ms):

```sh
.venv/bin/python -m pytest tests/test_effects.py tests/test_detector_regressions.py \
  -q --basetemp=/private/var/folders/9k/zgmpxlms40529k533yssmfsh0000gn/T/opencode/detector-final-green
```

**49 passed in 433.41s (7m13s); no skips or xfails.** Includes the original
tiny positive/negative zooms, all four large-zoom easing cases, shake/zoom,
dissolves, encoded typewriter timing, analytic pan/zoom/noise controls, and
word-arrival negative controls. Scoped `git diff --check` passes. No commit
or staging was performed.
