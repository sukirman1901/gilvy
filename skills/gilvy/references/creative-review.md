# Creative review: evidence before the full cut

Use these examples to reason about a relationship, not to reproduce the same
symbols on every topic. The locked visual style still applies.

## A weak and stronger direction

Brief: continuing even though you know the direction is wrong.

| | Weak direction | Stronger direction |
|---|---|---|
| Action | A dot moves down a line while the caption discusses regret. | The dot leaves a trail; those same strokes fold into a wall that blocks its return. |
| Meaning | Most of the meaning comes from the caption. | Past effort becomes a present constraint. |
| Consequence | The next sentence can replace the picture arbitrarily. | The wall survives, forcing the next action to respond to it. |
| Revision | Add glow, slow the dot, or change the caption. | Change what the action does to the relationship. |

The weak direction is not universally wrong: a moving dot may be right for a
route or a measured journey. It is weak here because it does not express the
conflict in this brief. A ring is not automatically a good metaphor either.

Run the stronger motion proof offline:

```bash
gilvy preview examples/reflection.yaml
gilvy preview-motion examples/reflection.yaml --duration 7.2 --out out/reflection-proof.mp4
gilvy render examples/reflection.yaml
```

This caption-and-ambient example intentionally needs no narration or numeric
comparison. Watch the transformation at normal speed; the stills alone do not
prove its rhythm works.

## Study references with a question

- [Apple — Intention, animation collaborator's upload](https://vimeo.com/449143205): study how an abstract design idea can be represented by a spatial relationship.
- [Ordinary Folk — Small Steps](https://www.ordinaryfolk.co/project/small-steps): study how one simple subject can sustain a sequence through motion and sound.
- [BUCK — IBM Design Language](https://buck.co/work/ibm-design-language): study the Philosophy and Motion films for visual metaphors and expressive versus productive movement.
- [Ji Lee — Word as Image](https://pleaseenjoy.com/word-as-image/): study how letterforms can participate in meaning rather than merely carry a sentence.

These links are study leads, not bundled assets or proof that the agent watched
a film. Record the actual material inspected. Do not claim frame-by-frame
analysis from a project description. Transfer principles, not copied artwork.

## Record a concrete self-review

Write a short note identifying:

1. The preview filename and time range actually watched.
2. The intended meaning and the visible action supporting it.
3. The weakest beat, and the revision made or reason for retaining it.
4. Any approved material retained and intended differences in the revision.
5. Technical QC results separately from this creative judgment.

Do not label a cut approved unless the user approved it. Self-review is not a
mandatory new permission request; proceed within the existing task scope.

## Continue an approved cut

Keep its source and timing. Render a comparison clip at the same resolution as
the reference, then run:

```bash
gilvy compare out/approved.mp4 out/candidate-motion.mp4 --duration 7.2 --out out/comparison
```

Inspect reference, candidate, and amplified differences. Align starts explicitly
when moving the segment. A short reference may fade out where a longer cut
continues; inspect and explain that intentional difference. Pixel differences
also include compression noise. Sampled equality is not an all-frame guarantee,
and no automatic motion-energy or pixel-difference score establishes taste.
