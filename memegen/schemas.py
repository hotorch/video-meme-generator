"""JSON contracts between the Claude Code "brain" and the memegen "hands".

Claude writes analysis.json / cast.json / review JSON; the CLI validates them here before acting.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, computed_field, model_validator

from memegen.hf.endpoints import GENJUTSU_MAX_IMAGES, GENJUTSU_MAX_SECONDS, GENJUTSU_MIN_SECONDS


class Mode(str, Enum):
    OBJECT_SWAP = "object-swap"
    MOTION_TRANSFER = "motion-transfer"


class Importance(str, Enum):
    MAIN = "main"
    SIDE = "side"
    EXTRA = "extra"


class Source(str, Enum):
    """Where a cast member's identity image comes from — see docs/references/sourcing-policy.md."""
    KEEP = "keep"                    # not replaced; prompt tells Genjutsu to preserve them
    ASSET = "asset"                  # already in assets/characters (user sheet crops or previously verified)
    PUBLIC_FIGURE = "public_figure"  # real person: photos collected by web search; only dressed (look) from those
    GENERATED = "generated"          # generic/fictional: text-to-image, then saved to assets


class GateResult(BaseModel):
    passed: bool
    score: float = Field(ge=0, le=10)
    checks: dict[str, bool] = Field(default_factory=dict)
    notes: str = ""


class CastMember(BaseModel):
    id: str                                   # "A", "B", ...
    description: str                          # visual description used verbatim in the Genjutsu prompt
    position: str                             # e.g. "left, facing camera"
    importance: Importance
    screen_time: float = Field(ge=0, le=1)    # share of the trimmed clip where visible
    face_visibility: float = Field(ge=0, le=1)
    shot: str = "medium"                      # close-up | medium | full-body — drives asset framing
    angle: str = "front"                      # front | three-quarter | profile


class Analysis(BaseModel):
    source_duration: float
    trim_start: float
    trim_end: float
    cuts: list[float] = Field(default_factory=list)
    meme_beat: str                            # what makes it funny / the moment to keep
    transcript_summary: str = ""
    cast: list[CastMember]
    mode: Mode
    mode_reason: str
    risks: list[str] = Field(default_factory=list)
    gate1: GateResult

    @property
    def trimmed_duration(self) -> float:
        return self.trim_end - self.trim_start

    @model_validator(mode="after")
    def _check(self) -> "Analysis":
        d = self.trimmed_duration
        if not (GENJUTSU_MIN_SECONDS <= d <= GENJUTSU_MAX_SECONDS):
            raise ValueError(f"trimmed duration {d:.2f}s outside Genjutsu range "
                             f"{GENJUTSU_MIN_SECONDS}-{GENJUTSU_MAX_SECONDS}s")
        if self.trim_end > self.source_duration + 0.05:
            raise ValueError("trim_end beyond source duration")
        ids = [c.id for c in self.cast]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate cast ids")
        return self


LOOK_PASS = 7.0


class Look(BaseModel):
    """How a replaced character should look in its Genjutsu input so it fits the reference video (Claude writes it).

    A studio image of the character in the target's pose/outfit/mood is generated with Codex, reviewed (Gate L),
    and sent to Genjutsu first. See docs/references/look-policy.md.
    """
    frame_time: float                         # source-video seconds of a clear frame of this cast member
    body_box: list[int] = Field(min_length=4, max_length=4)  # x0,y0,x1,y1 source px, NECK DOWN (outfit/pose only)
    pose: str                                 # e.g. "sitting upright on a stool, hands resting on his thighs"
    outfit: str                               # what to wear: the target's signature pieces in the video's vibe
    keep: list[str] = Field(default_factory=list)  # props the scene depends on: cap, glasses, chains, mic...
    framing: str = "head to knees, straight-on camera at chest height"
    background: str = "plain light grey studio wall"
    mood: str = ""                            # expression / energy / light, e.g. "confident smirk, warm daylight"
    variants: int = Field(2, ge=1, le=4)


class LookReview(BaseModel):
    """Gate L result for one cast member: every score must be >= LOOK_PASS to pass."""
    chosen: str                               # unit-relative path, e.g. 03_assets/looks/A_me_2.png
    identity: float = Field(ge=0, le=10)      # same face/hair/build as the character's views
    outfit: float = Field(ge=0, le=10)        # target's signature items + vibe present
    pose: float = Field(ge=0, le=10)          # posture/framing matches the reference
    clean: float = Field(ge=0, le=10)         # single subject, plain background, no text/artifacts
    notes: str = ""

    @property
    def passed(self) -> bool:
        return min(self.identity, self.outfit, self.pose, self.clean) >= LOOK_PASS


