"""Looks: dress each replaced character for the reference video before Genjutsu sees it.

Genjutsu swaps far better when the input image already matches the target: same posture (seated in a car ->
seated on a stool), same framing, the target's signature props (cap, glasses, chains) and the video's vibe,
on a plain background. For every replaced cast member with a `look` in cast.json (real people too, dressed only from their
collected photos — never generated from scratch):

    1. cut the target's body (neck down, so the original face is never sent) from the source video frame
    2. codex image_gen: identity refs (full-body view for build/height + close-up for the face) + that outfit ref
    3. review sheet [outfit ref | identity refs | variants] -> Claude scores Gate L -> `look approve`

The approved look goes to Genjutsu as image 1 of that character, followed by its best close-up view.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from memegen import assets
from memegen.imagegen import codex
from memegen.project import Project
from memegen.schemas import CastAssignment, Look
from memegen.video import contact_sheet as cs
from memegen.video import ffmpeg as ff


def stem(a: CastAssignment) -> str:
    return f"{a.cast_id}_{a.character}"


def outfit_ref(project: Project, a: CastAssignment) -> Path:
    """Full-resolution frame at look.frame_time, cropped to the neck-down body box."""
    look = a.look
    frame = ff.extract_frame(project.source_video, look.frame_time, project.looks_dir / f"{a.cast_id}_frame.png",
                             width=ff.probe(project.source_video).width)
    dest = project.looks_dir / f"{a.cast_id}_outfit_ref.png"
    with Image.open(frame) as img:
        x0, y0, x1, y1 = look.body_box
        img.convert("RGB").crop((max(x0, 0), max(y0, 0), min(x1, img.width), min(y1, img.height))).save(dest)
    return dest


def identity_refs(slug: str) -> list[codex.Ref]:
    """Full-body front (height/build) + the two best face views (one face view let the face drift wider)."""
    picked = assets.refs(slug, "full-body", "front", limit=3)
    return [codex.Ref(path, f"IDENTITY — {note}") for path, note in picked]


def prompt(look: Look, char: assets.Character, n_identity: int) -> str:
    who = "person" if char.species == "human" else char.species
    ids = "images 1-" + str(n_identity) if n_identity > 1 else "image 1"
    keep = f" These items must be clearly visible: {', '.join(look.keep)}." if look.keep else ""
    real = (f" {char.name} is a real person: keep a faithful, dignified photographic likeness from the reference "
            f"photos (no caricature, no exaggeration); only the clothes and pose change." if char.type == "public_figure"
            else "")
    mood = f" Mood and expression: {look.mood}." if look.mood else ""
    return (
        f"{ids.capitalize()} define WHO this is: {char.name}"
        + (f" ({char.bible})" if char.bible else "")
        + f".{real} Reproduce this {who}'s face, hairstyle, skin tone{', fur pattern' if who != 'person' else ''}, "
        f"body proportions, height and build exactly — do not make them shorter, rounder or younger. Match the face "
        f"width, jawline and cheeks of the close-ups exactly; the outfit or the pose must not widen the face or add "
        f"weight.\n"
        f"Image {n_identity + 1} is an OUTFIT & POSE reference cut from a video (neck down, another person). Take only "
        f"the clothing, accessories and body posture from it. Ignore any hair, skin tone, hands or body shape visible "
        f"in it — those come from {ids}.\n\n"
        f"Create one photorealistic full-color studio photo of the {who} from {ids}:\n"
        f"- Pose: {look.pose}\n"
        f"- Outfit: {look.outfit}.{keep}\n"
        f"- Framing: {look.framing}; one subject, centered, nothing cut off at the head.\n"
        f"- Background: {look.background}; soft even studio light.{mood}\n"
        f"- No text, no brand logos or lettering on clothes, no watermark."
    )


def generate(project: Project, a: CastAssignment, n: int | None = None) -> tuple[list[codex.Generated], dict, Path]:
    char = assets.load(a.character)
    ref = outfit_ref(project, a)
    ids = identity_refs(a.character)
    refs = ids + [codex.Ref(ref, "OUTFIT & POSE reference from the video (neck down) — not the identity")]
    description = f"dressed for this scene: {a.look.pose}, wearing {a.look.outfit}"  # legend adds the name
    results, errors = codex.generate_many(prompt(a.look, char, len(ids)), refs, project.looks_dir, stem(a),
                                          n or a.look.variants, aspect="portrait", clean=False,
                                          description=description, logs_dir=project.logs_dir)
    sheet = cs.image_sheet([ref] + [r.path for r in ids] + [r.file for r in results],
                           project.looks_dir / f"{stem(a)}_review.jpg",
                           title=f"{a.cast_id}->{a.character}: #1 outfit ref | #2-{len(ids) + 1} identity | "
                                 f"#{len(ids) + 2}+ looks")
    return results, errors, sheet
