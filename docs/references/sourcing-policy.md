# Asset sourcing policy (read this in the Cast / Assets step)

The goal is to give Genjutsu **single-subject images that are clean, share one identity, and match the reference's shot**.
Every character lives in `assets/characters/<slug>/` (`character.json` + `source/` + `views/`).
Only files in `views/` are sent to Genjutsu. **Never send original sheets or `source/` images as-is.**

## 1. Source decision (the first matching rule wins)

| # | Condition | source | Action |
|---|---|---|---|
| 1 | Doesn't need replacing (extras, side characters) | `keep` | No image. The prompt says to keep them as they are |
| 2 | `memegen asset list` already has the character with a usable view | `asset` | Leave `images` empty in cast.json → `render` picks automatically by shot/angle |
| 3 | The user gave a new sheet or photo | `asset` | `asset new` → `asset add` → **crop large single-view regions** (see §2) → Gate 2 |
| 4 | A real existing person (celebrity) who isn't in the folder yet | `public_figure` | **Never generate from scratch.** Collect real photos by web search (§3) → Gate 2 → register as views. If the look decision says *generate*, they are dressed for the scene (look, identity only from those photos) |
| 5 | A generic or fictional character that doesn't exist | `generated` | Generate with **Codex** (§6, no refs) → Gate 2 → register as views |

Additionally, when an `asset` character has no view that fits this reference (different outfit, pose, angle or prop that is part of the meme), make one with **Codex from its views** (§6) instead of settling for a poor match.
**Higgsfield image models (Soul, Qwen, Grok) are never used**; Higgsfield is for Genjutsu video only.

