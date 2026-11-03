# Study a reference before directing

`gilvy analyze-reference` and MCP `analyze_reference` extract evidence from a
**local video file**, independent of Gilvy's house palette or layout. They do
not generate a reconstruction or download YouTube URLs. Obtain the video file
separately; a title, description, thumbnail or transcript cannot establish its
motion style.

```bash
gilvy analyze-reference reference.mp4 --out out/reference-study
# Correct provisional boundaries with interior seconds, in a new directory:
gilvy analyze-reference reference.mp4 --out out/reference-corrected --boundaries 4.2 9.8
# Deliberately keep one continuous scene, still studied in <=8s chunks:
gilvy analyze-reference reference.mp4 --out out/reference-continuous --boundaries
```

## Outputs

- `reference.json`: source dimensions, duration, average fps, candidate cut
  timestamps/scores, provisional scene intervals, requested frame timestamps,
  clip ranges and paths. Review fields start empty, with `not_reviewed` status.
- `contact-NNN.jpg`: paginated, labelled scene/time thumbnails. Each viewing
  chunk is sampled at 12%, 45% and 80%. These are sampling positions, not a claim
  that the reference has an entrance, action and settled state at those times.
- `scene-NNN/`: PNG samples and MP4 motion clips. Chunks cover every scene in
  full, with 0.25s handles on either side where possible, retaining original
  audio when available. Watch boundary handles to understand transitions.
- `REVIEW.md`: links and a worksheet separating observations from inferences.

## Review sequence

1. Read the manifest and inspect all sheets for composition and typography.
2. Watch **every** clip at normal speed. Stills do not establish rhythm, sound
   synchronization, acceleration, or continuous transformations.
3. Correct scene boundaries when large motion triggered a false cut, or when a
   morph/fade hid a narrative change. Automatic detection is a pixel-change
   heuristic, not semantic segmentation. A long continuous shot remains one
   scene, with multiple viewing chunks.
4. Record **observed** composition, type, color, object actions, transitions and
   sound timing. Put camera, easing and layer hypotheses in **inferred** fields,
   including uncertainty. Mark a scene reviewed only after observing its clips.
5. Write a reconstruction plan from those observations. Do not silently force a
   supplied style into Gilvy's dot/green system. If the target requires a new
   rendering/style capability, name that gap before claiming fidelity.
6. Reconstruct a short proof, then compare aligned video evidence. This tool
   does not recover the original layers, fonts, keyframes, code or exact curves.

## Controls and limits

`--threshold` is a normalized FFmpeg scene-score threshold, default 0.3 (0–1,
exclusive of zero). Lower values detect more changes. `--min-scene` defaults to
0.8 seconds and suppresses auto cuts too close to the preceding accepted cut or
the end. Inspect candidate scores and correct manually rather than treating
them as certainty. Manual boundaries must be unique, ascending and interior;
they bypass the minimum because the reviewer explicitly chose them.

`--clip-seconds` defaults to 8, accepts 1–12, and excludes overlap handles.
`--width` defaults to 640, accepts even values 160–1280; aspect is preserved at
an even encoded height. Clip fps/timestamps may be normalized by the encoder;
`reference.json` retains the requested source intervals. Frames use accurate
seek requests, not recovered keyframe positions. Variable-rate sources require
particular care when making frame-level comparisons.

Input duration is limited to ten minutes and scene count to sixty. Use a short
reference excerpt for longer videos. The destination must be new: retries
cannot accidentally mix prior evidence with a different source. On extraction
failure partial media can remain for diagnosis, but no completed manifest is
written. No vision model, OCR, object tracker, beat detector or easing estimator
runs. `creative_review: required` is an explicit unresolved review step, not an
automatic approval.
