"""memegen — the deterministic "hands". Every command prints JSON on stdout for the Claude Code skills."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Optional

import typer

from memegen import assets
from memegen.config import load_settings
from memegen.hf import endpoints as ep
from memegen.hf.client import GenerationFailed, HFError, HiggsfieldClient, output_urls
from memegen.project import Project
from memegen.video import contact_sheet as cs
from memegen.video import ffmpeg as ff

app = typer.Typer(no_args_is_help=True, add_completion=False, help=__doc__)
sheet_app = typer.Typer(no_args_is_help=True, help="Contact sheets for review gates")
hf_app = typer.Typer(no_args_is_help=True, help="Raw Higgsfield API access")
asset_app = typer.Typer(no_args_is_help=True, help="Global character assets (assets/characters/<slug>)")
image_app = typer.Typer(no_args_is_help=True, help="Image generation via the Codex CLI (image_gen)")
look_app = typer.Typer(no_args_is_help=True, help="Gate L: dress each character for the reference before Genjutsu")
take_app = typer.Typer(no_args_is_help=True, help="Genjutsu takes: record MCP results, status, resume waiting")
prompt_app = typer.Typer(no_args_is_help=True, help="Genjutsu prompt: draft skeleton, then check Claude's final prompt")
route_app = typer.Typer(no_args_is_help=True, help="Input router: per character, build asset / decide / direct views / look")
app.add_typer(sheet_app, name="sheet")
app.add_typer(image_app, name="image")
app.add_typer(look_app, name="look")
app.add_typer(prompt_app, name="prompt")
app.add_typer(take_app, name="take")
app.add_typer(route_app, name="route")
app.add_typer(hf_app, name="hf")
app.add_typer(asset_app, name="asset")


for _stream in (sys.stdout, sys.stderr):  # Korean text in JSON must survive a cp949/cp1252 Windows console
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def emit(data: dict) -> None:
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def fail(message: str, **extra) -> None:
    emit({"ok": False, "error": message, **extra})
    raise typer.Exit(1)


def client() -> HiggsfieldClient:
    settings = load_settings()
    if not settings.hf_key:
        fail("HF_KEY not set — copy .env.example to .env and add KEY_ID:KEY_SECRET from console.higgsfield.ai")
    return HiggsfieldClient(settings.hf_key)


def open_project(ref: str) -> Project:
    try:
        return Project.open(ref, load_settings().work_dir)
    except FileNotFoundError as error:
        fail(str(error))


def log(message: str) -> None:
    typer.echo(message, err=True)


# ---------------------------------------------------------------------------------------------
@app.command()
def doctor() -> None:
    """Check local tools, the generation backend, codex login and the /watch plugin."""
    import importlib.util
    import platform
    import subprocess

    settings = load_settings()
    codex_bin = shutil.which(settings.codex_bin)  # codex.cmd on Windows
    codex = bool(codex_bin) and subprocess.run([codex_bin, "login", "status"], capture_output=True).returncode == 0
    plugins = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    checks = {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "yt-dlp (URL sources)": importlib.util.find_spec("yt_dlp") is not None,
        "HF_KEY (REST API)": bool(settings.hf_key),
        "codex (looks / image gen)": codex,
        "watch plugin (optional)": plugins.exists() and "claude-video" in plugins.read_text(errors="ignore", encoding="utf-8"),
        "characters": [c.slug for c in assets.list_all()],
    }
    mine = [c.slug for c in assets.list_all() if c.type == "me"]
    required = ("ffmpeg", "ffprobe")
    missing = [k for k, v in checks.items() if v is False and k not in required]
    emit({"ok": all(checks[k] for k in required), "home": str(settings.home), "work_dir": str(settings.work_dir),
          "os": platform.system(), "checks": checks, "run_plan_default": settings.run_plan,
          "onboarded": bool(mine), "my_characters": mine,
          "next": None if mine else "no `me` character yet — run the onboarding course (meme-onboarding skill)",
          "generation": ("REST API ready (memegen render)" if settings.hf_key else
                         "no HF_KEY: generate through the Higgsfield MCP connector in Claude "
                         "(https://mcp.higgsfield.ai/mcp), or add HF_KEY to .env for `memegen render`"),
          "hints": {k: v for k, v in {
              "ffmpeg": {"Windows": "winget install Gyan.FFmpeg  (then open a new terminal)",
                         "Darwin": "brew install ffmpeg"}.get(platform.system(), "sudo apt install ffmpeg"),
              "ffprobe": "comes with ffmpeg",
              "yt-dlp (URL sources)": "installed with memegen (uv sync); only needed for URLs",
              "HF_KEY (REST API)": "cp .env.example .env and paste KEY_ID:KEY_SECRET from https://console.higgsfield.ai"
                                   " — or use the MCP connector instead",
              "codex (looks / image gen)": "npm i -g @openai/codex && codex login  (ChatGPT sign-in; only needed "
                                           "when a character must be dressed for the scene)",
              "watch plugin (optional)": "/plugin marketplace add bradautomates/claude-video && "
                                         "/plugin install watch@claude-video",
          }.items() if k in missing or not checks.get(k, True)}})


@app.command()
def new(name: str = typer.Argument(..., help="short name of this meme, e.g. 'jensen-x-me'"),
        source: Optional[str] = typer.Option(None, help="reference video path or URL (or `memegen ingest` later)"),
        brief: str = typer.Option("", help="what the meme should be, e.g. 'left guy = me, right = Jensen Huang'"),
        frames: int = typer.Option(16, help="frames in the reference contact sheet")) -> None:
    """Create a work unit work/<stamp>-<name>/ with the standard scaffold (+ ingest the video if given)."""
    from memegen.project import SCAFFOLD

    project = Project.create(load_settings().work_dir, name, brief)
    if source:
        _ingest(project, source, frames)
        return
    emit({"ok": True, "unit": str(project.root), "scaffold": SCAFFOLD,
          "next": f"memegen ingest {project.root.name} <video|URL>"})


@app.command()
def ingest(unit: str = typer.Argument(..., metavar="UNIT"),
           source: str = typer.Argument(..., help="reference video path or URL"),
           frames: int = typer.Option(16, help="frames in the reference contact sheet")) -> None:
    """Ingest the reference video into a work unit: probe, detect cuts, render the reference contact sheet."""
    _ingest(open_project(unit), source, frames)


@app.command()
def status(unit: Optional[str] = typer.Argument(None, metavar="[UNIT]")) -> None:
    """Without UNIT: list all work units. With UNIT: stages, next step and files per scaffold folder."""
    if unit:
        emit({"ok": True, **open_project(unit).status()})
        return
    units = Project.list_all(load_settings().work_dir)
    emit({"ok": True, "units": [{"unit": u.root.name, "name": u.load()["name"], "next": u.next_stage()}
                                for u in units]})


RUN_PLANS = {
    "probe-first": "4 s test at 480p first; if it looks right, the full run follows without asking again",
    "full": "straight to the full-length run",
    "prep-only": "prepare everything up to the paid step, then stop",
}


def _cost_table(seconds: float) -> dict:
    """What the one cost question shows: a 4 s probe vs the whole clip, REST USD and MCP credits."""
    return {"clip_seconds": round(seconds, 3),
            "probe": ep.genjutsu_cost(ep.PROBE_SECONDS, "480p"),
            "full": {res: ep.genjutsu_cost(seconds, res) for res in ("480p", "720p")},
            "note": "per take (count:2 on MCP bills each variant); failed / ip_detected / nsfw runs are refunded"}


@app.command()
def cost(unit: str = typer.Argument(..., metavar="UNIT"),
         choose: Optional[str] = typer.Option(None, help="record the user's answer: probe-first | full | prep-only"),
         resolution: Optional[str] = typer.Option(None, help="final resolution the user picked: 480p | 720p")) -> None:
    """Probe vs full-run cost for this unit (the one question before spending), and record the answer."""
    project = open_project(unit)
    data = project.load()
    video = project.prepared_video if project.prepared_video.exists() else project.source_video
    if not video.exists():
        fail("no video yet — `memegen ingest` first")
    seconds = ff.probe(video).duration
    if not project.prepared_video.exists():  # not prepared yet: the default is the whole clip, max 30 s
        seconds = min(seconds, ep.GENJUTSU_MAX_SECONDS)
    if choose:
        if choose not in RUN_PLANS:
            fail(f"--choose must be one of {list(RUN_PLANS)}")
        data = project.update(run_plan={"plan": choose, "resolution": resolution or "720p"})
    default = load_settings().run_plan
    emit({"ok": True, **_cost_table(seconds), "run_plan": data.get("run_plan"),
          "default_from_env": default, "plans": RUN_PLANS,
          "next": ("ask the user once (meme-video skill: cost question), then "
                   f"`memegen cost {project.root.name} --choose <plan>`") if not data.get("run_plan") and not default
                  else "no question needed — follow run_plan"})


def _ingest(project: Project, source: str, frames: int) -> None:
    try:
        ff.ingest(source, project.source_video)
        info = ff.probe(project.source_video)
        cuts = ff.detect_scenes(project.source_video)
        sheet = cs.reference_sheet(project.source_video, project.analysis_dir / "reference_sheet.jpg", frames, cuts=cuts)
    except ff.ToolError as error:
        fail(str(error), project=str(project.root))
    project.update(source=source, video=info.to_dict(), cuts=cuts)
    project.mark("ingest")
    emit({"ok": True, "unit": str(project.root), "video": info.to_dict(), "cuts": cuts,
          "reference_sheet": str(sheet), "next": "analyze: write 02_analysis/analysis.json, then `memegen prepare`"})


@app.command()
def prepare(project_ref: str = typer.Argument(..., metavar="UNIT")) -> None:
    """Validate 02_analysis/analysis.json, trim + normalize + pad to whole seconds → 01_input/prepared.mp4."""
    from memegen.schemas import Analysis, Mode

    project = open_project(project_ref)
    path = project.analysis_dir / "analysis.json"
    if not path.exists():
        fail(f"{path} missing")
    try:
        analysis = Analysis.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as error:
        fail(f"analysis.json invalid: {error}")
    if not analysis.gate1.passed:
        fail("Gate 1 did not pass — pick another segment or abort", gate1=analysis.gate1.model_dump())
    trimmed = project.input_dir / "trimmed.mp4"
    ff.trim(project.source_video, trimmed, analysis.trim_start, analysis.trim_end)
    clip_seconds = ff.probe(trimmed).duration
    min_px = ep.OBJECT_SWAP_MIN_PIXELS if analysis.mode == Mode.OBJECT_SWAP else 0
    normalized = project.input_dir / "normalized.mp4"
    ff.normalize(trimmed, normalized, min_pixels=min_px)
    ff.pad_to_whole_seconds(normalized, project.prepared_video)  # finalize trims back to clip_seconds
    normalized.unlink()
    info = ff.probe(project.prepared_video)
    sheet = cs.reference_sheet(project.prepared_video, project.analysis_dir / "prepared_sheet.jpg", 12,
                               cuts=ff.detect_scenes(project.prepared_video))
    project.update(clip_seconds=round(clip_seconds, 3))
    project.mark("analyze", mode=analysis.mode.value, trim=[analysis.trim_start, analysis.trim_end])
    emit({"ok": True, "prepared": str(project.prepared_video), "video": info.to_dict(), "sheet": str(sheet),
          "clip_seconds": round(clip_seconds, 3), "padded_to": info.duration,
          "upscaled": info.pixels != ff.probe(trimmed).pixels, "cost": _cost_table(info.duration)})


# ---------------------------------------------------------------------------------------------
PROMPT_FILE = "genjutsu_prompt.txt"          # final prompt, written by Claude (genjutsu-prompt skill)
PROMPT_CHECK = "genjutsu_prompt.check.json"  # what `prompt check` validated it against


def _request(project: Project, mode: Optional[str] = None, extra: str = "", skip_look_gate: bool = False):
    """Image order + skeleton prompt from analysis.json + cast.json (Gate L enforced). Returns (request, problems)."""
    from memegen import assets
    from memegen.genjutsu.prompt import build
    from memegen.schemas import Analysis, Mode

    analysis = Analysis.model_validate_json((project.analysis_dir / "analysis.json").read_text(encoding="utf-8"))
    plan = _load_cast(project)
    problems = plan.look_problems()
    if problems and not skip_look_gate:
        fail("Gate L not passed — every character the look decision dresses needs an approved look before Genjutsu",
             problems=problems)
    try:
        plan, profiles = assets.resolve_plan(plan, analysis, project.root)
        return build(analysis, plan, profiles, Mode(mode) if mode else None, extra), problems
    except (FileNotFoundError, ValueError) as error:
        fail(str(error))


def _images_digest(images: list[str]) -> str:
    h = hashlib.sha256()
    for image in images:
        h.update(image.encode())
        if not image.startswith("http") and Path(image).exists():
            h.update(hashlib.sha256(Path(image).read_bytes()).digest())
    return h.hexdigest()[:16]


def _final_prompt(project: Project, request, allow_draft: bool) -> tuple[str, str]:
    """(prompt, source). Only a prompt that passed `prompt check` for exactly these images may be sent."""
    from memegen.genjutsu.prompt import lint

    path = project.analysis_dir / PROMPT_FILE
    if not path.exists():
        if allow_draft:
            return request.prompt, "draft"
        fail(f"no {PROMPT_FILE} — write it with the genjutsu-prompt skill: `memegen prompt draft {project.root.name}`"
             f" → edit → `memegen prompt check {project.root.name}` (or --draft-prompt to send the skeleton)")
    prompt = path.read_text(encoding="utf-8").strip()
    errors, _ = lint(prompt, len(request.images), request.mode, _real_names(project))
    if errors:
        fail("prompt check failed", errors=errors)
    check = project.analysis_dir / PROMPT_CHECK
    stamp = json.loads(check.read_text(encoding="utf-8")) if check.exists() else {}
    if stamp.get("images") != _images_digest(request.images) or stamp.get("prompt") != _text_digest(prompt):
        fail(f"{PROMPT_FILE} was not checked against the current images/prompt — run `memegen prompt check "
             f"{project.root.name}` again (image order or looks changed since)")
    return prompt, PROMPT_FILE


def _real_names(project: Project) -> list[str]:
    """Names of the public figures being sent: they must never be written into the prompt."""
    from memegen.schemas import Source
    plan = _load_cast(project)
    names = []
    for a in plan.replaced():
        if a.source == Source.PUBLIC_FIGURE and a.character:
            try:
                names.append(assets.load(a.character).name)
            except FileNotFoundError:
                pass
    return names


def _text_digest(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()[:16]


@app.command()
def render(project_ref: str = typer.Argument(..., metavar="UNIT"),
           resolution: Optional[str] = typer.Option(None, help="480p | 720p (default 720p, probe 480p)"),
           mode: Optional[str] = typer.Option(None, help="override: object-swap | motion-transfer"),
           extra: str = typer.Option("", help="extra line appended to the skeleton (draft prompts only)"),
           budget: float = typer.Option(25.0, help="abort if the REST USD cost exceeds this (30 s at 720p = $20.43)"),
           probe: bool = typer.Option(False, help="cheap test: only 4 s of the clip (default 480p) to verify "
                                                  "token binding + identity before the full run"),
           probe_start: float = typer.Option(0.0, help="probe window start (s) in prepared.mp4 — pick the busiest"),
           draft_prompt: bool = typer.Option(False, help="send the skeleton when no checked prompt exists"),
           skip_look_gate: bool = typer.Option(False, help="render without approved looks (recorded in the take)"),
           dry_run: bool = typer.Option(False, help="build + estimate + inputs sheet only: no upload, no submit")) -> None:
    """Send the checked prompt + images to Genjutsu (or --dry-run), download a new take + compare sheet."""
    project = open_project(project_ref)
    request, problems = _request(project, mode, extra, skip_look_gate)
    prompt, prompt_source = _final_prompt(project, request, allow_draft=draft_prompt or dry_run)
    resolution = resolution or ("480p" if probe else "720p")
    for old in project.refs_dir.glob("image*"):  # refs/ always mirrors the latest request only
        old.unlink()
    for n, image in enumerate(request.images, 1):  # keep a copy of exactly what Genjutsu sees, in order
        if not image.startswith("http"):
            shutil.copy2(image, project.refs_dir / f"image{n}_{Path(image).parent.parent.name}_{Path(image).name}")
    video = project.prepared_video
    if probe:
        video = ff.trim(project.prepared_video, project.input_dir / "probe.mp4", probe_start,
                        probe_start + ep.PROBE_SECONDS)
    estimate = {**ep.genjutsu_cost(ff.probe(video).duration, resolution), "probe": probe}
    if estimate["usd"] > budget:
        fail(f"cost ${estimate['usd']} exceeds budget ${budget} — shorten the clip, lower resolution or raise --budget")

    model = ep.GENJUTSU[request.mode.value]
    if dry_run:  # nothing leaves the machine: no uploads, no submit
        request_path = project.analysis_dir / "genjutsu_request.json"
        request_path.write_text(json.dumps({
            "model": model, "mcp_model": ep.GENJUTSU_MCP[request.mode.value], "video": str(video),
            "images": request.images, "prompt": prompt,
            "prompt_source": prompt_source, "resolution": resolution, "estimate": estimate,
            "bindings": request.bindings}, indent=2, ensure_ascii=False), encoding="utf-8")
        sheet = cs.image_sheet([Path(p) for p in request.images if not p.startswith("http")],
                               project.analysis_dir / "genjutsu_inputs.jpg", title="Genjutsu image_urls, in order")
        emit({"ok": prompt_source != "draft", "dry_run": True, "model": model,
              "mcp_model": ep.GENJUTSU_MCP[request.mode.value], "video": str(video), "estimate": estimate,
              "run_plan": project.load().get("run_plan"),
              "bindings": request.bindings, "images": request.images, "prompt": prompt,
              "prompt_source": prompt_source, "request": str(request_path), "inputs_sheet": str(sheet),
              "next": (f"write the final prompt (genjutsu-prompt skill), then `memegen prompt check {project.root.name}`"
                       if prompt_source == "draft" else
                       f"memegen render {project.root.name} --probe  (≈${ep.genjutsu_cost_usd(ep.PROBE_SECONDS, '480p')}"
                       f" / {ep.genjutsu_cost_credits(ep.PROBE_SECONDS, '480p')} credits) then the full run")})
        return

    hf = client()
    uploads = project.load().get("uploads", {})
    video_url = _upload_cached(hf, video, uploads)
    image_urls = [_upload_cached(hf, Path(p), uploads) if not p.startswith("http") else p for p in request.images]
    project.update(uploads=uploads)
    body = {"video_url": video_url, "image_urls": image_urls, "prompt": prompt, "resolution": resolution}

    takes = project.load().get("takes", [])
    take = len(takes) + 1
    ticket = hf.submit(model, body)
    record = {"take": take, "backend": "rest", "request_id": ticket["request_id"], "model": model, "body": body,
              "estimate": estimate,
              "bindings": request.bindings, "images": request.images, "look_gate_skipped": problems or None,
              "prompt_source": prompt_source, "probe": probe}
    project.update(takes=takes + [record])
    log(f"submitted take {take}: {ticket['request_id']}")
    _await_take(project, hf, take)


def _await_take(project: Project, hf: HiggsfieldClient, take: int, timeout: float = 1800.0) -> None:
    """Wait for a submitted take, then download + compare sheet. A timeout never resubmits (that would bill twice):
    the request keeps running on Higgsfield and `memegen take wait` picks it up again."""
    takes = project.load().get("takes", [])
    record = next((t for t in takes if t["take"] == take), None)
    if record is None:
        fail(f"no take {take} in the manifest")

    def save() -> None:
        project.update(takes=[record if t["take"] == take else t for t in project.load().get("takes", [])])

    try:
        result = hf.wait(record["request_id"], timeout=timeout,
                         on_update=lambda r: log(f"  status: {r.get('status')}"))
    except TimeoutError as error:
        record["status"] = hf.status(record["request_id"]).get("status")
        save()
        emit({"ok": False, "take": take, "status": record["status"], "request_id": record["request_id"],
              "error": str(error), "next": f"memegen take wait {project.root.name} --take {take}  (do NOT re-render: "
                                          f"that submits and bills again)"})
        raise typer.Exit(2)
    record["status"] = result.get("status")
    if record["status"] != "completed":
        record["error"] = result.get("error")
        save()
        fail(f"take {take} {record['status']}", result=result)
    out = hf.download(output_urls(result)[0], project.renders_dir / f"take_{take}.mp4")
    record["path"] = str(out)
    save()
    project.add_cost(f"genjutsu take {take}", record.get("estimate"))
    video = project.input_dir / "probe.mp4" if record.get("probe") else project.prepared_video
    sheet = cs.compare_sheet(video, out, project.renders_dir / f"take_{take}_compare.jpg")
    project.mark("render", last_take=take)
    emit({"ok": True, "take": take, "probe": record.get("probe"), "video": str(out), "compare_sheet": str(sheet),
          "next": "Gate 3: review the compare sheet, write 04_renders/take_N_review.json"})


@take_app.command("wait")
def take_wait(unit: str = typer.Argument(..., metavar="UNIT"),
              take: Optional[int] = typer.Option(None, help="take number (default: the last one)"),
              timeout: float = typer.Option(3600.0, help="seconds to keep polling")) -> None:
    """Resume waiting for an already-submitted take (after a timeout or a closed terminal); never resubmits."""
    project = open_project(unit)
    takes = project.load().get("takes", [])
    if not takes:
        fail("no takes submitted yet")
    rest = [t for t in takes if t.get("request_id")]
    if not rest:
        fail("no REST takes to wait for (MCP takes are recorded with `memegen take add`)")
    _await_take(project, client(), take or rest[-1]["take"], timeout)


@take_app.command("status")
def take_status(unit: str = typer.Argument(..., metavar="UNIT")) -> None:
    """Every take in the unit; REST takes also get their live Higgsfield status."""
    project = open_project(unit)
    takes = project.load().get("takes", [])
    hf = client() if any(t.get("request_id") for t in takes) else None
    emit({"ok": True, "takes": [{"take": t["take"], "backend": t.get("backend", "rest"), "probe": t.get("probe"),
                                 "model": t.get("model"), "recorded": t.get("status"),
                                 "live": hf.status(t["request_id"]).get("status") if t.get("request_id") else None,
                                 "estimate": t.get("estimate"), "path": t.get("path")} for t in takes]})


@take_app.command("add")
def take_add(unit: str = typer.Argument(..., metavar="UNIT"),
             video: Optional[str] = typer.Argument(None, help="result mp4 path or URL (omit for a failed job)"),
             model: str = typer.Option(..., help="e.g. hf_mult_motion_control | hf_mult_replace_object"),
             resolution: str = typer.Option(..., help="480p | 720p"),
             job_id: str = typer.Option("", help="MCP job id"),
             status: str = typer.Option("completed", help="completed | failed | nsfw | ip_detected ..."),
             credits: Optional[float] = typer.Option(None, help="credits actually charged (default: price list)"),
             probe: bool = typer.Option(False, help="this was the 4 s probe clip (01_input/probe.mp4)"),
             driving: Optional[Path] = typer.Option(None, help="driving video sent, if not prepared.mp4/probe.mp4"),
             notes: str = typer.Option("", help="what changed in this take")) -> None:
    """Record a take generated outside `render` (Higgsfield MCP): copy/download it to 04_renders/take_N.mp4,
    log model/cost/prompt in the manifest and build the compare sheet — so `finalize` works the same way."""
    import httpx

    project = open_project(unit)
    takes = project.load().get("takes", [])
    take = len(takes) + 1
    sent = driving or (project.input_dir / "probe.mp4" if probe else project.prepared_video)
    seconds = ff.probe(sent).duration if sent.exists() else None
    estimate = {**(ep.genjutsu_cost(seconds, resolution) if seconds else {}), "probe": probe}
    if credits is not None:
        estimate["credits"] = credits
    prompt = project.analysis_dir / PROMPT_FILE
    record = {"take": take, "backend": "mcp", "job_id": job_id, "model": model, "status": status,
              "estimate": estimate, "probe": probe, "driving": str(sent), "notes": notes,
              "prompt": prompt.read_text(encoding="utf-8").strip() if prompt.exists() else None}
    if status != "completed":  # refunded, but worth remembering why
        record["estimate"] = {"refunded": True, "probe": probe}
        project.update(takes=takes + [record])
        emit({"ok": True, "take": take, "status": status, "recorded": True})
        return
    if not video:
        fail("a completed take needs its video (path or URL)")
    out = project.renders_dir / f"take_{take}.mp4"
    if ff.is_url(video):
        with httpx.stream("GET", video, follow_redirects=True, timeout=300) as response:
            response.raise_for_status()
            with out.open("wb") as fh:
                for chunk in response.iter_bytes():
                    fh.write(chunk)
    else:
        shutil.copy2(Path(video).expanduser(), out)
    record["path"] = str(out)
    project.update(takes=takes + [record])
    project.add_cost(f"genjutsu take {take} (mcp)", estimate)
    sheet = cs.compare_sheet(sent, out, project.renders_dir / f"take_{take}_compare.jpg")
    project.mark("render", last_take=take)
    emit({"ok": True, "take": take, "video": str(out), "compare_sheet": str(sheet), "estimate": estimate,
          "output": ff.probe(out).to_dict(),
          "next": "Gate 3: review the compare sheet, write 04_renders/take_N_review.json"})


@app.command()
def finalize(project_ref: str = typer.Argument(..., metavar="UNIT"),
             take: int = typer.Option(..., help="approved take number")) -> None:
    """Restore the reference audio onto the approved take -> 05_final/<slug>.mp4."""
    project = open_project(project_ref)
    generated = project.renders_dir / f"take_{take}.mp4"
    if not generated.exists():
        fail(f"{generated} missing")
    clip_seconds = project.load().get("clip_seconds")  # the real length, without the whole-second padding
    out = ff.restore_audio(generated, project.prepared_video, project.final_dir / f"{project.slug}.mp4",
                           duration=clip_seconds)
    project.mark("finalize", take=take, output=str(out))
    emit({"ok": True, "final": str(out), "video": ff.probe(out).to_dict(), "costs": project.load()["costs"]})


# ---------------------------------------------------------------------------------------------
@sheet_app.command("ref")
def sheet_ref(video: Path, out: Path = typer.Option(...), n: int = 16, cols: int = 4) -> None:
    """Reference video contact sheet (timestamps + cut markers)."""
    emit({"ok": True, "sheet": str(cs.reference_sheet(video, out, n, cols, ff.detect_scenes(video)))})


@sheet_app.command("images")
def sheet_images(paths: list[Path], out: Path = typer.Option(...), cols: int = 4,
                 title: str = typer.Option("", help="sheet title")) -> None:
    """Candidate image sheet with #index labels (Gate 2)."""
    emit({"ok": True, "sheet": str(cs.image_sheet(paths, out, cols, title or None))})


