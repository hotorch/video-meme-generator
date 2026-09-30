# Take failed → what to change

Change one thing per re-take, re-check, and re-probe (4 s, 480p) before another full run.

| Symptom on the compare sheet | Likely cause | Prompt / input fix |
|---|---|---|
| The wrong person got a face (A's face on B) | Binding cues too weak or shared ("the man in black") | Bind by seat/position + a cue unique to that person in *every* shot type; keep each person's tokens in one sentence |
| Identity drifts after a hard cut | Model re-finds people per shot | Add "keeps the same identity across every cut"; put the close-up token right after the look token; probe the 4 s that contain a cut |
| Face looks like a blend of the look and the close-up | Roles not stated | "wearing that outfit from <<<image_1>>>, with the face of <<<image_2>>>"; don't describe the face in words |
| Outfit reverted to the original | Look not referenced as outfit authority | "wearing exactly that outfit" on the look token; check the look really passed Gate L |
| Props vanish or float (mic, wheel, glasses) | Not protected / conflicting eyewear | List them under Keep unchanged; say which glasses win |
| Extra person / duplicate face appears | Too many references or unreferenced image | Every token referenced exactly once in its role; "no extra people" in negatives; drop a weak image |
| Text, logos, watermark on output | References contain text (lanyards, prints) | Negatives + clean the reference (crop out lanyards; looks use "no readable words") |
| Lip-sync or gestures out of time | Motion block missing | "performs exactly the original movements, lip movements… in every shot" |
| Run fails / nsfw status | Moderation on names or content | Remove real names; describe by appearance; failed runs are refunded but cost time |
| Everything subtly ignored | Sentences that restate the video or the images drown the real changes | Cut every sentence that isn't a delta, binding, conflict or failure guard (SKILL.md 3b); repeat only the riskiest invariant |
| A new setting, prop or story beat is missing | Prompt too short for a re-stage (T4) — the change lives in no image | Write the world, props and beats in order (patterns.md §6); length is fine here |
| Main person got the crowd's look (or the reverse) | Roles not separated (T2) | Add a cross-exclusion block: "<<<image_2>>> is never applied to the central person…" |
| App UI, usernames or captions from a screen capture survive | Capture debris read as scene content (T3) | Name the debris in a CLEAN FRAME block; better, crop it out at Gate 1 |
| Face shape stays the source actor's (broad jaw, round cheeks) | Object-swap keeps source geometry, whatever the prompt | Switch to motion-transfer; in motion-transfer add the body-shape sentence (SKILL §3e) or squeeze the face in the driving video (`docs/references/driving-video-fixes.md`) |
| Source hair / braids / glasses / beard leak onto the new face | Face gap not named | One short contrast sentence per large gap, right after the identity sentence (SKILL §3e); long blocks cause side effects (red lips) |
| A prop the source wears (sunglasses) disappears | "face from `<<<image_1>>>`" copies the bare eyes of the sheet | A separate "the only thing not taken from `<<<image_1>>>` is the eyewear…" sentence *before* the contrast block |
| New person isn't taller / head too big | Wording can't change geometry; a warp that scaled the head | Warp the driving video, stretching below the shoulders only |
| Clothes from an identity photo leak into the outfit | That photo went first / has a distinctive shirt | Put the clean multi-view sheet or look first; drop the photo with the shirt |
| Unswapped people or the crowd get redrawn (other faces, ethnicity, colours) | Motion-transfer redraws the whole frame | A crowd/people lock block (number, positions, look as in `<<<video_1>>>`); if they must be exact, object-swap for this clip |
| Lyrics / subtitles appear | Music clips invite them | "no subtitles, no captions, no on-screen lyrics" |
| Black-and-white stretches come out in colour | Motion-transfer re-renders colour | Say so in the prompt, or re-grade those seconds in post |
| `ip_detected` (refunded) | The clip refuses object-swap, or a crop of the source's own people was sent | Motion-transfer on the same clip; never send source crops |
| Public figure "completed" but the face is untouched (billed) | Silently ignored in object-swap | Motion-transfer, or keep the original person; don't re-run the same thing |
| Output ends early (~12.0 s of a 12.04 s clip) | Genjutsu returns about whole seconds | `prepare` pads to whole seconds, `finalize` trims back — send `prepared.mp4`, not `trimmed.mp4` |
