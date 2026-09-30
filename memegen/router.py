"""Input router: which path each replaced character's Genjutsu input takes (asset → look decision → images).

Two binary questions, asked in order for every replaced cast member:

    1. asset   does the character exist in assets/characters with usable views?
               no  → build_asset   (meme-character skill: crop the user's sheet / collect photos, Gate 2)
    2. look    look_decision.generate?  (body_visible AND (signature_outfit OR held_props OR dress_up_gag))
               no  → direct        reviewed views go straight to Genjutsu (auto-picked by shot/angle)
               yes → look          Codex look → Gate L review → [approved look, best close-up]
               unset → decide      record the decision first (look-policy §0)

`keep` members are routed to keep. Every route carries a state (ready / todo) and the next step, so a
session can resume a unit from `memegen route show <unit>` alone.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from memegen import assets
from memegen.schemas import Analysis, CastAssignment, CastPlan, Source

KEEP, BUILD_ASSET, DECIDE, DIRECT, LOOK = "keep", "build_asset", "decide", "direct", "look"


@dataclass
class Route:
    cast_id: str
    character: str | None
    route: str                 # keep | build_asset | decide | direct | look
    ready: bool
    next: str = ""             # what to do next (command or skill), empty when ready
    reason: str = ""           # why this route (decision reason, missing asset, review notes)
    images: list[str] = field(default_factory=list)  # direct / approved look: what Genjutsu will get


def _asset_problem(slug: str) -> str:
    try:
        char = assets.load(slug)
    except FileNotFoundError:
        return f"no character '{slug}' in assets/characters"
    if not any(v.usable for v in char.views):
        return f"'{slug}' has no usable views"
    return ""


def route_one(a: CastAssignment, unit: str, shot: str = "medium", angle: str = "front") -> Route:
    base = Route(a.cast_id, a.character, KEEP, True)
    if a.source == Source.KEEP:
        return base
    if problem := _asset_problem(a.character):
        how = ("collect photos (`memegen asset commons`)" if a.source == Source.PUBLIC_FIGURE
               else "crop the user's sheet / generate views")
        return Route(a.cast_id, a.character, BUILD_ASSET, False,
                     f"meme-character skill: {how}, then Gate 2", problem)

    d = a.look_decision
    if d is None and a.look is None:
        return Route(a.cast_id, a.character, DECIDE, False,
                     f"memegen route decide {unit} --cast {a.cast_id} --body-visible/--no-body-visible "
                     "--signature-outfit/--no-signature-outfit --held-props/--no-held-props "
                     "--dress-up-gag/--no-dress-up-gag --reason \"…\"", "no look decision yet")
    reason = d.reason if d else "older plan: a look without a decision counts as generate"

    if not a.needs_look:
        images = a.images or [str(path) for path, _ in assets.pick(a.character, shot, angle)]
        return Route(a.cast_id, a.character, DIRECT, True, "", reason, images)

    route = Route(a.cast_id, a.character, LOOK, False, reason=reason)
    review = a.look_review
    if a.look is None:
        route.next = f"meme-look skill: write the look for {a.cast_id} in cast.json (look-policy §1)"
    elif review is None:
        route.next = f"memegen look gen {unit} --cast {a.cast_id}, then review + `memegen look approve`"
    elif not review.passed:
        route.next = f"fix the look (look-policy §3), `memegen look gen {unit} --cast {a.cast_id}`"
        route.reason = f"{reason} · Gate L failed: {review.notes or 'score < 7'}"
    else:
        route.ready, route.images = True, [review.chosen]
    return route


def route_plan(plan: CastPlan, analysis: Analysis | None, unit: str) -> list[Route]:
    cast = {c.id: c for c in analysis.cast} if analysis else {}
    routes = []
    for a in plan.assignments:
        member = cast.get(a.cast_id)
        routes.append(route_one(a, unit, member.shot if member else "medium", member.angle if member else "front"))
    return routes


def summary(routes: list[Route], unit: str) -> dict:
    todo = [r for r in routes if not r.ready]
    return {"ready": not todo,
            "counts": {k: sum(r.route == k for r in routes) for k in (KEEP, BUILD_ASSET, DECIDE, DIRECT, LOOK)},
            "routes": [asdict(r) for r in routes],
            "next": (f"memegen prompt draft {unit}  (genjutsu-prompt skill)" if not todo
                     else [f"{r.cast_id}: {r.next}" for r in todo])}