@sheet_app.command("compare")
def sheet_compare(reference: Path, generated: Path, out: Path = typer.Option(...), n: int = 6) -> None:
    """Reference vs generated side-by-side sheet (Gate 3)."""
    emit({"ok": True, "sheet": str(cs.compare_sheet(reference, generated, out, n))})


@app.command()
def frame(video: Path, t: float = typer.Argument(..., help="seconds"),
          out: Optional[Path] = typer.Option(None, help="png path (default: next to the video, frame_<t>.png)"),
          width: int = typer.Option(1280, help="output width in px")) -> None:
    """Save one full-resolution frame to look at (instead of shell ffmpeg + /tmp, which Windows lacks)."""
    dest = out or video.parent / f"frame_{t:.2f}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    emit({"ok": True, "frame": str(ff.extract_frame(video, t, dest, width=width))})


@app.command()
def trash(paths: list[Path] = typer.Argument(..., help="files or folders to move to the OS trash / recycle bin")) -> None:
    """Move old files to the Trash / Recycle Bin (never a permanent delete; same on macOS, Windows, Linux)."""
    from send2trash import send2trash

    moved, missing = [], []
    for path in paths:
        if path.exists():
            send2trash(str(path.resolve()))
            moved.append(str(path))
        else:
            missing.append(str(path))
    emit({"ok": not missing, "trashed": moved, "missing": missing})


