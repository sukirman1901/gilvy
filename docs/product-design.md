# Inbox preset geometry and limits

This documents an optional code-drawn inbox preset. The historical screenshot
below illustrates component geometry; it is not a recommended SaaS composition,
proof of reference fidelity, or an approved visual standard. The old inbox and
learning films have been removed from examples after the visual audit.

![Historical inbox preset geometry](product/inbox.png)

## Design decisions

| Before | After | Why |
|---|---|---|
| An almost empty panel with tiny generic rows | Navigation, conversation list, message thread, customer/source context, and reply composer | Give the screen a recognisable product task and information hierarchy |
| Repeated anonymous filler | One coherent shipping enquiry, a relevant source, and an actionable reply | Show a causal relationship that motion can explain |
| One flat panel moving as a unit | Separate shell, sidebar, conversations, thread, customer, knowledge and reply planes | Reveal evidence and state changes independently |
| Inconsistent one-off spacing and decoration | Shared colors, measured type, restrained borders, common spacing/radius roles | Establish relationships before adding effects |
| Large typography and gradients masking empty UI | Neutral surfaces; blue signals selection and the primary action | Keep attention on the product content |
| A static save button after a generic workflow | Draft reply becomes a sent state at the cursor action | End the beat with an observable consequence |

Native geometry is 1280x760, designed specifically for this desktop product
film. Sidebar 180px, list 300px, thread 520px, auxiliary context 280px. These
are task-specific proportions, not a universal dashboard layout. Primary
message text is 14px; focus shots enlarge the thread/reply. Auxiliary source
text is 12px and metadata is smaller. Body lines wrap by measured glyph width;
names, subjects and long identifiers ellipsize inside their allotted column.
Source and reply paragraphs have explicit line limits to preserve controls.

Semantic colors and type/spacing/radius roles live in `product_design.py`.
Selection uses a quiet fill rather than a heavy accent rail. Foreground token
contrast is checked on actual surfaces; this is not a claim that a rendered
video is a keyboard-accessible or responsive web application.

## Authoring and independent parts

Use `type: panel`, `variant: inbox` for a complete static reference; `content`
overrides fictional demo strings (brand/workspace/agent/customer/company/email,
message/acknowledgement, source title/path/text and reply). `sent` is boolean.
Full examples use `inbox-part` nodes inside a group so parts can move on their
own. Each part has a native rectangle in `PARTS`; set the layer width/height to
that rectangle and center it at `x+w/2, y+h/2` inside the 1280x760 group.

`progress` on a reply part can reveal its prefix for streaming demonstrations.
The revised example reveals a complete suggested reply rather than typing
through a form. Other parts are static; entrance timing belongs in each
layer's explicit keyframes. `content.sent: true` changes the reply action to
sent feedback without moving its text or frame. This is a film, not a network
request or an email-sending integration.

## Scope of validation

Tests cover localized text, invalid content, part bounds, state changes,
contrast, and reply updates through the renderer cache. They do not evaluate
taste, reference fidelity, motion rhythm, or user approval. Small-screen video
readability and audio synchronization require a new authored proof. For a new
product, design its content, hierarchy, and choreography from the brief before
selecting any of these optional components.

## References consulted

- [Emil Kowalski: design engineering](https://github.com/emilkowalski/skills/blob/main/skills/emil-design-eng/SKILL.md)
  and [UI cheatsheet](https://github.com/emilkowalski/skills/blob/main/ui-cheatsheet.md):
  purposeful motion, easing by function, restrained press feedback, and keeping
  entry geometry coherent. Web performance/gesture rules are not presented
  as features of this offline Pillow renderer.
- [Frontend Expert: foundations](https://github.com/sukirman1901/frontend-expert/blob/main/skills/design-foundations/SKILL.md)
  and [anti-patterns](https://github.com/sukirman1901/frontend-expert/blob/main/references/anti-patterns.md):
  content before geometry, shared anchors, spacing relationships, quiet
  selection, realistic content and measured readability.

These principles are adapted to a code-rendered video. No skill pack is
installed or copied into Gilvy, and naming a reference is not evidence that
the visual result matches it. Numtera remains a motion study, not a set of
source assets or recovered layers.
