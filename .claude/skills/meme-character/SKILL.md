---
name: meme-character
description: Build and repair reusable characters in assets/characters for the meme generator — crop a user's character sheet into clean single views, regenerate or fix views with Codex (wrong height/proportions, face shape, new angles or expressions) and rebuild the sheet, or collect a real public figure's photos from Wikimedia Commons (`memegen asset commons` → `asset fetch`) and review them (Gate 2). Use this whenever the user gives a new character sheet, photo, pet or celebrity to put in a meme, says a character looks wrong ("키가 작게 나왔어", "얼굴이 너무 둥글어", "시트 다시 만들어줘"), or a cast member's character doesn't exist yet.
---

# Meme character

> Run every `memegen …` below as `uv run memegen …` — the same on Windows, macOS and Linux. No shell-only commands: `memegen frame` for frames, `memegen trash` instead of deleting, `memegen upload-put` for MCP uploads, temporary files inside the work unit (never `/tmp`).

A character is `assets/characters/<slug>/` = `character.json` (type, species, bible, views, provenance) +
`source/` (originals, never sent to Genjutsu) + `views/` (single-subject crops, the only thing sent).
Identity comes only from the user's own material or, for real people, collected photos. Never Higgsfield
Soul/avatars; image generation goes through Codex (`memegen image gen`), not Higgsfield image models.
Detailed rules: `docs/references/sourcing-policy.md`.

## A. From the user's sheet or photos
1. `memegen asset new <slug> --name "…" --type me|fixed --species human|cat …` → `memegen asset add <slug> <file>`
2. Look at the sheet, then crop **large single views** (hero close-up, full front, 3/4, side, a couple of
   expressions) — busy sheets (labels, palettes, costume breakdowns, several outfits) confuse Genjutsu. Exclude
   labels, palettes and text. Exception: a **clean multi-view identity sheet** (one person, one outfit, several
   angles, almost no text) worked best as the *single* identity image in motion-transfer — better than a stack of
   selfies, which widened the face. If the user has one, register it whole as a view (`asset crop` without `--box`,
   `--shot medium --description "multi-view identity sheet: …"`) and use it as `<<<image_1>>>`:
   `memegen asset crop <slug> <sheet> --box x0,y0,x1,y1 --name hero --shot close-up --angle front --description "…"`
3. `memegen asset show <slug>` and look at `views_sheet.jpg`; recrop anything with a label or a cut-off limb.
4. Write the `bible`: identity traits only (face shape, hair, build **and height**, markings/fur) — clothes
   follow the scene. The bible is pasted into looks and prompts, so a wrong bible poisons everything downstream.

## B. Fixing a character that is drawn wrong
Users notice proportions and face shape instantly and care a lot (a tall, slim user drawn short and round-faced was
a real, angry correction). Take the user's statement as ground truth.
1. Move nothing destructive: old views/sheet go to the Trash / Recycle Bin (`uv run memegen trash <paths>`), never a permanent delete.
2. Regenerate with Codex, references attached, stating the fix explicitly and what must stay:
   `memegen image gen --char <slug> --name four_view_fixed --n 2 --aspect landscape --no-clean --ref <old four-view crop> --ref <hero> --prompt "…same four poses… realistic adult proportions of about 8 heads tall, long legs… keep face, hair, outfit exactly…"`
   Generate a whole turnaround in one image when views must match each other; expressions as a 2×2 grid.
3. Compare faces side by side (crop + zoom) with the originals; pick the variant closest to the *corrected*
   truth; if the user confirms a change (e.g. "갸름한 게 맞다"), regenerate the other views to match it.
4. Rebuild the sheet by pasting the new panels into the original sheet (keep labels, text, palettes pixel-exact);
   see `references/sheet-repair.md`. Re-crop views from the high-res generations (`asset crop` without `--box`
   takes the whole image and records `origin: codex:…`), update the bible, update provenance.
5. If the user keeps the sheet elsewhere (e.g. the Downloads folder), replace it only when asked, old copy to the Trash (`memegen trash`).

## C. Real public figures
Never generated from scratch. Identity by provenance (Commons category + file name), not by recognising faces.
1. `memegen asset new <slug> --name "Full Name" --type public_figure`
2. `memegen asset commons "Full Name" --year 2023 --year 2025` → pick 5–6 files named after the person alone
   (skip meetings/groups), include the Wikipedia main image as the anchor.
3. `memegen asset fetch <slug> <url> --page <page> --license "<lic>"` per file (one call each keeps provenance
   right); open `source/candidates_sheet.jpg`.
4. Gate 2 (sourcing-policy §4, ≥ 7): single subject, face clear, no lanyard/text, ≥ 512 px. Keep a frontal
   close-up + a medium/seated or 3/4 view. Crop other people out (`--no-tighten` for photos).
5. `memegen asset review <slug> <view> --score 8 --usable`, and a bible of stable traits (hair, eyes, face
   shape, glasses if always worn).