@app.command("upload-put")
def upload_put(file: Path, url: str = typer.Argument(..., help="the signed upload_url from MCP media_upload")) -> None:
    """PUT a file to a Higgsfield MCP signed upload URL (the `If-None-Match: *` header is part of the signature).
    Replaces a shell curl command, so it works the same on Windows."""
    import mimetypes

    import httpx

    if not file.exists():
        fail(f"{file} not found")
    mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    response = httpx.put(url, content=file.read_bytes(), headers={"Content-Type": mime, "If-None-Match": "*"},
                         timeout=600)
    emit({"ok": response.status_code < 300, "status": response.status_code, "file": str(file), "content_type": mime,
          "body": response.text[:300] if response.status_code >= 300 else "",
          "next": "media_confirm" if response.status_code < 300 else "fix the upload, then media_confirm"})


@app.command()
def probe(video: Path) -> None:
    """ffprobe summary + detected cuts."""
    emit({"ok": True, "video": ff.probe(video).to_dict(), "cuts": ff.detect_scenes(video)})


# ---------------------------------------------------------------------------------------------
@hf_app.command("upload")
def hf_upload(path: Path) -> None:
    emit({"ok": True, "url": client().upload_file(path)})


@hf_app.command("estimate")
def hf_estimate(model: str, body: str = typer.Argument(..., help="JSON body or @file.json")) -> None:
    emit({"ok": True, "estimate": client().estimate(model, _json_arg(body))})


