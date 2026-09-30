---
name: meme-look
description: Gate L for the meme generator — decide per swapped character whether to dress it for the reference video, write the look (pose, framing, outfit, props, mood) by reading the clip like a stylist, generate hero shots with Codex (`memegen look gen`), review them honestly (identity/outfit/pose/clean ≥ 7) and approve. Use this whenever a work unit has a cast.json and characters must be prepared for Genjutsu, when the user wants characters "dressed like the video", "힙하게 입혀서", a hero shot / 룩 / 스튜디오 컷 for each person, or when render refuses with "Gate L not passed" / "no look decision" — including real people, who are dressed only from their collected photos.
---

# Meme look (Gate L)

> Run every `memegen …` below as `uv run memegen …` — the same on Windows, macOS and Linux. No shell-only commands: `memegen frame` for frames, `memegen trash` instead of deleting, `memegen upload-put` for MCP uploads, temporary files inside the work unit (never `/tmp`).

Genjutsu swaps far better when each input image already belongs in the scene: same posture as the target,
same framing, the target's signature props, the video's vibe, on a plain background. Plain identity views
(black tee, standing) have to be "translated" by Genjutsu and it often loses the outfit or the props.
`memegen render` refuses to run until every character the decision dresses has an approved look.

The rules, tables and fixes live in `docs/references/look-policy.md` — read §0–§3 there when doing this.
This skill is the procedure and the judgement.

## Steps
1. **Decide, per replaced character** (look-policy §0): `body_visible AND (signature_outfit OR held_props OR
   dress_up_gag)` → generate a look, else direct input. Record it with the router:
   `memegen route decide <unit> --cast A --body-visible --no-signature-outfit --no-held-props --no-dress-up-gag
   --reason "…"`, then `memegen route show <unit>`. Characters routed `direct` are done here (skip steps 2–6).
   A `build_asset` route means the character doesn't exist yet → meme-character skill first. When the user asks for everyone to be dressed (e.g. "나머지 인원들도 힙하게"), that is a
   `dress_up_gag`/`signature_outfit` yes for all of them — say so in the reason.
2. **Read the clip like a stylist** (look-policy §1). Look at the reference sheet and 2–3 full-res frames per
   target (`uv run memegen frame 01_input/source.mp4 <t> --out 03_assets/looks/frame_<t>.png`). Write `look`:
   - `pose`: the target's *posture* (seated in a car → seated on a stool; driver → hands up as if on a wheel)
   - `framing`: the body region the video shows, always "50mm lens from about 2.5 m" (wide angles widen faces)
   - `outfit` + `keep`: concrete garments/colors in the video's vibe; props the scene interacts with
   - `frame_time` + `body_box`: a frame where the outfit is most visible (often a wide shot), box **neck down**
     so the original face is never sent. Preview the crop before generating.
3. **Generate**: `memegen look gen <unit>` (all pending) or `--cast B` (one). ~2 min, characters in parallel.
4. **Review honestly** (look-policy §2): open each `03_assets/looks/<cast>_<slug>_review.jpg`, then crop and
   compare faces side by side with the identity views — thumbnails hide drift. Score identity / outfit / pose /
   clean. A look that is "close" is not a pass; the whole point of the gate is that Genjutsu money is only spent
   on inputs you'd defend.
5. **Record**: `memegen look approve <unit> --cast A --chosen 03_assets/looks/… --identity 8 --outfit 9 --pose 8
   --clean 9 --notes "…"`. Record failures too (they keep render blocked), fix the cause (look-policy §3:
   framing for wide faces, lower body_box for leaked hair, `keep` for missing props) and regenerate.
   Stop after 3 rounds and report what keeps failing.
6. Show the user the chosen hero shots side by side (one image, labelled by slot) before moving on to the
   prompt (genjutsu-prompt skill).

## Real people
Dressed only from their collected photos (never generated from scratch), faithful and dignified likeness, only
clothes and pose change; identity is judged against those photos. If their photos haven't been collected yet,
do that first (meme-character skill).

## Lessons from real runs
- Direct input is the default for a reason: every finished take in the example set used direct identity input.
  A look is worth it only when the outfit/prop is the joke or the scene (look-policy §0).
- A look can carry the **wrong face shape** into Genjutsu: a Codex hero shot that came out rounder than the user
  made the swap worse. Identity < 8 on the face crop → don't use it; fall back to direct input.
- Tight close-up looks have tripped moderation (`nsfw`). Keep looks medium/wide, clothed, neutral.
- If Genjutsu later drops a prop or the outfit, flip the decision to *look* after Gate 3 — not before.

