# Genjutsu prompt patterns, by tier

Pick the tier in SKILL.md step 3a first, then start from the matching pattern. Tiers stack: T2 + T3 means the
role blocks from T2 with the identity lock and cleanup from T3 on top.

## Contents
1. T1 swap: one person, clean clip (object-swap)
2. T1 variants: conflict clause, person + object, head-only
3. T2 roles: main + crowd
4. T2 worked example: carpool hip-hop (4 swaps, 8 hard cuts)
5. T3 noisy capture / weak identity
6. T4 re-stage: new world, video donates motion and camera
7. Motion-transfer, one performer
8. Community examples (for tone)

---

## 1. T1 swap: one person, clean clip
The video carries everything else, so say who and with what, and stop.

```
Replace the main dancer in the middle of <<<video_1>>> with the person in <<<image_1>>>. Everything else stays exactly as in <<<video_1>>>: the other dancers, the moves, timing, camera and setting. No identity drift, no extra people, no text, no watermark.
```
(~260 chars. The user's field version was a single sentence: "Put @Image 1 as the main dancer, the middle one,
instead of @Video 1's main dancer. All other things are similar to @Video 1." — and it worked.)

With a look + close-up pair, give each token its role in the same sentence:
`… with the person in <<<image_1>>>, wearing exactly that outfit, with the face of <<<image_2>>>.`

## 2. T1 variants
**One conflict** — two sources disagree; one clause says who wins:
```
Change the man in <<<video_1>>> to the identity and appearance of <<<image_1>>>, but he wears black sunglasses in the same style as in <<<video_1>>>; every other facial and visual feature comes from <<<image_1>>>. Replace the pickup truck with the one in <<<image_2>>>. Everything else as in <<<video_1>>>. No extra people, no text, no watermark.
```
(Person + object is still T1 when each token's target is obvious.)

**Head-only** (look decision = direct; the target keeps his clothes):
```
Replace only the face, head and hair of <person cues> with those of the person in <<<image_3>>> <<<image_4>>>; keep that person's original clothes, headwear and jewelry from <<<video_1>>>.
```
If the reference wears glasses and the target wears sunglasses, say which wins ("glasses follow <<<image_3>>>").

## 3. T2 roles: main + crowd
Two tokens aim at different people, so the prompt's job is the binding matrix: who gets what, who never gets what,
and how many people there are.

```
<<<video_1>>> is the reference for all motion, choreography, timing, composition and camera.

MAIN: Replace only the single central person with the person in <<<image_1>>>, matching face, hair, skin tone, build and clothing, and keep them clearly distinguishable from everyone around them.

SURROUNDING: Replace every surrounding person with the look in <<<image_2>>>: same clothing, headwear, mask and colours on each of them.

EXCLUSION: <<<image_2>>> is never applied to the central person; <<<image_1>>> is never applied to anyone in the crowd. The central person is never swapped with a crowd member.

CROWD: Keep the original number of people, their spacing, rows and positions. Do not add, remove, merge or duplicate people, and do not move anyone between positions.

MOTION: The crowd performs the same synchronized moves and deep bows as in <<<video_1>>>; the central person performs only the original central person's movements. No new gestures.

Camera, framing and cuts exactly as in <<<video_1>>>. No identity drift, no face changes between frames, no flicker, no warped hands, no extra people, no text, no watermark.
```
Short headers help once a prompt has several roles: the model (and the next reviewer) can see which sentences
belong to whom. A T1 prompt doesn't need them.

## 4. T2 worked example: carpool hip-hop (unit `car-hiphop`, 4 swaps, 8 images, 8 hard cuts)
Brief: SUV interior, dashboard camera; front passenger raps into the lens (main), two in the back seat vibe,
driver at the wheel on the right. Wide shots show all four; close-ups mostly the front passenger.

```
<<<video_1>>> is the source: keep its dashboard camera angle, framing, all hard cuts, timing and rhythm, the SUV interior, daylight and the street outside exactly.
Replace the front-passenger rapper nearest the camera (long dreadlocks, white round glasses) with the man in <<<image_1>>>, wearing exactly that outfit, with the face of <<<image_2>>>.
Replace the man in the red cap in the back seat on the left, directly behind the front passenger, with the man in <<<image_3>>>, wearing that outfit, with the face of <<<image_4>>>.
Replace the man in the striped sweater in the back seat on the right with the man in <<<image_5>>>, wearing that outfit, with the face of <<<image_6>>>.
Replace the driver on the right with the man in <<<image_7>>>, wearing that outfit, with the face of <<<image_8>>>.
The front passenger and the man in the red cap are two different people: keep their faces separate, even when one sits right behind the other.
Keep unchanged: the steering wheel, seatbelts and the view through the windows.
Every new person performs exactly the original movements, hand gestures, head turns, lip movements and expressions of the one they replace, in every shot, and keeps the same identity across every cut.
No identity drift, no face morphing, no extra people or limbs, no text, no logos, no watermark.
```
Why it is shaped this way: each person is found by seat + one cue visible in wide and close shots (the cue
describes the *source* person, which no image shows — that's binding, not restating); "wearing that outfit" lets
the look image speak instead of listing its clothes; the look-alike seat pair gets a cross-exclusion; the 8 cuts
are why "same identity across every cut" is spelled out; seatbelts and the wheel are protected because hands touch them.

## 5. T3 noisy capture / weak identity
Use when the clip is a screen recording (Instagram/TikTok UI, usernames, like buttons, captions, watermark), when
faces are small, or when the source actor's face is far from the identity. The prompt now has to hold the
identity against a weak signal and tell the model which pixels are debris.

```
<<<video_1>>> is the reference for the scene, actions, timing, camera and lighting. <<<image_1>>> is the reference for identity.

IDENTITY (highest priority): Replace only the main person with the person in <<<image_1>>>, keeping their face recognizably the same from the first frame to the last. Preserve face shape and proportions, eyes, eyebrows, nose, lips, cheeks, jawline and chin, ears, hairline and hairstyle, skin tone and texture, and facial hair. Do not redesign, beautify, stylize, age, widen or average the face into a generic one.

CONSISTENCY: The face stays stable through every expression, head turn, distance and lighting change — no morphing, no flicker, no changing hair or beard.

CLEAN FRAME: <<<video_1>>> is a phone screen capture. Remove all app interface: usernames, icons, like and comment buttons, progress bars, captions and watermarks. The output is a clean full-frame video with none of them.

Everything else — actions, choreography, camera movement, composition, environment — as in <<<video_1>>>. No extra people, no text, no watermark.
```
Naming the features here is the guard itself, which is why it's the one place where describing a face in words
is right. Still don't *describe* them ("a narrow nose") — list what to *preserve* and let the image define it.
Better still, fix the input: crop the capture UI out at Gate 1 and send more identity views at Gate 2.

## 6. T4 re-stage: new world, the video donates motion and camera
The output looks nothing like the clip except for how people move and how the camera moves. Everything new must
be written, because no image carries it. Skeleton (headers are worth it at this length):

```
REFERENCES
<<<video_1>>> — master for choreography, timing, formation and camera movement only. Do not invent, simplify or replace the choreography.
<<<image_1>>> — master for the main person's identity, hair, build and glasses.
<<<image_2>>> — master for <the new element's> look, scale and colours.

FORMAT — <length>, <aspect>, <one continuous shot / cuts>, <photoreal / style>.

WORLD — <place, light, palette, what is absent (no buildings, no studio…)>.

SUBJECT — identity lock (as T3, short) + styling that no image shows (gown, colour, material, what it must not look like).

PROPS — <each prop: what it is, exact count/text, e.g. two number candles "3" and "8", both lit>.

BEATS — 1) <opening action>  2) <what happens next, and what triggers it>  3) <the moment the video's choreography starts>. Only after <beat 2> does <beat 3> happen.

CAMERA — follows <<<video_1>>> exactly; no cuts, no reset, no orbit.

HIERARCHY — 1. <main person> 2. <outfit> 3. <signature element> 4. <group> 5. <setting>.

RISKIEST INVARIANT — <the one rule most likely to break, stated plainly and repeated once at the end, e.g. "every person has exactly one flower instead of a head">.

NEGATIVES — scene-specific (no bouquets, no human faces under flowers, no funeral mood…) + no identity drift, no extra people, no text, no watermark.
```
The user's field example of this tier (a 30 s birthday on a hill of giant flowers with flower-headed dancers)
ran to roughly 10k characters and worked. Its strength wasn't its length: it had beats in order (candles → walk in →
reach the centre → choreography starts), an explicit visual hierarchy, and one invariant repeated on purpose.
Genjutsu caps prompts at 10,000 characters; if a T4 brief hits that, cut restatements first, never the beats.

## 7. Motion-transfer, one performer
The source's background is NOT kept — the scene is rebuilt from the references, so say what the scene is.

```
The character from <<<image_1>>> <<<image_2>>> performs the exact same movements as the person in <<<video_1>>>, matching every motion, timing and rhythm and outfit. Natural fabric and hair motion, smooth grounded movement, consistent lighting, camera and framing follow <<<video_1>>>, no identity drift, no extra people, no text, no watermark.
```
(The user's field-tested template. It is T1-sized because the references define the scene; add a setting
sentence — and it becomes a small T4 — when they don't.) If the new setting matters, describe it concretely and
tell the model to ignore the video's and the look's backgrounds. If a probe still keeps the old background, add a
setting reference image as its own token (e.g. `<<<image_3>>>` = the rooftop) rather than writing more words.

## 8. Community examples (for tone, from the Genjutsu web app, where `@Video` / `@Image 1` = our tokens)
- "Use @Video as the motion reference. Preserve the original subject's choreography, timing, pacing, camera movement, and framing. Replace the performer with an original character from @Image 1 while keeping body proportions and identity consistent. Photorealistic music-video frame, natural motion, restrained cinematic color, no face morphing, no identity drift, no extra limbs, no logos, no readable text, no watermark."
- "Use @Video as the base clip. Replace one clearly defined object with the object shown in @Image 2, while leaving the performer, background, lighting direction, and camera path stable. The swap should track perspective and shadows across the shot."

Common thread at every tier: authority of each reference → the change → who never gets what → what must not appear.