class LookDecision(BaseModel):
    """Binary: dress this character with a Codex look (Gate L) or send its views straight to Genjutsu.

    Direct input is the default; a look is generated only when the scene needs it to land (virality).
    Claude fills the four checks from the reference video + the chosen asset. See look-policy.md §0.
    """
    body_visible: bool      # the target's body/outfit is on screen enough to matter (not only a face close-up)
    signature_outfit: bool  # the outfit/props ARE the scene: viewers recognise the slot or the joke by them
    held_props: bool        # the target holds/wears props the motion interacts with (mic, guns, phone, cap...)
    dress_up_gag: bool      # the payoff is seeing THIS character dressed as the target (cat in a suit, me as a rapper)
    reason: str = ""

    @computed_field
    @property
    def generate(self) -> bool:
        return self.body_visible and (self.signature_outfit or self.held_props or self.dress_up_gag)


class CastAssignment(BaseModel):
    cast_id: str
    source: Source
    character: str | None = None              # asset slug, e.g. "me", "jensen_huang", "nabi"
    images: list[str] = Field(default_factory=list)  # view paths (ordered, 1–2); empty = auto-pick by shot/angle
    image_notes: list[str] = Field(default_factory=list)  # what each image shows (from Gate 2 review)
    look_decision: LookDecision | None = None  # generate a look or input the views directly (binary)
    look: Look | None = None                  # required when look_decision.generate (real people: from their photos)
    look_review: LookReview | None = None     # Gate L; render refuses until it passes

    @property
    def needs_look(self) -> bool:
        """Dressed for the scene only when the look decision says so (older plans without a decision: yes)."""
        if self.source == Source.KEEP:
            return False
        return self.look_decision.generate if self.look_decision else True

    @model_validator(mode="after")
    def _check(self) -> "CastAssignment":
        if self.source == Source.KEEP:
            if self.images or self.character:
                raise ValueError(f"{self.cast_id}: 'keep' takes no character/images")
        elif not self.character:
            raise ValueError(f"{self.cast_id}: source {self.source.value} needs a character slug")
        return self


class CastPlan(BaseModel):
    assignments: list[CastAssignment]

    def replaced(self) -> list[CastAssignment]:
        return [a for a in self.assignments if a.source != Source.KEEP]

    def look_problems(self) -> list[str]:
        """Gate L: every replacement the look decision dresses must have an approved look, sent first."""
        problems = []
        for a in self.replaced():
            if not a.needs_look:
                continue
            if a.look is None and a.look_decision is None:
                problems.append(f"{a.cast_id}: no look decision — record look_decision (look-policy §0)")
            elif a.look is None:
                problems.append(f"{a.cast_id}: no look — describe pose/outfit/mood for {a.character}")
            elif a.look_review is None:
                problems.append(f"{a.cast_id}: look not reviewed — `memegen look gen` then `memegen look approve`")
            elif not a.look_review.passed:
                problems.append(f"{a.cast_id}: look failed Gate L ({a.look_review.notes or 'score < 7'}) — regenerate")
            elif a.images and a.images[0] != a.look_review.chosen:
                problems.append(f"{a.cast_id}: images[0] must be the approved look {a.look_review.chosen}")
        return problems

    def check_ready(self) -> None:
        for a in self.replaced():
            if a.image_notes and len(a.image_notes) != len(a.images):
                raise ValueError(f"{a.cast_id}: image_notes must match images one-to-one")
        """Before render: every replaced member has images, total within Genjutsu's limit."""
        missing = [a.cast_id for a in self.replaced() if not a.images]
        if missing:
            raise ValueError(f"cast members without images: {missing}")
        total = sum(len(a.images) for a in self.replaced())
        if not 1 <= total <= GENJUTSU_MAX_IMAGES:
            raise ValueError(f"{total} reference images; Genjutsu accepts 1–{GENJUTSU_MAX_IMAGES}")


class AssetReview(BaseModel):
    """Gate 2 output for one character's candidate set."""
    character: str
    ranked: list[dict]                        # [{"path": ..., "score": 0-10, "reasons": [...]}]
    chosen: list[str]                         # 1–2 paths, score >= 7
    gate: GateResult


class OutputReview(BaseModel):
    """Gate 3 output for one render take."""
    take: int
    gate: GateResult
    fix: str = ""                             # what to change for the next take if failed
