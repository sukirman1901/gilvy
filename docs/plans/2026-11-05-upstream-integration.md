# Upstream collage integration and follow-up hardening

Date: 2026-11-05. Branch: `fix/audit-hardening`.
Merge inputs: audited fixes/portable skill `1d742cb` and upstream `ad76ea9`.

## Integration decisions

Resolved the four conflicts by comparing the base, audited branch and upstream changes:

- **Skill root:** retained the concise capability-first router and standalone links; incorporated upstream separate-asset/alpha guidance and the distinction between technical demos and creative references. The creative-review guide now explicitly identifies the optional reflection reference as a repository-checkout resource and uses absolute-path placeholders, rather than implying it exists in a standalone copied skill.
- **Assets:** retained the shared dependency inventory, corrupt-image decoding, card dependencies and camera-path overscan. Integrated upstream role-specific collage prompts, narrative briefs as separate metadata, placement sizing, alpha integrity and fragment/reference non-comparability. Attached cards carry their parent and field location.
- **Image scenes:** retained field-specific validation, estimated keyword timing and full camera metrics while integrating placed fragments, parent annotations, collage default grade/grain, independent episode/scene clocks and static collage holds. The actual-duration motion check exempts collage, matching upstream parser/QC semantics.
- **Keyframes:** retained finite numeric/bezier checks and integrated upstream duplicate property/time rejection, episode track duration limits and independent fragment scale floor. Added analytical cubic-bezier value bounds for placement source sizing.

Upstream example/fixture relocations and all nonconflicting upstream changes are preserved. No detector, CLI, capability-provider or package-initializer implementation was edited by this worker.

## New P1 regressions and fixes

### Episode-clock SFX and shared identity

`overlay_event` resolves the existing visual onset to both `scene_at` and `episode_at`. Audio uses the absolute field directly; an episode cue at 2.5 in a scene beginning at 2 is scheduled at **2.5**, not 4.5.

An optional explicit `event_id` identifies a shared sounded annotation across scene declarations. It requires episode clock and SFX. Repeated IDs must agree on absolute `at` and cue name; conflicts fail preflight/build-state before encoding. The soundtrack emits each declared identity once. Distinct identities and unidentified annotations remain distinct even when simultaneous and using the same cue. This is not time-based sound deduplication and does not invent global object identity.

Timeline events preserve the declared onset/clock and include both resolved clocks, identity and keyword-estimate provenance. `COLLAGE.md` documents the new contract.

The incoming dissolve regression explicitly verifies local `u` clamps to zero while `episode_time` remains `scene_start + unclamped_u`. Existing upstream pixel-equality tests for the continuous incoming/outgoing object also pass.

### Source-over attached annotations

Each attached annotation paints onto its own transparent RGBA layer, then source-over composites onto the parent plane before projection. Multiple annotations follow painter order. A 210-alpha red highlighter on opaque white now produces **RGBA (255,45,45,255)**, rather than replacing the parent with (255,0,0,210). Parent opacity/rotation/scale and later-layer occlusion remain intact.

### Collage dependency and scale envelope

Attached cards appear in the same dependency collector as screen-space cards. Missing files, corrupt pixels and empty alpha are preflight errors. The manifest records `overlays[i].src` and `parent`.

Placed fragment resolution combines the static placement scale, camera depth gain and the full local scale-track envelope. Cubic-bezier extrema are solved from the derivative of the easing polynomial, not inferred from key values or sparse timing samples. Attached card source dimensions inherit that parent envelope. Per-layer envelopes are conservative across the entire authored track, including episode-clock tracks reused across shots.

## Additional controller review gaps fixed with RED/GREEN

