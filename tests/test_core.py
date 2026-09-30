import subprocess
from pathlib import Path

import pytest

from memegen.genjutsu.prompt import Profile, build
from memegen.hf.client import HFError, output_urls
from memegen.hf.endpoints import OBJECT_SWAP_MIN_PIXELS
from memegen.project import Project
from memegen.schemas import Analysis, CastPlan, Mode
from memegen.video import contact_sheet as cs
from memegen.video import ffmpeg as ff


def analysis(**overrides) -> Analysis:
    data = {
        "source_duration": 20.0, "trim_start": 2.0, "trim_end": 12.0, "meme_beat": "reaction",
        "cast": [
            {"id": "A", "description": "the man in a black leather jacket", "position": "left",
             "importance": "main", "screen_time": 0.9, "face_visibility": 0.8},
            {"id": "B", "description": "the woman in a red dress", "position": "right",
             "importance": "side", "screen_time": 0.7, "face_visibility": 0.6},
            {"id": "C", "description": "the audience", "position": "background",
             "importance": "extra", "screen_time": 1.0, "face_visibility": 0.1},
        ],
        "mode": "object-swap", "mode_reason": "keep scene",
        "gate1": {"passed": True, "score": 8},
    }
    data.update(overrides)
    return Analysis.model_validate(data)


PLAN = CastPlan.model_validate({"assignments": [
    {"cast_id": "B", "source": "public_figure", "character": "jensen_huang", "images": ["j1.png"]},
    {"cast_id": "A", "source": "asset", "character": "me", "images": ["me_front.png", "me_34.png"]},
    {"cast_id": "C", "source": "keep"},
]})


def test_prompt_orders_main_first_and_numbers_images():
    plan = PLAN.model_copy(deep=True)
    plan.assignments[1].image_notes = ["front close-up, smiling", "full body, three-quarter"]
    request = build(analysis(), plan, {"me": Profile("Alex", "human", "short black hair, round glasses")})
    assert request.images == ["me_front.png", "me_34.png", "j1.png"]
    assert request.legend[0] == "<<<image_1>>> = Alex: front close-up, smiling"
    assert request.legend[2] == "<<<image_3>>> = jensen_huang: reference"
    assert request.prompt.startswith("<<<video_1>>> is the source")
    assert ("Replace the man in a black leather jacket (left) with the person in <<<image_1>>> <<<image_2>>>."
            in request.prompt)
    assert ("Replace only the face, head and hair of the woman in a red dress (right) with those of the person in "
            "<<<image_3>>>; keep that person's original clothes") in request.prompt
    assert "Keep unchanged: the audience (background)" in request.prompt
    assert "no watermark" in request.prompt
    assert request.bindings[0] == {"cast_id": "A", "character": "me", "images": [1, 2], "role": "views"}


def test_prompt_uses_species_noun():
    plan = CastPlan.model_validate({"assignments": [
        {"cast_id": "A", "source": "asset", "character": "nabi", "images": ["hero.png"]}]})
    request = build(analysis(), plan, {"nabi": Profile("Nabi", "cat")})
    assert "with the cat in <<<image_1>>>" in request.prompt


def test_prompt_motion_transfer_override():
    request = build(analysis(), PLAN, mode=Mode.MOTION_TRANSFER)
    assert request.mode == Mode.MOTION_TRANSFER
    assert "performs exactly the movements of" in request.prompt and "<<<video_1>>>" in request.prompt


def test_prompt_lint():
    from memegen.genjutsu.prompt import lint
    good = ("<<<video_1>>> is the source; keep its camera and background. Replace the man on the left with the person "
            "in <<<image_1>>> <<<image_2>>>. No identity drift, no extra people, no text, no watermark.")
    assert lint(good, 2) == ([], [])
    errors, _ = lint(good, 3)
    assert any("never referenced" in e for e in errors)
    errors, _ = lint(good.replace("<<<video_1>>>", "the video"), 2)
    assert any("<<<video_1>>> never mentioned" in e for e in errors)
    errors, _ = lint(good + " Use image 2 for the face.", 2)
    assert any("non-token" in e for e in errors)
    errors, _ = lint(good + " <<<image_5>>>", 2)
    assert any("not sent" in e for e in errors)
    _, warnings = lint("<<<video_1>>> keep camera. Replace him with <<<image_1>>>.", 1)
    assert any("watermark" in w for w in warnings)
    errors, _ = lint("x" * 10_001 + " <<<video_1>>> <<<image_1>>>", 1)
    assert any("limit" in e for e in errors)


