# Look policy — decide, then (only if needed) dress the character for the reference (Gate L)

A **look** is a Codex studio shot of *that character* in *the target's* posture, framing, signature props and the
video's vibe. It helps Genjutsu when the input must "belong" in the scene, but it costs a few minutes per image and
every generation risks identity drift. So each replaced character first gets a **binary look decision**:
**generate** a look (→ Gate L) or send its reviewed views **directly** to Genjutsu. Direct input is the default;
a look is generated only when the meme needs it to land.

```
look_decision ──generate──→ cast.json look → memegen look gen → review sheet → memegen look approve → render
              └─direct────→ render (views auto-picked by the cast member's shot/angle)
```

## 0. Look decision (binary, per replaced character — write it before anything else)
Answer four yes/no checks from the reference video **and the chosen asset**, and record them in cast.json:

| Check | Yes when… | Yes | No |
|---|---|---|---|
| `body_visible` | The target's body/outfit is on screen enough to matter (medium/full shots), not only a face close-up | carpool rapper seated waist-up | talking-head close-up |
| `signature_outfit` | The outfit/props **are** the scene: viewers recognise the slot or the joke by them | white tunic suit in a gunfight, layered chains + white glasses rapper, school uniform rebel | plain T-shirt, an unclothed animal |
| `held_props` | The target holds/wears props the motion interacts with — without them Genjutsu's hands/occlusion won't line up | mic, pistols, phone at the ear, cigarette, cap that gets touched | empty-handed dancing |
| `dress_up_gag` | The payoff is seeing **this** character dressed as the target (species/style contrast) | the cat in a hip-hop outfit, me as a white-suit action hero | cat replacing a cat, me replacing a man in similar casual clothes |

**`generate = body_visible AND (signature_outfit OR held_props OR dress_up_gag)`**; otherwise direct input.
The rule is computed by the schema (`LookDecision.generate`); write a one-line `reason` in Korean or English.
Record it with `memegen route decide <unit> --cast A --body-visible --no-signature-outfit … --reason "…"`;
`memegen route show <unit>` (memegen/router.py) then lists every character's route — `build_asset` (character
missing → meme-character), `decide`, `direct` (+ the views it will send), `look` (+ Gate L state), `keep` — and
the next step, until the unit is `ready` for the prompt.

```json
"look_decision": {"body_visible": true, "signature_outfit": false, "held_props": false, "dress_up_gag": false,
                  "reason": "고양이→고양이 교체, 옷·소품 없음: 뷰를 바로 넣는 게 정체성에 가장 안전"}
```

- Unsure → **direct**. If take 1's Gate 3 shows a missing prop/outfit or a character that doesn't fit, flip the check
  to yes, write the `look`, and generate — never the other way round without a reason.
- A plan with neither a decision nor a look is blocked by `render` ("no look decision"). Older plans that already have
  a `look` but no decision are treated as *generate*.
- Real people (`public_figure`) follow the same decision. Dressed → only from their collected photos (never generated
  from scratch), faithful and dignified, Gate L identity against those photos. Direct → object-swap takes only their
  head; the target's clothes and props stay (see sourcing-policy.md).

## 1. Read the video like a stylist (write `look` for each character the decision dresses)
Look at the reference sheet + a few full-resolution frames (`uv run memegen frame 01_input/source.mp4 <t>`).
For each target, decide:

| Field | How to decide | Car hip-hop example |
|---|---|---|
| `pose` | The target's **body posture**, not their exact frame. Seated in a car → seated on a stool; standing at a podium → standing; dancing → a neutral mid-move stance. Include hand energy if the scene is gestural. | "sitting upright on a simple wooden stool with only a slight forward lean, one hand raised mid-gesture at chest height like he is rapping, the other resting on his thigh" |
| `framing` | The **body region the video shows** (+ a bit). Always ask for a normal lens so faces aren't distorted: *"50mm lens from about 2.5 m away"*. | "head to knees, 50mm lens from ~2.5 m at chest height" |
| `outfit` | The target's outfit, described concretely (garment, color, print, fit), in the video's vibe. Printed text/logos → "abstract, no readable words / no logo". | "black vintage band tee with a white gothic-lettering print (no readable words), layered iced-out chains, dark jeans, silver rings" |
| `keep` | Props the **scene interacts with or recognises the slot by**: caps, glasses, chains, microphones, instruments. They must survive so Genjutsu's motion/occlusion lines up. | `["round white-framed clear glasses", "layered diamond chains"]` |
| `mood` | Expression/energy + light of the beat. | "confident mid-verse rap energy, mouth slightly open, bright warm daylight" |
| `background` | Almost always plain: `"plain light grey studio wall"`. Never the video's background (Genjutsu keeps that). | |
| `frame_time`, `body_box` | A frame where the outfit is **most visible** (often a wide shot, not the close-up) and a box from the **neck down**. The original face must never be in the crop. | `8.6`, `[100, 340, 500, 720]` |
| `variants` | 2 (default). | |

Non-humans follow the same rules ("the cat sitting upright on a stool like a person, front paws on its lap").

## 2. Gate L review (score each of the variants 0–10, **all four ≥ 7 to pass**)
Open `03_assets/looks/<cast>_<slug>_review.jpg` (#1 outfit ref, then identity views, then the looks) and zoom into faces.

| Score | Question | Typical failures |
|---|---|---|
| `identity` | Same face shape/width, jaw, eyes, hair, skin tone, build/height as the character views? (fur pattern/markings for animals) | face gets wider/rounder, body stockier, looks younger; hair from the outfit ref leaks in |
| `outfit` | Target's signature items + vibe present, `keep` items clearly visible? | missing chains/cap, readable logos/text |
| `pose` | Posture + framing match the target in the video? | standing when the target sits, cropped head, wide-angle distortion |
| `clean` | One subject, plain background, no text/watermark/artifacts (hands!) | extra fingers, props floating, busy background |

Record it: `memegen look approve <unit> --cast A --chosen 03_assets/looks/A_me_2.png --identity 8 --outfit 9 --pose 8 --clean 9 --notes "..."`
A failing review is recorded too (it keeps render blocked). Then fix the cause and `memegen look gen <unit> --cast A`.

## 3. Fixing a failed look (what actually worked)
- **Face drifted wider** → wide-angle/forward-lean framing: switch to "50mm lens from ~2.5 m", reduce the lean. (car hip-hop: failed at identity 6, passed at 8 after this.)
- **Identity weak** → the generator already gets the full-body view + two best face views + the bible; make sure the character's views are current (e.g. corrected height or face-shape views).
- **Hair or skin from the outfit ref leaked** → tighten `body_box` lower (below the chin/hair) or pick another frame.
- **Prop missing** → name it in `keep`, and describe it in `outfit`.
- Stop after 3 rounds and report what keeps failing instead of approving a weak look.

## 4. What Genjutsu receives
Direct input: the character's best views for the cast member's shot/angle (Gate 2 notes as legend).
For each dressed character: `[approved look, best close-up view]` (the look is always image 1 of that character),
with the look's `description` as the image legend. Order across characters stays main → side → extra.