@hf_app.command("run")
def hf_run(model: str, body: str = typer.Argument(..., help="JSON body or @file.json"),
           download: Optional[Path] = typer.Option(None, help="directory to save outputs")) -> None:
    """Submit any model, wait, optionally download outputs."""
    hf = client()
    try:
        result = hf.run(model, _json_arg(body), on_update=lambda r: log(f"status: {r.get('status')}"))
    except (HFError, GenerationFailed) as error:
        fail(str(error))
    files = []
    if download:
        for i, url in enumerate(output_urls(result)):
            suffix = Path(url.split("?")[0]).suffix or ".bin"
            files.append(str(hf.download(url, download / f"{result['request_id']}_{i}{suffix}")))
    emit({"ok": True, "result": result, "files": files})


@hf_app.command("status")
def hf_status(request_id: str) -> None:
    emit({"ok": True, "result": client().status(request_id)})


# ---------------------------------------------------------------------------------------------
@asset_app.command("new")
def asset_new(slug: str, name: str = typer.Option(...),
              type_: str = typer.Option("fixed", "--type", help="me | fixed | public_figure | generated"),
              species: str = typer.Option("human"), bible: str = typer.Option("", help="stable appearance traits")) -> None:
    """Create a character folder."""
    from memegen import assets
    char = assets.create(slug, name, type_, species, bible)
    emit({"ok": True, "character": char.model_dump(), "dir": str(assets.char_dir(slug))})


