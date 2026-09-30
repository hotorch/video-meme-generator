"""Global asset library: assets/characters/<slug>/

    character.json   metadata: type, bible, views[] (each crop's file/shot/angle/description), provenance
    source/          original sheets / downloaded candidates (never sent to Genjutsu directly)
    views/           single-subject crops actually used as Genjutsu image_urls

Sheets confuse Genjutsu, so a sheet is always cut into single-view crops first (big regions only:
hero/close-up portrait, full-body front / three-quarter / side).
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import httpx
from PIL import Image
from pydantic import BaseModel, Field

from memegen.config import load_settings

SHOTS = ("close-up", "medium", "full-body")
ANGLES = ("front", "three-quarter", "side", "back")
CHAR_TYPES = ("me", "fixed", "public_figure", "generated")


class View(BaseModel):
    file: str                                  # relative to the character dir, e.g. views/hero.png
    shot: str                                  # close-up | medium | full-body
    angle: str = "front"
    expression: str = "neutral"
    description: str = ""                      # what the image shows — used in the Genjutsu prompt
    score: float | None = None                 # Gate 2 score (0-10)
    usable: bool = True
    origin: str = ""                           # "" = cut from the user's own sheet/photo; "codex:<png>" = generated


class Provenance(BaseModel):
    file: str
    url: str | None = None
    page: str | None = None
    license: str | None = None
    note: str = ""
    added: str = Field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))


class Character(BaseModel):
    slug: str
    name: str
    type: str                                  # me | fixed | public_figure | generated
    species: str = "human"                     # human | cat | ...
    bible: str = ""                            # stable appearance traits, reused in every prompt
    views: list[View] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)
    uses: int = 0


def assets_dir() -> Path:
    return load_settings().assets_dir


def char_dir(slug: str) -> Path:
    return assets_dir() / slug


def load(slug: str) -> Character:
    path = char_dir(slug) / "character.json"
    if not path.exists():
        raise FileNotFoundError(f"no character '{slug}' in {assets_dir()}")
    return Character.model_validate_json(path.read_text(encoding="utf-8"))


def save(char: Character) -> Path:
    path = char_dir(char.slug) / "character.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(char.model_dump_json(indent=2), encoding="utf-8")
    return path


def list_all() -> list[Character]:
    root = assets_dir()
    if not root.exists():
        return []
    return [Character.model_validate_json(p.read_text(encoding="utf-8")) for p in sorted(root.glob("*/character.json"))]


def create(slug: str, name: str, type_: str, species: str = "human", bible: str = "") -> Character:
    if type_ not in CHAR_TYPES:
        raise ValueError(f"type must be one of {CHAR_TYPES}")
    if (char_dir(slug) / "character.json").exists():
        return load(slug)
    for sub in ("source", "views"):
        (char_dir(slug) / sub).mkdir(parents=True, exist_ok=True)
    char = Character(slug=slug, name=name, type=type_, species=species, bible=bible)
    save(char)
    return char


def add_source(slug: str, file: Path, url: str | None = None, page: str | None = None,
               license_: str | None = None, note: str = "") -> Path:
    """Copy a local file into source/ and record where it came from."""
    char = load(slug)
    dest = _unique(char_dir(slug) / "source" / Path(file).name)
    shutil.copy2(file, dest)
    char.provenance.append(Provenance(file=dest.relative_to(char_dir(slug)).as_posix(), url=url, page=page,
                                      license=license_, note=note))
    save(char)
    return dest


def record_source(slug: str, file: Path, note: str = "") -> None:
    """Record provenance for a file already inside the character dir (e.g. a codex-generated sheet)."""
    char = load(slug)
    char.provenance.append(Provenance(file=file.resolve().relative_to(char_dir(slug).resolve()).as_posix(), note=note))
    save(char)


UA = "memegen/0.1 (https://github.com/reducingtime/video-meme-generator; open-source meme video tool) httpx"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def commons_candidates(name: str, years: list[int] | None = None, min_side: int = 500) -> list[dict]:
    """Single-image candidates for a public figure from Wikimedia Commons: Category:<Name> (+ '<Name> in <year>'),
    with size, license, source page and a 1280px thumbnail URL. Identity comes from this provenance (category +
    file name), never from face recognition. Wikimedia rejects generic User-Agents (403), hence UA."""
    def api(**params) -> dict:
        response = httpx.get(COMMONS_API, params={"format": "json", **params}, headers={"User-Agent": UA}, timeout=60)
        response.raise_for_status()
        return response.json()

    cats = [f"Category:{name}"] + [f"Category:{name} in {y}" for y in (years or [])]
    titles: list[str] = []
    for cat in cats:
        members = api(action="query", list="categorymembers", cmtitle=cat, cmtype="file", cmlimit=200)
        titles += [m["title"] for m in members.get("query", {}).get("categorymembers", [])]
    titles = [t for t in dict.fromkeys(titles) if t.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    out = []
    for i in range(0, len(titles), 40):
        pages = api(action="query", titles="|".join(titles[i:i + 40]), prop="imageinfo",
                    iiprop="url|size|extmetadata", iiurlwidth=1280)["query"]["pages"].values()
        for page in pages:
            info = (page.get("imageinfo") or [{}])[0]
            if not info.get("width") or min(info["width"], info["height"]) < min_side:
                continue
            meta = info.get("extmetadata", {})
            out.append({"title": page["title"][5:], "width": info["width"], "height": info["height"],
                        "license": meta.get("LicenseShortName", {}).get("value"),
                        "url": info.get("thumburl") or info.get("url"), "page": info.get("descriptionurl")})
    return out


def fetch(slug: str, url: str, page: str | None = None, license_: str | None = None) -> Path:
    """Download a web image (found via Claude Code web search) into source/ with provenance."""
    char = load(slug)
    headers = {"User-Agent": UA}
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=60)
    response.raise_for_status()
    kind = response.headers.get("content-type", "").split(";")[0]
    if not kind.startswith("image/"):
        raise ValueError(f"{url} is not an image ({kind or 'unknown type'})")
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(kind, ".img")
    index = len(list((char_dir(slug) / "source").glob("web_*"))) + 1
    dest = char_dir(slug) / "source" / f"web_{index:02d}{ext}"
    dest.write_bytes(response.content)
    with Image.open(dest) as img:  # validate + normalise odd formats to png
        img.load()
        if ext in (".gif", ".img", ".webp"):
            png = dest.with_suffix(".png")
            img.convert("RGB").save(png)
            dest.unlink()
            dest = png
    char.provenance.append(Provenance(file=dest.relative_to(char_dir(slug)).as_posix(), url=url, page=page,
                                      license=license_))
    save(char)
    return dest


def crop(slug: str, source: Path, box: tuple[int, int, int, int] | None, name: str, *, shot: str,
         angle: str = "front", expression: str = "neutral", description: str = "", origin: str = "",
         tighten: bool = True, pad: float = 0.08, min_long_side: int = 1024) -> Path:
    """Cut one view out of a sheet/photo (box=None: whole image, e.g. a codex-generated single view):
    flatten alpha on white, optionally tighten to the subject, pad."""
    if shot not in SHOTS or angle not in ANGLES:
        raise ValueError(f"shot in {SHOTS}, angle in {ANGLES}")
    with Image.open(source) as img:
        region = _flatten(img)
        if box:
            region = region.crop(box)
    if tighten:
        region = _tighten(region, pad)
    long_side = max(region.size)
    if long_side < min_long_side:  # small sheet cells: upscale so model input-size limits never bite
        factor = min_long_side / long_side
        region = region.resize((round(region.width * factor), round(region.height * factor)), Image.LANCZOS)
    dest = char_dir(slug) / "views" / f"{name}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    region.save(dest)
    char = load(slug)
    rel = dest.relative_to(char_dir(slug)).as_posix()
    char.views = [v for v in char.views if v.file != rel]
    char.views.append(View(file=rel, shot=shot, angle=angle, expression=expression, description=description,
                           origin=origin))
    save(char)
    return dest


def pick(slug: str, shot: str = "medium", angle: str = "front", limit: int = 2) -> list[tuple[Path, View]]:
    """Best usable views for a reference shot/angle: identity (closest face) first, then body/angle match.

    close-up/medium reference -> [largest face view, angle match]; full-body -> [full-body angle match, face view].
    """
    char = load(slug)
    usable = [v for v in char.views if v.usable]
    if not usable:
        raise ValueError(f"'{slug}' has no usable views — crop or fetch some first")

    def face_rank(v: View) -> tuple:
        return (SHOTS.index(v.shot), v.angle != "front", v.expression != "neutral", -(v.score or 0))

    def body_rank(v: View) -> tuple:
        return (v.shot != "full-body", v.angle != angle, -(v.score or 0))

    face = sorted(usable, key=face_rank)
    body = sorted(usable, key=body_rank)
    order = [body[0], face[0]] if shot == "full-body" else [face[0], sorted(usable, key=lambda v: (
        v.angle != angle, abs(SHOTS.index(v.shot) - SHOTS.index(shot)), -(v.score or 0)))[0]]
    seen, picked = set(), []
    for v in order + face:
        if v.file not in seen:
            seen.add(v.file)
            picked.append(v)
    return [(char_dir(slug) / v.file, v) for v in picked[:limit]]


def refs(spec: str, shot: str = "medium", angle: str = "front", limit: int = 3) -> list[tuple[Path, str]]:
    """Resolve an image-generation reference spec to [(path, note)]:
    "<slug>" -> its best usable views for shot/angle, "<slug>:<view>" -> that view, anything else -> a file path."""
    slug, _, view_name = spec.partition(":")
    if (char_dir(slug) / "character.json").exists() and not Path(spec).exists():
        char = load(slug)
        if view_name:
            view = next((v for v in char.views if Path(v.file).stem == view_name or v.file == view_name), None)
            if view is None:
                raise KeyError(f"{slug} has no view '{view_name}' ({[Path(v.file).stem for v in char.views]})")
            picked = [(char_dir(slug) / view.file, view)]
        else:
            picked = pick(slug, shot, angle, limit)
        return [(path, _note(char, view)) for path, view in picked]
    path = Path(spec).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"reference '{spec}' is neither a character (asset list) nor a file")
    return [(path, "")]


def _note(char: Character, view: View) -> str:
    what = view.description or f"{view.shot} {view.angle} view, {view.expression} expression"
    traits = f" (identity: {char.bible})" if char.bible else ""
    return f"{char.name}, {what}{traits}"


def describe(slug: str, file: str, **fields) -> None:
    """Update a view's description/score/usable after Claude reviews it (Gate 2)."""
    char = load(slug)
    for view in char.views:
        if view.file == file or Path(view.file).name == file:
            for key, value in fields.items():
                if value is not None:
                    setattr(view, key, value)
            save(char)
            return
    raise KeyError(f"{slug} has no view {file}")


