# Gilvy Audit Hardening Implementation Plan

**Goal:** Resolve all nine reproduced audit findings, harden integration and make the installed skill reliable without manual checkpoints.
**Architecture:** Retain existing renderers and pixel contracts. Share validation/timing/publication concepts; separate technical QC by artifact kind and style routing from engine capability.
**Tech Stack:** Python, pytest, Pillow/NumPy, FFmpeg, MCP, OpenCode.

User explicitly delegates design decisions and requests autonomous TDD and subagents. Existing code and audit provide the design baseline. A focused repair is preferred over a rewrite or expanding into a full video editor.

## Acceptance / tasks
- [ ] T1 Engine fixes: add failing regressions for F1–F9, verify RED, implement minimal fixes, verify focused GREEN; preserve approved output on failed house QC; support complete camera paths; shared keyword SFX clock; card dependencies; product-aware QC; stable errors; track-aware overscan; valid TTS rate; signed tilt.
- [ ] T2 Integration: capability/doctor output, command availability, optional dependency status, consistent MCP contracts; robust jobs/snapshot where practical; tests before behavior changes.
- [ ] T3 Skill/docs: concise router, generic composition routing, standalone references, command/cwd guidance, behavioral eval cases; update README and relevant runtime docs to actual behavior.
- [ ] T4 Spec review then code quality review; fix identified issues with RED/GREEN regression loops.
- [ ] T5 Full suite, direct repro rechecks, MCP fresh-process smoke, installed CLI/dependency checks, clean diff review and completion record.

## Execution
Implement in the installed repository on branch fix/audit-hardening so editable venv and linked skill receive changes. Subagents are sequential writers; independent read-only review may run concurrently. Do not push upstream. Preserve unrelated configuration. Test commands use `.venv/bin/python -m pytest`; retain RED/GREEN evidence in the implementation report. Full suite renders can be lengthy; use background execution and completion notifications.

## Upstream steering
User requested checking new GitHub changes during implementation. `git fetch origin` discovered main `ad76ea9` (PR22/23/24), including editorial collage and relocated examples. Preserve current repair checkpoint, merge upstream after the engine writer finishes, reconcile shared assets/keyframes/image/render/MCP/QC changes, then run new collage tests and full suite. Never merge into a concurrently edited worktree. Upstream fixes some keyframe/overscan gaps; retain its validation and collage semantics rather than blindly choosing either side.

Baseline suite completed: 246 passed, 3 failed, 2 skipped in 607.80s. Additional detector failures: tiny zoom positive/negative rates and third typewriter reveal. Independent diagnosis points to integer-rounded scale sampling/noisy slope override and final-ink-relative reveal threshold. Preserve current test tolerances when repairing.

Installation evidence: global CLI symlink added; download/cutout extras installed with Intel-compatible numba 0.61.2 / llvmlite 0.44.0. Imports verified; real u2net CPU cutout inference succeeded with 128x128 RGBA output. Record compatibility constraints in integration work.

## Boundaries
Resolve audited defects and integration/skill readiness. AE parity (full 3D, 4K, multitrack editor, GPU/browser renderer) remains an explicitly documented roadmap, not a fabricated completion claim. Optional extras must either be installed and validated or reported unavailable by capabilities with an actionable reason.