@asset_app.command("add")
def asset_add(slug: str, files: list[Path], note: str = typer.Option("", help="where it came from")) -> None:
    """Copy local files (sheets, photos) into the character's source/."""
    from memegen import assets
    emit({"ok": True, "added": [str(assets.add_source(slug, f, note=note)) for f in files]})


@asset_app.command("fetch")
def asset_fetch(slug: str, urls: list[str], page: str = typer.Option(None, help="page the image was found on"),
                license_: str = typer.Option(None, "--license")) -> None:
    """Download web images (found by Claude Code web search) into source/ with provenance, + candidate sheet."""
    from memegen import assets
    saved, errors = [], {}
    for url in urls:
        try:
            saved.append(assets.fetch(slug, url, page, license_))
        except Exception as error:  # keep going: some hosts block hotlinking
            errors[url] = str(error)
    sheet = None
    if saved:  # every candidate collected so far, not just this call's (fetch is often called per URL)
        candidates = sorted((assets.char_dir(slug) / "source").glob("web_*"))
        sheet = cs.image_sheet(candidates, assets.char_dir(slug) / "source" / "candidates_sheet.jpg",
                               title=f"{slug} candidates")
    emit({"ok": bool(saved), "saved": [str(p) for p in saved], "errors": errors, "sheet": str(sheet) if sheet else None})