def test_analysis_rejects_out_of_range_trim():
    with pytest.raises(ValueError, match="outside Genjutsu range"):
        analysis(trim_start=0.0, trim_end=3.0)
    with pytest.raises(ValueError, match="outside Genjutsu range"):
        analysis(source_duration=60.0, trim_start=0.0, trim_end=40.0)


def test_cast_plan_validation():
    with pytest.raises(ValueError, match="takes no character"):
        CastPlan.model_validate({"assignments": [{"cast_id": "A", "source": "keep", "character": "me"}]})
    with pytest.raises(ValueError, match="needs a character"):
        CastPlan.model_validate({"assignments": [{"cast_id": "A", "source": "asset"}]})
    too_many = CastPlan.model_validate({"assignments": [
        {"cast_id": "A", "source": "asset", "character": "cat", "images": [f"{i}.png" for i in range(9)]}]})
    with pytest.raises(ValueError, match="accepts 1"):
        too_many.check_ready()


def test_scale_for_min_pixels():
    assert ff.scale_for_min_pixels(1920, 1080) == (1920, 1080)
    w, h = ff.scale_for_min_pixels(640, 360)
    assert w * h >= OBJECT_SWAP_MIN_PIXELS and w % 2 == 0 and h % 2 == 0
    assert abs(w / h - 640 / 360) < 0.01
    w, h = ff.scale_for_min_pixels(360, 640)  # vertical
    assert w * h >= OBJECT_SWAP_MIN_PIXELS and h > w


def test_sample_times_includes_cuts():
    times = cs.sample_times(12.0, 8, cuts=[6.0])
    assert any(abs(t - 6.1) < 1e-6 for t in times)
    assert all(0 < t < 12 for t in times)


def test_output_urls_and_concurrency_error():
    assert output_urls({"video": {"url": "v.mp4"}}) == ["v.mp4"]
    assert output_urls({"images": [{"url": "a.png"}, {"url": "b.png"}]}) == ["a.png", "b.png"]
    assert HFError(400, "Maximum number of concurrent requests (4) has been reached").is_concurrency_limit
    assert not HFError(400, "bad input").is_concurrency_limit


def test_project_manifest(tmp_path):
    from memegen.project import SCAFFOLD
    project = Project.create(tmp_path, "Jensen x Me!", "brief")
    assert project.root.name.endswith("jensen-x-me") and project.slug == "jensen-x-me"
    assert all((project.root / sub).is_dir() for sub in SCAFFOLD)
    assert "- [ ] ingest" in (project.root / "README.md").read_text(encoding="utf-8")
    assert project.next_stage() == "ingest"
    project.mark("ingest")
    assert project.next_stage() == "analyze"
    assert "- [x] ingest" in (project.root / "README.md").read_text(encoding="utf-8")
    assert Project.open("jensen-x-me", tmp_path).root == project.root.resolve()
    second = Project.create(tmp_path, "Jensen x Me!")  # same minute -> distinct unit, same scaffold
    assert second.root != project.root and second.root.name.endswith("jensen-x-me-2")
    assert [u.root.name for u in Project.list_all(tmp_path)] == sorted([project.root.name, second.root.name])
    with pytest.raises(FileNotFoundError, match="several"):
        Project.open("jensen", tmp_path)


FAKE_CODEX = r"""
# fake `codex exec`: record argv/stdin, emit a thread id, "generate" into $CODEX_HOME/generated_images/<thread>
import os, pathlib, sys
from PIL import Image
home = pathlib.Path(os.environ["CODEX_HOME"])
(home / "argv.txt").write_text(" ".join(sys.argv[1:]), encoding="utf-8")
(home / "stdin.txt").write_text(sys.stdin.read(), encoding="utf-8")
out = home / "generated_images" / "t-123"
out.mkdir(parents=True, exist_ok=True)
Image.new("RGB", (64, 96), "red").save(out / "exec-1.png")
print('{"type":"thread.started","thread_id":"t-123"}')
print('{"type":"turn.completed"}')
"""