# ---------------------------------------------------------------------------------------------
def _flatten(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return img.convert("RGB")


def _tighten(region: Image.Image, pad: float, threshold: int = 238) -> Image.Image:
    """Shrink to non-white content, then add `pad` (fraction of the larger side) of white margin."""
    gray = region.convert("L").point(lambda p: 255 if p < threshold else 0)
    bbox = gray.getbbox()
    if not bbox:
        return region
    content = region.crop(bbox)
    margin = int(max(content.size) * pad)
    out = Image.new("RGB", (content.width + 2 * margin, content.height + 2 * margin), (255, 255, 255))
    out.paste(content, (margin, margin))
    return out


def _unique(path: Path) -> Path:
    candidate, n = path, 1
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}_{n}{path.suffix}")
        n += 1
    return candidate


def resolve_plan(plan, analysis, base: Path | None = None) -> tuple[object, dict]:
    """Fill each replaced assignment's images (auto-pick by the cast member's shot/angle when empty),
    absolutise view paths, default image_notes to the reviewed view descriptions; return (plan, profiles).

    Relative image paths are character views ("views/hero.png") or, failing that, files in the work unit
    `base` ("03_assets/generated/me_suit.png", note taken from its codex sidecar description)."""
    from memegen.genjutsu.prompt import Profile
    from memegen.imagegen.codex import load_sidecar

    cast = {c.id: c for c in analysis.cast}
    profiles: dict[str, Profile] = {}
    for a in plan.replaced():
        char = load(a.character)
        profiles[a.character] = Profile(name=char.name, species=char.species, bible=char.bible,
                                        public_figure=char.type == "public_figure")
        by_file = {v.file: v for v in char.views}
        if not a.images and a.look_review and a.look_review.passed:
            # approved look first (pose/outfit/framing of the target), then the sharpest face view
            face_path, face = pick(a.character, "close-up", "front", 1)[0]
            a.images = [a.look_review.chosen, face_path.relative_to(char_dir(a.character)).as_posix()]
            a.image_notes = []
        if not a.images:
            member = cast[a.cast_id]
            picked = pick(a.character, member.shot, member.angle)
            a.images = [str(path) for path, _ in picked]
            a.image_notes = [view.description for _, view in picked]
            continue
        notes = []
        for i, image in enumerate(a.images):
            if not image.startswith("http") and not Path(image).is_absolute():
                view = by_file.get(image)
                local = base / image if base else None
                if view is None and local is not None and local.exists():
                    a.images[i] = str(local)
                    notes.append(load_sidecar(local).get("description", ""))
                    continue
                a.images[i] = str(char_dir(a.character) / image)
                notes.append(view.description if view else "")
            else:
                notes.append("")
        if not a.image_notes:
            a.image_notes = notes
    return plan, profiles