## 2. Cropping sheets (character sheets, model sheets)
Putting a busy sheet (labels, palettes, costume breakdowns, several outfits) into Genjutsu confuses it. **Crop only the big regions, one view per image.**
The one exception: a clean multi-view identity sheet of a single person (one outfit, several angles, little or no text) sent as the *only* identity image. In motion-transfer it held the face better than several separate views or selfies (which widened the face, and a selfie's shirt leaked into the outfit).
- Priority: hero/close-up portrait (for identity) → full-body front → full-body three-quarter → side → front expressions (neutral, surprised, etc.)
- Exclude labels, titles, dividers, color palettes, costume breakdowns, and text blocks. If a box would include a label, pull the top/bottom edge in.
- `memegen asset crop <slug> <sheet> --box x0,y0,x1,y1 --name <name> --shot close-up|medium|full-body --angle front|three-quarter|side --description "..."`
  - It automatically fills the transparent background with white, trims the margins, adds 8% padding, and upscales to a long side of 1024px.
- After cropping, **always look at** `asset show <slug>` (the views contact sheet). If a label is showing or part of the subject is cut off, crop again.

## 3. Collecting celebrity images (Claude Code web search, fully automatic)
1. **Search**: use WebSearch to find 2–4 pages.
   - Priority: Wikimedia Commons (`site:commons.wikimedia.org "<name>"`), the Wikipedia infobox image, official press/newsroom photos, major news-agency photos.
   - Use WebFetch on each page to get direct image file URLs. For Commons, use the `upload.wikimedia.org/...` original or the 1280px thumbnail.
   - Wikimedia rejects generic User-Agents (403 "robot policy"); memegen sends a descriptive one. The Commons API (`list=categorymembers` on `Category:<Name>` and `Category:<Name> in <year>`, then `prop=imageinfo&iiurlwidth=1280`) gives thumbnails + licenses in one go.
2. **Download**: `memegen asset new <slug> --name "<Full Name>" --type public_figure`, then
   `memegen asset fetch <slug> <url1> <url2> ... --page <source page> [--license "CC BY-SA 4.0"]`
   → aim for 6–10 candidates. `source/candidates_sheet.jpg` is created automatically.
3. **Establish identity by provenance**: decide whether an image is that person from the **source metadata** (the Commons file name or category, the Wikipedia infobox, the caption, the article title). **Don't identify people by their face.**
   - Use the Wikipedia/Wikidata main image as the anchor.
   - A candidate is valid only if its visible traits (hairstyle, glasses, beard, build, signature outfit) match the anchor.
   - Drop anything with a different subject in the caption, several people, or an unclear source.
4. **Crop**: from the candidate images, crop only the target person, as a single view (§2).
5. Run Gate 2 → record the results with `asset review`, and write the **bible** in `character.json`. It holds **identity traits only**: face, hairstyle, build, markings or fur pattern. Leave out clothing, because the outfit follows the reference video or the image → reuse it from then on with no new search.

## 4. Gate 2 rubric (score each view 0–10; **use it if it scores 7 or higher**)
| Item | Criterion | Deduction |
|---|---|---|
| Single subject | Exactly one subject in the frame, no other people's faces or bodies | -4 if not met |
| Identity | Consistent with the anchor or other views (hair, glasses, markings/fur pattern, build) | Exclude outright if it doesn't match |
| Visibility | Face ≥ 256px, no occlusion from hands, microphones, sunglasses, or masks | -2 |
| Cleanliness | No watermarks, logos, captions, heavy filters, or motion blur | -2 |
| Resolution | Original long side ≥ 512px (upscaling covers what's below that, but it's a deduction) | -1 |
| Shot fit | Has a view matching the main shot size and angle in the reference (e.g. a full-body reference needs a full-body view) | -1 |
| Lighting/expression | Even lighting; expression neutral to mild (it follows the source's expression) | -1 |

Record the result: `memegen asset review <slug> <view>.png --score 8 --usable --description "<what the image shows>"`
**The description goes verbatim into the Genjutsu prompt's image legend**, so write it concretely: shot size, direction, pose, expression, outfit.

## 5. Which images go to Genjutsu
> **Before this, every replaced character gets a binary look decision** (`look-policy.md` §0). *Generate* → it must pass Gate L, and `render` sends `[look, best close-up]` automatically. *Direct* → the rules below pick its views.

- Each character gets **1–2 images** (total ≤ 8). More images per person did not help and often hurt; a clean multi-view sheet (§2) can be the single one. `render` picks them automatically from the reference cast member's `shot`/`angle`:
  - close-up / medium → [the view with the largest face, the view with the closest angle]
  - full-body → [the full-body view with the matching angle, the view with the largest face]
- Public figures sent directly (look decision *direct*, or `render --skip-look-gate`) are swapped **head-only** in object-swap: the prompt keeps the target's clothes, headwear and jewelry from the video, while glasses follow the reference photos (e.g. Dario keeps his own glasses, not the target's sunglasses).
- If you specify images directly in cast.json, you can use relative paths such as `views/hero.png`.

## 6. Generating images with Codex (`memegen image gen`)
Image generation runs through the Codex CLI (`codex exec` + its built-in image_gen, ChatGPT login). ~1–2 min per image.
```bash
memegen image gen <unit> --ref me --shot full-body --angle three-quarter --name me_suit \
  --prompt "Full-body three-quarter view, standing, wearing a navy suit, slight smile" \
  --description "Me, full-body three-quarter, navy suit, slight smile" [--n 2]
```
- `--ref`: `<slug>` (auto-picks up to 3 views for `--shot/--angle`, with the bible) · `<slug>:<view>` · a file path. Repeatable.
- The references are the identity source. Always include the character's **close-up/hero view** so the face is locked.
- The prompt only describes **what changes** (outfit, pose, angle, expression, prop). Don't re-describe the face — the refs do that.
- Outputs land in `<unit>/03_assets/generated/<name>.png` + `<name>.json` (prompt, refs, thread id) and `<name>_review.jpg` (refs next to outputs).
- **Gate 2 identity check against the refs is mandatory** (§4, compare face shape, eyes, hairstyle, skin tone, glasses/markings on the review sheet). Drift → regenerate (`--n 2` to get options) or fall back to the plain views.
- Real people (`public_figure`) are never generated from scratch. The only Codex use allowed is a **look** built from their collected photos (faithful, dignified likeness; only clothes/pose change), which must pass Gate L identity against those photos.
- Use it in cast.json as `"images": ["03_assets/generated/me_suit.png", "views/hero.png"]` (unit-local, the sidecar `description` becomes the legend),
  or, if it's reusable identity material, promote it: `memegen asset crop <slug> <png> --name <view> --shot ... --angle ...` (no `--box` = whole image; `origin` records it came from Codex).
