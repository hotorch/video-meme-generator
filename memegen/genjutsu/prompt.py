"""Genjutsu request: image_urls order, a structured prompt DRAFT, and a linter for the final prompt.

The final prompt is written by Claude with the genjutsu-prompt skill (meta-prompt) into
02_analysis/genjutsu_prompt.txt after understanding the video and every reference; `build()` only produces
the image order + a skeleton draft in the four-block shape that works for Genjutsu:

    1. source      <<<video_1>>> is the authority for motion, camera, framing, cuts, timing, light
    2. replace     who becomes whom, bound by position/appearance to <<<image_N>>> tokens
    3. protect     what must not change (kept people, background, props)
    4. quality     motion realism + negatives (identity drift, extra people, text, watermark...)

The official API docs define no placeholder syntax; <<<image_N>>> / <<<video_1>>> is what the web app's
@-mentions serialize to and what practitioners use. IMAGE_REF / VIDEO_REF are the knobs if a probe run
shows otherwise (docs/findings.md #5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from memegen.hf.endpoints import GENJUTSU_MAX_IMAGES
from memegen.schemas import Analysis, CastPlan, Mode, Source

IMAGE_REF = "<<<image_{n}>>>"
VIDEO_REF = "<<<video_1>>>"
MAX_PROMPT_CHARS = 10_000
LONG_PROMPT_CHARS = 2_500  # past this only a T4 re-stage should need the room (genjutsu-prompt skill, step 3a)

TOKEN = re.compile(r"<<<(image|video)_(\d+)>>>")
QUALITY = ("Natural fabric and hair motion, smooth grounded movement, consistent lighting. No identity drift, no face "
           "morphing, no extra people or limbs, no text, no logos, no watermark.")


@dataclass
class Profile:
    """What the prompt needs to know about a character (from assets/characters/<slug>/character.json)."""
    name: str = ""
    species: str = "human"
    bible: str = ""
    public_figure: bool = False


@dataclass
class GenjutsuRequest:
    mode: Mode
    images: list[str]  # local paths or URLs, in the order sent as image_urls
    prompt: str
    bindings: list[dict] = field(default_factory=list)  # [{cast_id, character, images:[n...], role}] for the report
    legend: list[str] = field(default_factory=list)     # "<<<image_1>>> = ..." lines for the prompt author


def ref(n: int) -> str:
    return IMAGE_REF.format(n=n)


def _refs(numbers: list[int]) -> str:
    return " ".join(ref(n) for n in numbers)


def _noun(profile: Profile) -> str:
    return "person" if profile.species == "human" else profile.species


def build(analysis: Analysis, plan: CastPlan, profiles: dict[str, Profile] | None = None,
          mode: Mode | None = None, extra: str = "") -> GenjutsuRequest:
    """Image order (main -> side -> extra, each [look?, face views]) + a four-block skeleton prompt."""
    plan.check_ready()
    mode = mode or analysis.mode
    profiles = profiles or {}
    cast = {c.id: c for c in analysis.cast}
    order = {"main": 0, "side": 1, "extra": 2}
    replaced = sorted(plan.replaced(), key=lambda a: order[cast[a.cast_id].importance.value])

    images: list[str] = []
    legend: list[str] = []
    actions: list[str] = []
    bindings: list[dict] = []
    for a in replaced:
        member = cast[a.cast_id]
        profile = profiles.get(a.character or "", Profile())
        noun = _noun(profile)
        numbers = list(range(len(images) + 1, len(images) + len(a.images) + 1))
        images.extend(a.images)
        dressed = a.look_review is not None and a.look_review.passed
        role = "look+face" if dressed and len(numbers) > 1 else "look" if dressed else "views"
        bindings.append({"cast_id": member.id, "character": a.character, "images": numbers, "role": role})
        for n, note in zip(numbers, a.image_notes or [""] * len(numbers)):
            legend.append(f"{ref(n)} = {profile.name or a.character}: {note or 'reference'}")

        who = f"{member.description} ({member.position})"
        if dressed and len(numbers) > 1:
            source = (f"the {noun} in {ref(numbers[0])}, wearing exactly that outfit, with the face from "
                      f"{_refs(numbers[1:])}")
        else:
            source = f"the {noun} in {_refs(numbers)}"
        if mode == Mode.OBJECT_SWAP and a.source == Source.PUBLIC_FIGURE and not dressed:
            actions.append(f"Replace only the face, head and hair of {who} with those of {source}; keep that "
                           f"person's original clothes, headwear and jewelry (glasses follow the reference).")
        elif mode == Mode.OBJECT_SWAP:
            actions.append(f"Replace {who} with {source}.")
        else:
            actions.append(f"{source[0].upper()}{source[1:]} performs exactly the movements of {who} in {VIDEO_REF}.")

    kept = [cast[a.cast_id] for a in plan.assignments if a.source == Source.KEEP]
    lines = [f"{VIDEO_REF} is the source: keep its camera path, framing, cuts, timing and rhythm, lighting and "
             f"background exactly." if mode == Mode.OBJECT_SWAP else
             f"Camera, framing, timing and rhythm follow {VIDEO_REF}.", *actions]
    if kept:
        lines.append("Keep unchanged: " + "; ".join(f"{c.description} ({c.position})" for c in kept) + ".")
    lines.append("Each new person keeps the identity, face, hair and body type of their references for the whole "
                 "clip while matching the original motion, gestures, lip movements and expressions.")
    lines.append(QUALITY)
    if extra:
        lines.append(extra.strip())
    return GenjutsuRequest(mode=mode, images=images, prompt="\n".join(lines), bindings=bindings, legend=legend)


# Words that tripped (or risk) moderation on real takes: describe skin as "complexion", never bodies/exposure.
RISKY_WORDS = re.compile(r"\b(skin|naked|nude|bare|topless|shirtless|sexy|lingerie|cleavage|blood)\b", re.I)


def lint(prompt: str, n_images: int, mode: Mode = Mode.OBJECT_SWAP,
         names: tuple[str, ...] | list[str] = ()) -> tuple[list[str], list[str]]:
    """(errors, warnings) for a final prompt. Errors block `render`; warnings are for the author to judge.
    `names` = real names of the characters being sent (public figures): they must not appear in the prompt."""
    errors, warnings = [], []
    text = prompt.strip()
    if not text:
        return ["prompt is empty"], []
    if len(text) > MAX_PROMPT_CHARS:
        errors.append(f"{len(text)} chars > Genjutsu limit {MAX_PROMPT_CHARS}")
    elif len(text) > LONG_PROMPT_CHARS:
        warnings.append(f"{len(text)} chars — fine for a T4 re-stage; otherwise cut sentences that restate "
                        f"{VIDEO_REF} or the images (> {LONG_PROMPT_CHARS})")
    if not 1 <= n_images <= GENJUTSU_MAX_IMAGES:
        errors.append(f"{n_images} images; Genjutsu accepts 1–{GENJUTSU_MAX_IMAGES}")
    used = {int(n) for kind, n in TOKEN.findall(text) if kind == "image"}
    videos = {int(n) for kind, n in TOKEN.findall(text) if kind == "video"}
    if not videos:
        errors.append(f"{VIDEO_REF} never mentioned — say what the source clip is the authority for")
    if videos - {1}:
        errors.append(f"only {VIDEO_REF} exists (found video_{sorted(videos - {1})})")
    if missing := sorted(set(range(1, n_images + 1)) - used):
        errors.append(f"images never referenced: {[ref(n) for n in missing]} — every image needs a role")
    if extra := sorted(n for n in used if n > n_images):
        errors.append(f"references to images that are not sent: {[ref(n) for n in extra]}")
    if stray := re.findall(r"<<<(?!(?:image|video)_\d+>>>)[^>]*>>>|@(?:image|video)\s*\d|\b(?:image|video) \d\b",
                           text, re.I):
        errors.append(f"non-token mentions {stray} — convert @Image N / @Video 1 to {ref(1)} / {VIDEO_REF}")
    for name in names:
        parts = [p for p in re.split(r"\s+", name.strip()) if len(p) > 2]
        if name and (name.lower() in text.lower() or (len(parts) > 1 and parts[-1].lower() in text.lower())):
            errors.append(f"real name '{name}' in the prompt — describe by token and appearance (moderation risk)")
    if risky := sorted({m.lower() for m in RISKY_WORDS.findall(text)}):
        warnings.append(f"moderation-risky words {risky} — say 'complexion' for skin; avoid body/exposure words")
    lowered = text.lower()
    for need, hint in (("watermark", "no watermark"), ("identity", "no identity drift"),
                       ("extra", "no extra people/limbs"), ("text", "no text/logos")):
        if need not in lowered:
            warnings.append(f"quality block lacks '{hint}'")
    if mode == Mode.OBJECT_SWAP and "keep" not in lowered and "unchanged" not in lowered:
        warnings.append("nothing is protected — say what stays (background, other people, camera)")
    return errors, warnings