def fake_executable(folder: Path, name: str, python_source: str) -> Path:
    """A command that runs python_source with this interpreter: a .cmd shim on Windows, a shebang script elsewhere."""
    import sys
    script = folder / f"{name}.py"
    script.write_text(python_source, encoding="utf-8")
    if sys.platform == "win32":
        shim = folder / f"{name}.cmd"
        shim.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
        return shim
    shim = folder / name
    shim.write_text(f"#!{sys.executable}\n" + python_source, encoding="utf-8")
    shim.chmod(0o755)
    return shim


def test_codex_generate_falls_back_to_codex_store(tmp_path, monkeypatch):
    from PIL import Image

    from memegen.imagegen import codex
    fake = fake_executable(tmp_path, "codex", FAKE_CODEX)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setenv("MEMEGEN_CODEX_BIN", str(fake))
    monkeypatch.setenv("MEMEGEN_HOME", str(tmp_path))
    ref = tmp_path / "hero.png"
    Image.new("RGB", (32, 32)).save(ref)
    out = tmp_path / "gen"
    first = codex.generate("in a suit", [codex.Ref(ref, "Alex, close-up")], out, "me_suit", logs_dir=tmp_path / "logs")
    assert first.file == out / "me_suit.png" and first.file.exists() and first.thread_id == "t-123"
    assert codex.load_sidecar(first.file)["refs"][0]["note"] == "Alex, close-up"
    argv = (tmp_path / "argv.txt").read_text(encoding="utf-8")
    assert argv.startswith(f"exec -i {ref}") and argv.rstrip().endswith("-")
    stdin = (tmp_path / "stdin.txt").read_text(encoding="utf-8")
    assert "- Image 1: Alex, close-up" in stdin and "in a suit" in stdin and "./me_suit.png" in stdin
    second = codex.generate("in a suit", [], out, "me_suit")  # never overwrites
    assert second.name == "me_suit_v2"
    many, errors = codex.generate_many("x", [], out, "var", n=2)
    assert not errors and sorted(r.name for r in many) == ["var_1", "var_2"]