1. **Entire house publication set protected:** final MP4, timeline, camera metadata, poster, and stale product/preview sidecar deletions are checked against all known input dependencies. An input card named `<stem>_poster.png` cannot be replaced by a new poster or deleted when no poster is requested.
2. **Shared renderer destination lock:** moved the advisory lock into `publication.py`; both house and product writers hold it for their destination. Product encoding/metadata publication remains inside the lock. Existing product queue/cancellation behavior passes focused checks.
3. **`vid.mp4` output collision:** candidate and intermediate files now occupy separate directories. Both path-level fault injection and a real FFmpeg collage render to `vid.mp4` pass.
4. **Narration-extended delayed camera:** the parser defers final static classification for stretchable narrated shots. The resolved-duration build-state check accepts the 0/4/6-second delayed move at six seconds but rejects it when actual duration is only three. Silent/ambient and explicit VO-overrun fixed shots retain immediate timing checks.
5. **Structured numeric/color errors:** nonfinite scene integer values fail before `int()` with the exact scene field path. Non-string color-track properties fail with `scenes[i].color.tracks[j].property` rather than leaking an unhashable-value `TypeError`.

## MCP capability adapter handoff

Implemented `mcp_server.doctor()` as a JSON adapter over the capability agent's shared `capability_report()`. It preserves `ok: false`, `read_only`, and `cutout.inference: unverified/not_run`; it does not run rendering, downloads or inference. The docstring explicitly distinguishes presence from readiness.

Its RED/GREEN regression is isolated in `tests/test_mcp_doctor.py`. Because the provider and related CLI/init changes belong to the capability worker, the adapter/test are handed off as unstaged working-tree changes for the controller's capability commit rather than adding an unfinished cross-worker dependency to the merge commit. The merge index retains the already staged upstream MCP changes; only the new `doctor` hunk and its new test stay outside this merge commit.

## Verification evidence

External logs: `/Users/aaa/.local/share/gilvy-audit/`.

| Stage | Evidence | Result |
|---|---|---|
| Resolved-source baseline | `integration-initial-red.log` | 3 failed, 80 passed: actual-duration static check wrongly rejected collage; key-only manifest stub required normalization |
| New behavior RED | `integration-new-red.log` | 11 failed, 1 passed: both P1s, identity conflicts, attached-card metadata/envelope and event clocks reproduced |
| First GREEN | `integration-green-first.log` | 95 passed |
| Controller review RED | `integration-review-red.log` | 8 failed, 12 deselected: full publication set, cross-renderer lock, vid collision, delayed VO camera, numeric/color validation |
| Review GREEN | `integration-review-green.log` | 103 passed |
| MCP adapter RED | `integration-doctor-red.log` | missing `doctor` function reproduced before implementation |
| Final focused GREEN | `integration-focused-final.log` | **111 passed in 5.60s** |
| Product lifecycle compatibility | `integration-product-lock.log` | **4 passed in 1.57s** |

Final focused command:

```sh
.venv/bin/pytest -q tests/test_upstream_integration.py tests/test_mcp_doctor.py \
  tests/test_collage.py tests/test_audit_hardening.py tests/test_skill_package.py \
  tests/test_episode.py tests/test_qc.py
```

Product lifecycle command:

```sh
.venv/bin/pytest -q \
  tests/test_product.py::test_real_encode_window_audio_cli_and_mcp \
  tests/test_composition.py::test_cancel_during_render_preserves_existing_video_and_cleans_encoder \
  tests/test_composition.py::test_job_queue_status_and_cancel_are_observable \
  tests/test_composition.py::test_mcp_job_reaches_completed_with_real_verified_video
```

No broad/full suite was run. The independent detector worker owns the original detector baseline failures; they are not reclassified as passing by these focused runs. No changes to their tolerances were made here.

## Remaining boundaries

- Shared advisory locking is Unix `fcntl`. Multi-file house publication remains rollback-capable for ordinary exceptions, not power-loss/SIGKILL-atomic. The MP4 is the final replacement; unlocked external readers can observe sidecar transition windows.
- Per-invocation workspaces isolate encoders; house cancellation is checked at phase/commit boundaries, not at every frame. Failed QC candidates remain available for review.
- Product retains its existing post-video metadata-warning contract; this integration adds shared locking, not a new transactional product sidecar protocol.
- Asset envelopes are conservative. Dynamic undeclared files read by custom Python remain outside static dependency discovery. Pixel/alpha checks do not establish artistic quality or semantics.
- SFX deduplication requires explicit identity; repeated annotations without `event_id` intentionally remain separate events. Keyword timing remains estimated rather than measured speech alignment.
- The MCP capability adapter only reports the provider's discovery evidence. Separate successful local model inference reported by the capability worker does not change `doctor` into an inference probe.