@asset_app.command("commons")
def asset_commons(name: str = typer.Argument(..., help='exact Commons category name, e.g. "Sam Altman"'),
                  year: list[int] = typer.Option([], help="also search 'Category:<name> in <year>' (repeatable)"),
                  min_side: int = typer.Option(500, help="drop images whose short side is smaller")) -> None:
    """List Wikimedia Commons candidates (title, size, license, thumb url, page) for a public figure.
    Pick single-subject files by provenance, then `asset fetch <slug> <url> --page <page> --license <lic>` each."""
    from memegen import assets
    try:
        found = assets.commons_candidates(name, year, min_side)
    except Exception as error:
        fail(f"commons search failed: {error}")
    emit({"ok": bool(found), "count": len(found), "candidates": found,
          "hint": "prefer files named after the person alone ('X in 2023 (cropped)'); skip group/meeting photos"})


@asset_app.command("crop")
def asset_crop(slug: str, source: Path,
               box: Optional[str] = typer.Option(None, help="x0,y0,x1,y1 in source pixels (omit = whole image)"),
               name: str = typer.Option(...), shot: str = typer.Option(..., help="close-up | medium | full-body"),
               angle: str = typer.Option("front"), expression: str = typer.Option("neutral"),
               description: str = typer.Option(""), tighten: bool = typer.Option(True)) -> None:
    """Cut one single-subject view out of a sheet/photo (or a codex-generated image) into views/<name>.png."""
    from memegen import assets
    from memegen.imagegen.codex import load_sidecar
    coords = tuple(int(v) for v in box.split(",")) if box else None
    origin = f"codex:{source.resolve()}" if load_sidecar(source).get("thread_id") else ""
    out = assets.crop(slug, source, coords, name, shot=shot, angle=angle, expression=expression,
                      description=description, origin=origin, tighten=tighten)
    emit({"ok": True, "view": str(out)})


@asset_app.command("review")
def asset_review(slug: str, file: str, score: Optional[float] = typer.Option(None),
                 usable: Optional[bool] = typer.Option(None), description: Optional[str] = typer.Option(None)) -> None:
    """Record Gate 2 results on a view (score, usable, what the image shows)."""
    from memegen import assets
    assets.describe(slug, file, score=score, usable=usable, description=description)
    emit({"ok": True, "character": assets.load(slug).model_dump()})


@asset_app.command("list")
def asset_list() -> None:
    from memegen import assets
    emit({"ok": True, "characters": [
        {"slug": c.slug, "name": c.name, "type": c.type, "species": c.species,
         "views": [f"{v.file} [{v.shot}/{v.angle}/{v.expression}] score={v.score} usable={v.usable}" for v in c.views]}
        for c in assets.list_all()]})


@asset_app.command("show")
def asset_show(slug: str, sheet: bool = typer.Option(True, help="also render a views contact sheet")) -> None:
    from memegen import assets
    char = assets.load(slug)
    out = None
    if sheet and char.views:
        out = cs.image_sheet([assets.char_dir(slug) / v.file for v in char.views],
                             assets.char_dir(slug) / "views_sheet.jpg", title=f"{char.name} views")
    emit({"ok": True, "character": char.model_dump(), "sheet": str(out) if out else None})


@asset_app.command("pick")
def asset_pick(slug: str, shot: str = typer.Option("medium"), angle: str = typer.Option("front"),
               limit: int = typer.Option(2)) -> None:
    """Which views would be sent to Genjutsu for a reference shot/angle."""
    from memegen import assets
    emit({"ok": True, "picked": [{"path": str(p), **v.model_dump()} for p, v in assets.pick(slug, shot, angle, limit)]})