@pytest.fixture(scope="module")
def sample_video(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("v") / "sample.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=6",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def test_trim_normalize_restore_audio(sample_video, tmp_path):
    trimmed = ff.trim(sample_video, tmp_path / "t.mp4", 1.0, 5.5)
    assert abs(ff.probe(trimmed).duration - 4.5) < 0.15
    normalized = ff.normalize(trimmed, tmp_path / "n.mp4")
    assert ff.probe(normalized).pixels >= OBJECT_SWAP_MIN_PIXELS
    silent = tmp_path / "silent.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(normalized), "-an", "-c:v", "copy", str(silent)], check=True)
    assert not ff.probe(silent).has_audio
    final = ff.restore_audio(silent, normalized, tmp_path / "final.mp4")
    assert ff.probe(final).has_audio


def test_sheets(sample_video, tmp_path):
    ref = cs.reference_sheet(sample_video, tmp_path / "ref.jpg", n=8)
    cmp = cs.compare_sheet(sample_video, sample_video, tmp_path / "cmp.jpg", n=4)
    imgs = cs.image_sheet([ref, cmp], tmp_path / "imgs.jpg", cols=2)
    assert all(p.exists() and p.stat().st_size > 0 for p in (ref, cmp, imgs))


def test_asset_crop_pick_and_resolve(tmp_path, monkeypatch):
    from PIL import Image

    from memegen import assets
    monkeypatch.setenv("MEMEGEN_HOME", str(tmp_path))
    sheet = tmp_path / "sheet.png"
    img = Image.new("RGBA", (400, 200), (0, 0, 0, 0))  # transparent background -> flattened to white
    img.paste((200, 50, 50, 255), (20, 20, 80, 180))   # "full body" figure
    img.paste((50, 50, 200, 255), (250, 30, 380, 170))  # "portrait"
    img.save(sheet)
    assets.create("cat", "Nabi", "fixed", species="cat")
    body = assets.crop("cat", sheet, (0, 0, 200, 200), "full_front", shot="full-body", description="sitting")
    assets.crop("cat", sheet, (200, 0, 400, 200), "hero", shot="close-up", description="face")
    assert max(Image.open(body).size) == 1024  # tightened then upscaled
    assert Image.open(body).getpixel((5, 5)) == (255, 255, 255)
    assert [v.file for _, v in assets.pick("cat", "medium")] == ["views/hero.png", "views/full_front.png"]
    assert [v.file for _, v in assets.pick("cat", "full-body")] == ["views/full_front.png", "views/hero.png"]
    plan = CastPlan.model_validate({"assignments": [{"cast_id": "A", "source": "asset", "character": "cat"}]})
    plan, profiles = assets.resolve_plan(plan, analysis())
    assert plan.assignments[0].image_notes == ["face", "sitting"]
    assert profiles["cat"].species == "cat"

    whole = assets.crop("cat", sheet, None, "whole", shot="full-body", origin="codex:x.png")
    assert max(Image.open(whole).size) == 1024 and assets.load("cat").views[-1].origin == "codex:x.png"
    assert [n for _, n in assets.refs("cat:hero")] == ["Nabi, face"]
    assert len(assets.refs("cat", "full-body", limit=3)) == 3
    assert assets.refs(str(sheet)) == [(sheet, "")]
    with pytest.raises(KeyError):
        assets.refs("cat:nope")

    unit = tmp_path / "unit"
    (unit / "03_assets" / "generated").mkdir(parents=True)
    gen = unit / "03_assets" / "generated" / "cat_hat.png"
    Image.new("RGB", (8, 8)).save(gen)
    gen.with_suffix(".json").write_text('{"description": "the cat wearing a hat"}')
    plan = CastPlan.model_validate({"assignments": [
        {"cast_id": "A", "source": "asset", "character": "cat", "images": ["03_assets/generated/cat_hat.png", "views/hero.png"]}]})
    plan, _ = assets.resolve_plan(plan, analysis(), unit)
    assert plan.assignments[0].images == [str(gen), str(tmp_path / "assets" / "characters" / "cat" / "views" / "hero.png")]
    assert plan.assignments[0].image_notes == ["the cat wearing a hat", "face"]


LOOK = {"frame_time": 1.0, "body_box": [0, 0, 10, 10], "pose": "sitting on a stool", "outfit": "black tee",
        "keep": ["round glasses"]}


def test_look_gate_blocks_until_approved():
    from memegen.schemas import LookReview
    plan = CastPlan.model_validate({"assignments": [
        {"cast_id": "A", "source": "asset", "character": "me"},
        {"cast_id": "B", "source": "public_figure", "character": "jensen", "images": ["j.png"]},  # dressed too
        {"cast_id": "C", "source": "keep"}]})
    assert plan.look_problems() == ["A: no look decision — record look_decision (look-policy §0)",
                                    "B: no look decision — record look_decision (look-policy §0)"]
    plan.assignments = plan.assignments[:1] + plan.assignments[2:]
    from memegen.schemas import Look
    plan.assignments[0].look = Look.model_validate(LOOK)
    assert "not reviewed" in plan.look_problems()[0]
    a = plan.assignments[0]
    a.look_review = LookReview(chosen="03_assets/looks/A_me_1.png", identity=6, outfit=9, pose=9, clean=9)
    assert not a.look_review.passed and "failed Gate L" in plan.look_problems()[0]
    a.look_review = LookReview(chosen="03_assets/looks/A_me_1.png", identity=8, outfit=9, pose=8, clean=9)
    assert plan.look_problems() == []
    a.images = ["views/hero.png"]
    assert "images[0] must be the approved look" in plan.look_problems()[0]


def test_look_decision_is_binary_and_direct_input_skips_gate_l():
    from memegen.schemas import LookDecision
    cat = {"body_visible": True, "signature_outfit": False, "held_props": False, "dress_up_gag": False,
           "reason": "cat replaces an unclothed cat: nothing to dress"}
    assert not LookDecision.model_validate(cat).generate
    assert LookDecision.model_validate({**cat, "held_props": True}).generate
    assert not LookDecision.model_validate({**cat, "held_props": True, "body_visible": False}).generate  # face only
    plan = CastPlan.model_validate({"assignments": [
        {"cast_id": "A", "source": "asset", "character": "nabi", "look_decision": cat},
        {"cast_id": "B", "source": "asset", "character": "me", "look_decision": {**cat, "dress_up_gag": True}}]})
    assert [a.needs_look for a in plan.assignments] == [False, True]
    assert plan.look_problems() == ["B: no look — describe pose/outfit/mood for me"]
    assert '"generate":true' in plan.model_dump_json()  # the verdict is recorded in cast.json
    assert CastPlan.model_validate_json(plan.model_dump_json()).assignments[1].needs_look


def test_look_prompt_and_resolve_puts_look_first(tmp_path, monkeypatch):
    from PIL import Image

    from memegen import assets, look
    from memegen.schemas import Look, LookReview
    monkeypatch.setenv("MEMEGEN_HOME", str(tmp_path))
    char = assets.create("me", "Alex", "me", bible="tall 185 cm, slim oval face")
    text = look.prompt(Look.model_validate(LOOK), char, 3)
    assert "Images 1-3 define WHO this is: Alex (tall 185 cm, slim oval face)" in text
    assert "Image 4 is an OUTFIT & POSE reference" in text and "Ignore any hair, skin tone" in text
    assert "round glasses" in text and "sitting on a stool" in text

    sheet = tmp_path / "s.png"
    Image.new("RGB", (100, 100), (200, 50, 50)).save(sheet)
    assets.crop("me", sheet, None, "hero", shot="close-up", description="close-up")
    unit = tmp_path / "unit"
    (unit / "03_assets" / "looks").mkdir(parents=True)
    Image.new("RGB", (8, 8)).save(unit / "03_assets" / "looks" / "A_me_1.png")
    (unit / "03_assets" / "looks" / "A_me_1.json").write_text('{"description": "dressed for this scene: stool"}')
    plan = CastPlan.model_validate({"assignments": [{"cast_id": "A", "source": "asset", "character": "me",
                                                      "look": LOOK}]})
    plan.assignments[0].look_review = LookReview(chosen="03_assets/looks/A_me_1.png", identity=8, outfit=8,
                                                 pose=8, clean=8)
    plan, _ = assets.resolve_plan(plan, analysis(), unit)
    assert plan.assignments[0].images == [str(unit / "03_assets/looks/A_me_1.png"),
                                          str(tmp_path / "assets/characters/me/views/hero.png")]
    assert plan.assignments[0].image_notes == ["dressed for this scene: stool", "close-up"]


def test_router_routes_asset_then_look_decision(tmp_path, monkeypatch):
    from PIL import Image

    from memegen import assets, router
    from memegen.schemas import LookReview
    monkeypatch.setenv("MEMEGEN_HOME", str(tmp_path))
    assets.create("cat", "Cat", "fixed", species="cat")
    sheet = tmp_path / "s.png"
    Image.new("RGB", (100, 100), (200, 50, 50)).save(sheet)
    assets.crop("cat", sheet, None, "hero", shot="close-up", description="face")
    no = {"body_visible": True, "signature_outfit": False, "held_props": False, "dress_up_gag": False}
    plan = CastPlan.model_validate({"assignments": [
        {"cast_id": "A", "source": "asset", "character": "cat", "look_decision": {**no, "reason": "cat for cat"}},
        {"cast_id": "B", "source": "asset", "character": "cat", "look_decision": {**no, "held_props": True},
         "look": LOOK},
        {"cast_id": "C", "source": "keep"}]})
    routes = {r.cast_id: r for r in router.route_plan(plan, analysis(), "u")}
    assert (routes["A"].route, routes["A"].ready, routes["A"].reason) == ("direct", True, "cat for cat")
    assert routes["A"].images == [str(tmp_path / "assets/characters/cat/views/hero.png")]
    assert (routes["B"].route, routes["B"].ready) == ("look", False) and "look gen u --cast B" in routes["B"].next
    assert (routes["C"].route, routes["C"].ready) == ("keep", True)
    plan.assignments[1].look_review = LookReview(chosen="03_assets/looks/B_cat_1.png", identity=8, outfit=8,
                                                 pose=8, clean=8)
    summary = router.summary(router.route_plan(plan, analysis(), "u"), "u")
    assert summary["ready"] and summary["counts"]["direct"] == 1 and summary["next"].startswith("memegen prompt draft")

    plan = CastPlan.model_validate({"assignments": [{"cast_id": "A", "source": "asset", "character": "cat"},
                                                    {"cast_id": "B", "source": "asset", "character": "ghost"}]})
    routes = {r.cast_id: r for r in router.route_plan(plan, analysis(), "u")}
    assert routes["A"].route == "decide" and "route decide u --cast A" in routes["A"].next
    assert routes["B"].route == "build_asset" and "no character 'ghost'" in routes["B"].reason


def test_pad_to_whole_seconds_then_finalize_cuts_back(sample_video, tmp_path):
    clip = ff.trim(sample_video, tmp_path / "clip.mp4", 0.0, 4.5)  # Genjutsu would return ~4 s of this
    real = ff.probe(clip).duration
    padded = ff.pad_to_whole_seconds(clip, tmp_path / "pad.mp4")
    info = ff.probe(padded)
    assert abs(info.duration - 5.0) < 0.1 and info.has_audio
    final = ff.restore_audio(padded, padded, tmp_path / "final.mp4", duration=real)
    assert abs(ff.probe(final).duration - real) < 0.1 and ff.probe(final).has_audio


def test_cost_rounds_up_and_lists_both_backends():
    from memegen.hf import endpoints as ep
    cost = ep.genjutsu_cost(12.04, "720p")
    assert cost == {"seconds": 13, "resolution": "720p", "usd": round(13 * 0.681, 3), "credits": 91}
    assert ep.genjutsu_cost(ep.PROBE_SECONDS, "480p")["credits"] == 12
    assert ep.genjutsu_cost(10.0, "1080p")["credits"] is None  # not measured on MCP
    assert ep.billed_seconds(20.0) == 20


def test_lint_blocks_real_names_and_at_mentions():
    from memegen.genjutsu.prompt import lint
    ok = ("Replace the man on the left in <<<video_1>>> with the person in <<<image_1>>>. Everything else stays. "
          "No identity drift, no extra people, no text, no watermark.")
    assert lint(ok, 1, Mode.MOTION_TRANSFER, ["Sam Altman"])[0] == []
    errors, _ = lint(ok + " He looks like Altman.", 1, Mode.MOTION_TRANSFER, ["Sam Altman"])
    assert any("real name" in e for e in errors)
    errors, _ = lint(ok.replace("<<<image_1>>>", "@Image 1"), 1, Mode.MOTION_TRANSFER)
    assert any("@Image" in str(e) or "non-token" in e for e in errors)
    _, warnings = lint(ok + " Smooth skin.", 1, Mode.MOTION_TRANSFER)
    assert any("moderation" in w for w in warnings)


def test_cli_cost_question_mcp_take_and_finalize(tmp_path, monkeypatch):
    """ingest → cost (record the answer) → prepare pads → MCP take add → finalize cuts back to the real length."""
    import json

    from typer.testing import CliRunner

    from memegen.cli import app

    monkeypatch.setenv("MEMEGEN_HOME", str(tmp_path))
    monkeypatch.delenv("MEMEGEN_RUN_PLAN", raising=False)
    src, result = tmp_path / "src.mp4", tmp_path / "result.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=24:duration=6.3",
                    "-f", "lavfi", "-i", "sine=duration=5", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    str(src)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=24:duration=7.04",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(result)], check=True)
    run = lambda *args: json.loads(CliRunner().invoke(app, list(args)).stdout)  # noqa: E731

    assert run("new", "demo", "--source", str(src), "--brief", "왼쪽 의자에 앉은 사람 = 나")["ok"]  # utf-8 on Windows
    cost = run("cost", "demo")
    assert cost["run_plan"] is None and cost["probe"]["credits"] == 12 and cost["full"]["720p"]["seconds"] == 7
    assert run("cost", "demo", "--choose", "probe-first")["run_plan"]["plan"] == "probe-first"
    unit = next((tmp_path / "work").glob("*demo"))
    (unit / "02_analysis" / "analysis.json").write_text(json.dumps({
        "source_duration": 6.3, "trim_start": 0, "trim_end": 6.3, "meme_beat": "t", "mode": "motion-transfer",
        "mode_reason": "face", "gate1": {"passed": True, "score": 8},
        "cast": [{"id": "A", "description": "x", "position": "c", "importance": "main", "screen_time": 1,
                  "face_visibility": 1}]}))
    prepared = run("prepare", "demo")
    assert prepared["padded_to"] == 7.0 and abs(prepared["clip_seconds"] - 6.33) < 0.05
    assert run("take", "add", "demo", str(result), "--model", "hf_mult_motion_control", "--resolution", "480p")["ok"]
    failed = run("take", "add", "demo", "--model", "x", "--resolution", "480p", "--status", "ip_detected")
    assert failed["status"] == "ip_detected"
    assert run("status", "demo")["brief"] == "왼쪽 의자에 앉은 사람 = 나"
    assert Path(run("frame", str(src), "2.5", "--out", str(tmp_path / "f" / "a.png"))["frame"]).exists()
    final = run("finalize", "demo", "--take", "1")
    assert abs(final["video"]["duration"] - 6.33) < 0.05 and final["video"]["has_audio"]
