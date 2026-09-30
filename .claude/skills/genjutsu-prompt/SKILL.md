---
name: genjutsu-prompt
description: Meta-prompting for Higgsfield Genjutsu (object-swap / motion-transfer) — understand the reference video and every input image first, grade how far the output departs from the clip (T1 simple swap → T4 full re-stage, which sets the prompt's length), then write the final prompt with video_1 / image_N reference tokens, lint it (`memegen prompt check`), and gate the paid run behind a dry-run and a cheap 4-second probe. Use this whenever a Genjutsu render, probe or re-take is about to happen, whenever someone asks to write, improve, review or debug a Genjutsu / video swap / motion transfer prompt, or when a take came back with identity drift, a wrong person swapped, lost props, watermarks or extra people — even if they only say "프롬프트 짜줘", "젠주츠 돌리기 전에", "왜 얼굴이 바뀌었지", or ask whether a prompt is too long or too short.
---

# Genjutsu prompt (meta-prompt)

> Run every `memegen …` below as `uv run memegen …` — the same on Windows, macOS and Linux. No shell-only commands: `memegen frame` for frames, `memegen trash` instead of deleting, `memegen upload-put` for MCP uploads, temporary files inside the work unit (never `/tmp`).

One Genjutsu run costs real money (720p: $0.68 or 7 credits per input second, rounded up; a 13 s clip ≈ $9 /
91 credits) and there is no undo.
The prompt is the one input we fully control, and the official API docs give no guidance beyond "optional,
≤ 10,000 chars, image_urls are ordered". So the prompt is written deliberately, by you, after actually
understanding the clip and the references — never by filling a template and hoping.

The CLI does the mechanical parts: `memegen prompt draft` (image order + legend + skeleton),
`memegen prompt check` (lint + stamp), `memegen render --dry-run / --probe`. Your job is the judgement.

## 1. Understand the clip (write a scene brief for yourself)
Read `02_analysis/analysis.json`, open `02_analysis/prepared_sheet.jpg` (the trimmed clip, with cut markers),
and pull 2–4 full-resolution frames around the busiest moments and each hard cut:
`uv run memegen frame 01_input/prepared.mp4 <t> --out 02_analysis/frames/f_<t>.png` (then look at them).

Note, per replaced person: where they are on screen in each shot type (wide / close), their most distinctive
**visual** cue (red cap, striped sweater, driver's seat), what their hands and head do, lip-sync, props they touch
(mic, steering wheel, seatbelt), and how many cuts there are. Also note what must survive untouched: the car, the
other people, the camera move, the light. This brief is where the prompt's binding and protection lines come from.

## 2. Understand every image that will be sent
Run `memegen prompt draft <unit>`. It writes `02_analysis/genjutsu_prompt.draft.txt`, a legend
(`<<<image_N>>> = who: what it shows`) and `02_analysis/genjutsu_inputs.jpg`. Look at the inputs sheet, not only
the legend. For each person decide the **role** of each image:
- approved look (studio hero shot) → outfit, styling, body, pose energy
- close-up view → face identity
- plain views only (look decision said "direct") → identity, and the target's original clothes stay

Spot conflicts before writing: the look shows glasses but the target wears sunglasses; the reference has a
microphone the scene doesn't; two characters look alike; a public figure's photo shows a lanyard or text.

## 3. Write `02_analysis/genjutsu_prompt.txt`
English, one idea per sentence. The draft is a starting skeleton — rewrite it.

**If the user wrote their own prompt** (often with the web app's `@Video 1` / `@Image 1` mentions), it is the
base: keep their sentences verbatim, only convert the mentions to `<<<video_1>>>` / `<<<image_N>>>` (the lint
rejects `@Image N`), then add what the steps below say is missing (face-gap block, exceptions, negatives) after
their text.

### 3a. Measure the delta first — it decides the length
Prompts that work in the field range from one line to ~10k characters. What they share is not a length but a
fit: each one says exactly **how the output differs from `<<<video_1>>>`**, and nothing more. The video already
carries everything that stays the same, so every sentence spent restating it is noise, and every change left
unsaid is a guess the model makes for you. So before writing, grade the job from the brief (steps 1–2):

| Tier | When | Shape | Typical size |
|---|---|---|---|
| **T1 swap** | One person (or object) changes; the clip is clean; the target is easy to point at | 1–3 sentences: who (screen position + a cue) → which tokens; the one conflict, if any; "everything else as in `<<<video_1>>>`"; a short negative line | ~150–500 chars |
| **T2 roles** | Two or more tokens go to *different* people or groups (main vs crowd, A vs B, person + object), or the two people look alike | One block per role, then **cross-exclusion** (A's refs never on B, B's never on A), and a count/formation lock when there is a crowd | ~600–2,500 chars |
| **T3 noisy / weak** | Reference is a screen capture (UI, watermark, captions), faces are small, or the source face is far from the identity | Add to T1/T2: an identity-lock block that names *what* to preserve (face shape, jaw, eyes, hairline…) and forbids reinterpretation, plus explicit cleanup (no UI, no captions, no watermark) | +300–1,500 chars |
| **T4 re-stage** | The output lives in a new world: new place, new props, new story beats; the video only donates motion and camera | A full brief — see below | 2,000–10,000 chars |

Tiers stack (T2 + T3 is common). If you can't decide between two tiers, pick the lower one and let a probe tell
you what's missing — adding a clause after a seen failure is cheap; untangling a bloated prompt is not.

### 3b. Every sentence has to earn its place
Keep a sentence only if it is one of:
1. **Delta** — something that differs from `<<<video_1>>>` (who, a new setting, a new prop, an event that isn't in the clip).
2. **Binding** — which token goes to which on-screen person, found by position plus one or two visual cues
   visible in every shot type ("the man in the red cap in the back seat, behind the driver").
3. **Conflict resolution** — where two sources disagree, say which one wins, in one clause
   ("sunglasses as in `<<<video_1>>>`, everything else from `<<<image_1>>>`").
4. **Failure guard** — a failure you saw in a take, or one this specific clip predicts (hard cuts → "same identity
   across every cut"; lyric video → "no subtitles"; look-alike pair → "two different people").

A sentence that only restates the video ("keep the lighting, the framing, the background…") is not on the list —
fold all of that into one "everything else as in `<<<video_1>>>`" clause. A sentence that describes what an image
already shows (outfit colours, face features) is not on the list either — words compete with the image. The
exceptions are T3's identity lock, where naming the features to preserve is itself the guard, and T4, where the
new world exists in no image and must be written.

### 3c. Shapes per tier
- **T1** — `Replace <position + cue> in <<<video_1>>> with the person in <<<image_1>>>[, face from <<<image_2>>>]. <conflict>. Everything else stays exactly as in <<<video_1>>>. No identity drift, no extra people, no text, no watermark.`
- **T2** — blocks with short headers (MAIN / SURROUNDING / OBJECT…), one per role → a cross-exclusion block
  ("`<<<image_3>>>` is never applied to the main dancer; `<<<image_1>>>` never to anyone in the crowd") → for crowds,
  keep the number, spacing and positions of people, no merging or duplicating → motion ("each performs exactly the
  movements of the one they replace") → negatives.
- **T3** — put the identity block first and label it the highest priority; list the features to hold, and forbid
  beautifying, regenerating or averaging the face. Then name the capture debris to remove (app UI, usernames,
  like buttons, captions, watermark) so the model doesn't learn them as scene content.
- **T4** — reference roles first (what each token is the master of: `<<<video_1>>>` = choreography, timing and
  camera only), then format (length, aspect, one shot or cuts) → the world (place, light, palette) → the subject
  (identity lock + styling) → props → **beats in order** (what happens first, what triggers what) → camera →
  a visual hierarchy (rank what matters most) → negatives. Repeat **only the single riskiest invariant** (e.g. "one
  person = one flower") — repetition is a spotlight, and spotlighting everything spotlights nothing.

Worked examples for every tier are in `references/patterns.md`.

### 3d. Rules that hold at every tier
- **Tokens only** (`<<<image_1>>>`, `<<<video_1>>>`). The web app's @-mentions serialize to these; plain
  "image 1" is ambiguous. Every image sent must be referenced, or it is noise the model will still use.
- **Don't write real people's names.** Names can trip moderation (a failed/nsfw run still costs time) and add
  nothing the image doesn't. Describe by appearance and token.
- **Tailor the negatives to what you saw.** If the scene has text that belongs there (whiteboard, signs), write
  "no added text" so the model doesn't wipe it; music clips invite "no subtitles, no captions, no on-screen lyrics";
  a reference photo with a headset mic or lanyard needs "no microphones" (or a crop at Gate 2).
- **Know what the prompt can't do.** In object-swap the source actor's face geometry dominates — our A/B runs
  (docs/findings.md #8–10) got the same face from a 1,400-char prompt, a 227-char one and no prompt at all. There the
  prompt decides *who* is swapped, what is protected and what must not appear; face shape is decided by the clip and
  the images (or by switching to motion-transfer). Motion-transfer rebuilds the scene, so there the prompt carries
  much more weight — describe the setting if the references don't define one.

### 3e. Face gap: the bigger the gap, the more the prompt has to say
The user's rule (2026-09-30): when the source performer's face is very different from the reference face, the
prompt has to be adjusted to that gap. A generic "identity from `<<<image_1>>>`" lets the model keep the performer's
jaw, hair and features. So before writing, crop the performer's face from `01_input/prepared.mp4` (biggest
close-up, a profile, a wide shot) and write `02_analysis/face_gap.md`. Rate each of these none / small / **large**:
sex, age, face width and shape, jaw and chin, cheeks, head size vs body, hair (length, texture, colour, hairline,
braids), facial hair, eyebrows, eyewear, complexion, build, headwear and accessories near the face.

For every **large** gap, write one contrast sentence. Name the source trait **and** the reference trait that
replaces it:
- "The performer in `<<<video_1>>>` has long braids, round clear glasses and a goatee; the result has the short
  black textured hair and clean-shaven face of `<<<image_1>>>` — no braids, no goatee."
- "The performer in `<<<video_1>>>` is a woman with a small rounded face; the result is the man from `<<<image_1>>>`,
  with his slim oval face and narrow jaw."

Put the contrast block right after the identity sentence. For a prompt the user wrote, append it after their text
and keep their sentences. Small gaps need nothing, since the image carries them. Several large gaps push the job to
T3 (identity lock). They also favour motion-transfer over object-swap, because object-swap keeps the source geometry.
Describe skin as "complexion", never with skin- or neck-exposure words (nsfw trap).

Body shape follows the same logic. When the performer is heavier or rounder than the new person, one sentence
helped: "`<<<video_1>>>` gives only the pose, timing and camera — not the body shape, weight or face shape; those
come from `<<<image_1>>>`", plus slim-build negatives (no round face, no double chin, no broad torso). It works on
frontal and medium shots; on low-angle or dash-cam close-ups the driving video still wins — edit the video
instead (`docs/references/driving-video-fixes.md`).

If the source has a prop the reference lacks and the user wants it kept (for example sunglasses), write a separate "keep X" exception sentence *before* the contrast block. Without it the model copies the bare face from the sheet. Keep contrast blocks short (one sentence per large gap). In v03 a long block pushed side effects, such as red lips, onto chair.

## 4. Check, then gate the money
1. `memegen prompt check <unit>` — errors block the render (missing/extra tokens, no `<<<video_1>>>`, `@Image`
   mentions, real names of the public figures being sent, > 10k chars). Warnings are yours to judge (length,
   moderation-risky words, no `face_gap.md`). It stamps the prompt against the exact image set; if looks or
   order change later, check again (render refuses a stale stamp).
2. `memegen render <unit> --dry-run [--probe --probe-start <s>]` — nothing leaves the machine; writes the request
   (REST model and `mcp_model`, driving video, image order, prompt, cost in $ and credits).
3. Spend according to the unit's `run_plan` (the one cost question, meme-video skill). Don't ask again here.
   - **probe-first**: 4 s at 480p ($1.27 / 12 credits). Pick the 4 s with the biggest face, the most swapped people
     and a cut. It answers the expensive questions — do the tokens bind to the right people, does the identity
     hold, does the mode fit — for a fraction of the price. Unsure between modes → probe both on the same window.
   - **full**: the whole clip, 720p unless the user picked 480p.
   - **prep-only**: stop after the dry-run and show the prompt, the inputs sheet and the cost.
4. Run it with REST (`memegen render`) or the MCP connector — `docs/references/generation-backends.md`.

## 5. After a take
Compare `04_renders/take_N_compare.jpg` against the brief, and crop the swapped faces from 5–6 frames (close-ups,
profiles, after each cut) next to the identity image — the compare sheet's thumbnails hide face-shape drift.
A probe that passed is no guarantee: in long clips where the person gets small, the full run has drifted back to
the original face. For each failure, change the prompt in the smallest
way that addresses its cause (see `references/failure-fixes.md`), re-check, and re-probe before another full run.
Record what changed and why in the take's review notes so the next unit starts smarter.