# ---------------------------------------------------------------------------------------------
@image_app.command("gen")
def image_gen(unit: Optional[str] = typer.Argument(None, metavar="[UNIT]"),
              char: Optional[str] = typer.Option(None, help="instead of a unit: save into assets/characters/<slug>/"
                                                              "source/generated/ (identity material, e.g. a fixed sheet)"),
              prompt: str = typer.Option(..., help="what to generate (pose, outfit, shot, expression...)"),
              name: str = typer.Option(..., help="file stem in 03_assets/generated/"),
              ref: list[str] = typer.Option([], help="repeatable: <slug> (auto-pick views) | <slug>:<view> | file"),
              shot: str = typer.Option("medium", help="for <slug> refs: close-up | medium | full-body"),
              angle: str = typer.Option("front", help="for <slug> refs: front | three-quarter | side | back"),
              n: int = typer.Option(1, min=1, max=4, help="variants, generated in parallel"),
              aspect: str = typer.Option("portrait", help="portrait | landscape | square"),
              clean: bool = typer.Option(True, help="single subject on a plain background (Genjutsu reference)"),
              description: str = typer.Option("", help="what the image shows, for the Genjutsu image legend")) -> None:
    """Generate images with Codex from asset references into the unit's 03_assets/generated/ (+ review sheet)."""
    from memegen import assets
    from memegen.imagegen import codex

    if bool(unit) == bool(char):
        fail("give either a work UNIT or --char <slug>")
    project = open_project(unit) if unit else None
    if char:
        assets.load(char)
        out_dir, logs_dir = assets.char_dir(char) / "source" / "generated", assets.char_dir(char) / "source" / "logs"
    else:
        out_dir, logs_dir = project.generated_dir, project.logs_dir
    try:
        refs = [codex.Ref(path, note) for spec in ref for path, note in assets.refs(spec, shot, angle)]
    except (FileNotFoundError, KeyError, ValueError) as error:
        fail(str(error))
    log(f"codex: generating {n} image(s) from {len(refs)} reference(s) — ~1-2 min each")
    results, errors = codex.generate_many(prompt, refs, out_dir, name, n, aspect=aspect, clean=clean,
                                          description=description, logs_dir=logs_dir)
    if not results:
        fail("codex generated nothing", errors=errors)
    if project:
        project.update(generated=project.load().get("generated", []) + [
            {**r.to_dict(), "file": str(r.file.relative_to(project.root))} for r in results])
    else:
        for r in results:
            assets.record_source(char, r.file, note=f"codex image_gen: {prompt[:200]}")
    sheet = cs.image_sheet([r.path for r in refs] + [r.file for r in results],
                           out_dir / f"{name}_review.jpg",
                           title=f"refs #1-{len(refs)} | generated #{len(refs) + 1}-{len(refs) + len(results)}")
    emit({"ok": True, "generated": [str(r.file) for r in results], "errors": errors, "review_sheet": str(sheet),
          "next": "Gate 2: compare identity with the refs on the review sheet; use it in cast.json as "
                  "'03_assets/generated/<name>.png' or promote with `memegen asset crop <slug> <png> --name ...`"})


# ---------------------------------------------------------------------------------------------
def _load_cast(project: Project):
    from memegen.schemas import CastPlan
    if not project.cast_path.exists():
        fail(f"{project.cast_path} missing — write the cast plan (with a `look` per replaced character) first")
    try:
        return CastPlan.model_validate_json(project.cast_path.read_text(encoding="utf-8"))
    except ValueError as error:
        fail(f"cast.json invalid: {error}")


def _routes(project: Project, plan) -> dict:
    from memegen import router
    from memegen.schemas import Analysis

    path = project.analysis_dir / "analysis.json"
    analysis = Analysis.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None
    return router.summary(router.route_plan(plan, analysis, project.root.name), project.root.name)


@route_app.command("show")
def route_show(unit: str = typer.Argument(..., metavar="UNIT")) -> None:
    """Per replaced character: build_asset / decide / direct (views go straight in) / look (Gate L) + next step."""
    project = open_project(unit)
    emit({"ok": True, **_routes(project, _load_cast(project))})


@route_app.command("decide")
def route_decide(unit: str = typer.Argument(..., metavar="UNIT"),
                 cast: str = typer.Option(..., help="cast id"),
                 body_visible: bool = typer.Option(..., "--body-visible/--no-body-visible",
                                                   help="the target's body/outfit is on screen (not only a face)"),
                 signature_outfit: bool = typer.Option(..., "--signature-outfit/--no-signature-outfit",
                                                       help="the outfit/props ARE the scene"),
                 held_props: bool = typer.Option(..., "--held-props/--no-held-props",
                                                 help="props the motion interacts with (mic, guns, phone, cap)"),
                 dress_up_gag: bool = typer.Option(..., "--dress-up-gag/--no-dress-up-gag",
                                                   help="the payoff is this character dressed as the target"),
                 reason: str = typer.Option(..., help="one line: why")) -> None:
    """Record the binary look decision (look-policy §0): generate a look, or send the views directly."""
    from memegen.schemas import LookDecision

    project = open_project(unit)
    plan = _load_cast(project)
    assignment = next((a for a in plan.replaced() if a.cast_id == cast), None)
    if assignment is None:
        fail(f"no replaced cast member {cast} in cast.json")
    assignment.look_decision = LookDecision(body_visible=body_visible, signature_outfit=signature_outfit,
                                            held_props=held_props, dress_up_gag=dress_up_gag, reason=reason)
    project.cast_path.write_text(plan.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
    routes = _routes(project, plan)
    emit({"ok": True, "cast": cast, "generate": assignment.look_decision.generate,
          "route": next(r for r in routes["routes"] if r["cast_id"] == cast), "next": routes["next"]})


@look_app.command("gen")
def look_gen(unit: str = typer.Argument(..., metavar="UNIT"),
             cast: list[str] = typer.Option([], help="only these cast ids (default: every look not yet approved)"),
             n: Optional[int] = typer.Option(None, min=1, max=4, help="override look.variants")) -> None:
    """Generate look variants with Codex for each replaced character + a review sheet per character."""
    from concurrent.futures import ThreadPoolExecutor

    from memegen import look

    project = open_project(unit)
    plan = _load_cast(project)
    todo = [a for a in plan.replaced() if a.look and (a.cast_id in cast if cast else
                                                    a.needs_look and not (a.look_review and a.look_review.passed))]
    missing = [a.cast_id for a in plan.replaced() if a.needs_look and not a.look]
    direct = [a.cast_id for a in plan.replaced() if not a.needs_look]  # look decision: views go straight in
    if not todo:
        fail("nothing to generate", missing_look=missing, direct_input=direct)
    log(f"codex: looks for {[a.cast_id for a in todo]} — ~1-2 min per image, characters in parallel")
    out = {}
    with ThreadPoolExecutor(max_workers=len(todo)) as pool:
        for a, (results, errors, sheet) in zip(todo, pool.map(lambda a: look.generate(project, a, n), todo)):
            out[a.cast_id] = {"character": a.character, "review_sheet": str(sheet), "errors": errors,
                              "looks": [str(r.file.relative_to(project.root)) for r in results]}
    project.mark("assets", looks={k: v["looks"] for k, v in out.items()})
    emit({"ok": all(v["looks"] for v in out.values()), "looks": out, "missing_look": missing, "direct_input": direct,
          "next": "Gate L: open each review sheet, score identity/outfit/pose/clean (0-10, all >= 7 to pass), then "
                  "`memegen look approve UNIT --cast A --chosen <path> --identity ...`; failed -> fix the look, regen"})


@look_app.command("approve")
def look_approve(unit: str = typer.Argument(..., metavar="UNIT"),
                 cast: str = typer.Option(..., help="cast id"),
                 chosen: str = typer.Option(..., help="unit-relative look path, e.g. 03_assets/looks/A_me_2.png"),
                 identity: float = typer.Option(...), outfit: float = typer.Option(...),
                 pose: float = typer.Option(...), clean: float = typer.Option(...),
                 notes: str = typer.Option("")) -> None:
    """Record the Gate L review in cast.json. Only a passing look (all scores >= 7) unlocks `render`."""
    from memegen.schemas import LookReview

    project = open_project(unit)
    plan = _load_cast(project)
    assignment = next((a for a in plan.assignments if a.cast_id == cast), None)
    if assignment is None or assignment.look is None:
        fail(f"cast {cast} has no look in cast.json")
    if not (project.root / chosen).exists():
        fail(f"{chosen} not found in {project.root.name}")
    review = LookReview(chosen=chosen, identity=identity, outfit=outfit, pose=pose, clean=clean, notes=notes)
    assignment.look_review = review
    if review.passed:
        assignment.images, assignment.image_notes = [], []  # render: [approved look, best close-up]
    project.cast_path.write_text(plan.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
    emit({"ok": review.passed, "cast": cast, "passed": review.passed, "review": review.model_dump(),
          "remaining": plan.look_problems()})


# ---------------------------------------------------------------------------------------------
@prompt_app.command("draft")
def prompt_draft(unit: str = typer.Argument(..., metavar="UNIT"),
                 mode: Optional[str] = typer.Option(None, help="override: object-swap | motion-transfer")) -> None:
    """Image order + legend + four-block skeleton → 02_analysis/genjutsu_prompt.draft.txt (for the skill to refine)."""
    project = open_project(unit)
    request, _ = _request(project, mode)
    draft = project.analysis_dir / "genjutsu_prompt.draft.txt"
    draft.write_text(request.prompt + "\n", encoding="utf-8")
    legend = project.analysis_dir / "genjutsu_prompt.legend.txt"
    legend.write_text("\n".join(request.legend) + "\n", encoding="utf-8")
    sheet = cs.image_sheet([Path(p) for p in request.images if not p.startswith("http")],
                           project.analysis_dir / "genjutsu_inputs.jpg", title="Genjutsu image_urls, in order")
    emit({"ok": True, "mode": request.mode.value, "legend": request.legend, "bindings": request.bindings,
          "draft": str(draft), "inputs_sheet": str(sheet), "draft_prompt": request.prompt,
          "next": f"write 02_analysis/{PROMPT_FILE} (genjutsu-prompt skill), then `memegen prompt check {unit}`"})


@prompt_app.command("check")
def prompt_check(unit: str = typer.Argument(..., metavar="UNIT"),
                 mode: Optional[str] = typer.Option(None, help="override: object-swap | motion-transfer")) -> None:
    """Lint 02_analysis/genjutsu_prompt.txt against the images that will be sent; stamp it if it passes."""
    from memegen.genjutsu.prompt import lint

    project = open_project(unit)
    request, _ = _request(project, mode)
    path = project.analysis_dir / PROMPT_FILE
    if not path.exists():
        fail(f"{path} missing — `memegen prompt draft {unit}` first")
    prompt = path.read_text(encoding="utf-8").strip()
    errors, warnings = lint(prompt, len(request.images), request.mode, _real_names(project))
    if not (project.analysis_dir / "face_gap.md").exists():
        warnings.append("no 02_analysis/face_gap.md — compare the performer's face with the reference first "
                        "(genjutsu-prompt skill §3e); large gaps need contrast sentences")
    stamp = project.analysis_dir / PROMPT_CHECK
    if errors:
        stamp.unlink(missing_ok=True)
    else:
        stamp.write_text(json.dumps({"images": _images_digest(request.images), "prompt": _text_digest(prompt),
                                     "chars": len(prompt), "warnings": warnings}, indent=2), encoding="utf-8")
    emit({"ok": not errors, "errors": errors, "warnings": warnings, "chars": len(prompt),
          "images": len(request.images), "legend": request.legend,
          "next": "fix the errors and check again" if errors else
                  f"memegen render {unit} --dry-run, then --probe (4 s, 480p) before the full run"})


# ---------------------------------------------------------------------------------------------
def _json_arg(value: str) -> dict:
    text = Path(value[1:]).read_text(encoding="utf-8") if value.startswith("@") else value
    return json.loads(text)


def _upload_cached(hf: HiggsfieldClient, path: Path, cache: dict) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest not in cache:
        log(f"uploading {path.name}")
        cache[digest] = hf.upload_file(path)
    return cache[digest]


if __name__ == "__main__":
    sys.exit(app())
