"""Image generation through the Codex CLI (`codex exec` + its built-in image_gen tool, ChatGPT login).

Replaces Higgsfield image models (Qwen/Grok) for every generated image: new views of a character built
from its asset views, outfit/pose variants matching the reference shot, and generic/fictional characters.

How it works: the reference images are attached with `-i`, codex is told to call image_gen once and copy the
result to <out_dir>/<name>.png. Codex always keeps the original under
$CODEX_HOME/generated_images/<thread_id>/, so if the copy step is skipped we take it from there.
Each output gets a <name>.json sidecar (prompt, refs, thread id) next to it.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from memegen.config import load_settings

ASPECTS = {"portrait": "1024x1536 portrait", "landscape": "1536x1024 landscape", "square": "1024x1024 square"}
MAX_PARALLEL = 3

CLEAN_REFERENCE = ("Output rules: exactly one subject, whole subject visible, even soft lighting, plain light "
                   "background, no text, no logos, no watermark, no frame or collage.")


class CodexError(RuntimeError):
    pass


@dataclass
class Ref:
    path: Path
    note: str = ""  # what the image shows; becomes "Image N: ..." in the instruction


@dataclass
class Generated:
    name: str
    file: Path
    prompt: str
    refs: list[dict]
    aspect: str
    thread_id: str | None
    seconds: float
    description: str = ""  # what the image shows (Gate 2), used as the Genjutsu image legend
    created: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return {**asdict(self), "file": str(self.file)}


def codex_home() -> Path:
    return Path(os.getenv("CODEX_HOME") or Path.home() / ".codex")


def instruction(prompt: str, refs: list[Ref], filename: str, aspect: str = "portrait", clean: bool = True) -> str:
    legend = "\n".join(f"- Image {i}: {r.note or 'reference of the subject'}" for i, r in enumerate(refs, 1))
    identity = (
        "Identity rules: the subject must be exactly the same individual as in the reference images — same face "
        "shape, eyes, nose, mouth, hairstyle and hair color, skin tone, body type, fur pattern/markings for animals, "
        "glasses and accessories — and the same rendering style (a photo stays a photo, an illustration stays in "
        "that illustration style). Only change what the request below asks to change."
    ) if refs else ""
    parts = [
        "You are an image-generation worker for a meme video pipeline. Do exactly this and nothing else:",
        f"1. Call the built-in image generation tool (image_gen) exactly once{', passing all attached reference images' if refs else ''}. "
        "Never draw with code, never use the CLI/API fallback, never touch other files.",
        f"2. Copy the generated PNG from $CODEX_HOME/generated_images/... to ./{filename} in the current directory.",
        f"3. Reply with only the absolute path of {filename}.",
        "",
    ]
    if refs:
        parts += ["Attached reference images, in order:", legend, "", identity, ""]
    parts += [f"Canvas: {ASPECTS[aspect]}.", CLEAN_REFERENCE if clean else "", "", "Request:", prompt.strip()]
    return "\n".join(p for p in parts if p is not None)


def generate(prompt: str, refs: list[Ref], out_dir: Path, name: str, *, aspect: str = "portrait",
             clean: bool = True, description: str = "", logs_dir: Path | None = None,
             timeout: float = 900) -> Generated:
    """One codex run -> <out_dir>/<name>.png (+ .json sidecar). Never overwrites: picks name_v2, _v3..."""
    if aspect not in ASPECTS:
        raise ValueError(f"aspect must be one of {list(ASPECTS)}")
    settings = load_settings()
    codex_bin = shutil.which(settings.codex_bin)  # finds codex.cmd on Windows
    if not codex_bin:
        raise CodexError(f"'{settings.codex_bin}' not found — npm i -g @openai/codex && codex login")
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    name = _free_name(out_dir, name)
    dest = out_dir / f"{name}.png"

    cmd = [codex_bin, "exec"]
    for ref in refs:  # -i takes several values, so keep them ahead of the other flags
        if not ref.path.exists():
            raise FileNotFoundError(ref.path)
        cmd += ["-i", str(ref.path.resolve())]
    cmd += ["--json", "--skip-git-repo-check", "--ephemeral", "-s", "workspace-write", "-C", str(out_dir)]
    if settings.codex_model:
        cmd += ["-m", settings.codex_model]
    cmd.append("-")

    started = time.monotonic()
    try:
        run = subprocess.run(cmd, input=instruction(prompt, refs, dest.name, aspect, clean),
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise CodexError(f"codex timed out after {timeout:.0f}s for {name}") from error
    seconds = round(time.monotonic() - started, 1)
    if logs_dir:
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / f"codex_{name}.jsonl").write_text(run.stdout + ("\n# stderr\n" + run.stderr if run.stderr else ""), encoding="utf-8")

    events = _events(run.stdout)
    thread_id = next((e.get("thread_id") for e in events if e.get("type") == "thread.started"), None)
    # Always prefer this thread's own image: with parallel runs sharing $CODEX_HOME, codex sometimes copies the
    # newest image of *another* thread (a different character), so the store under our thread id wins.
    produced = sorted((codex_home() / "generated_images" / (thread_id or "-")).glob("*.png"),
                      key=lambda p: p.stat().st_mtime)
    if produced:
        shutil.copy2(produced[-1], dest)
    if not dest.exists():
        errors = [e.get("message") or e.get("error") for e in events if e.get("type") in ("error", "turn.failed")]
        last = next((e["item"].get("text") for e in reversed(events)
                     if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message"), "")
        raise CodexError(f"codex produced no image for {name} (exit {run.returncode}): "
                         f"{errors or last or run.stderr.strip()[-500:]}")

    result = Generated(name=name, file=dest, prompt=prompt, aspect=aspect, thread_id=thread_id, seconds=seconds,
                       refs=[{"path": str(r.path), "note": r.note} for r in refs], description=description)
    dest.with_suffix(".json").write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def generate_many(prompt: str, refs: list[Ref], out_dir: Path, name: str, n: int = 1,
                  **kwargs) -> tuple[list[Generated], dict[str, str]]:
    """n independent variants in parallel (name_1..name_n). Returns (results, {name: error})."""
    names = [name] if n == 1 else [f"{name}_{i}" for i in range(1, n + 1)]
    for i, candidate in enumerate(names):  # reserve distinct names before the parallel runs start
        names[i] = _free_name(out_dir, candidate, taken=set(names[:i]))
    results, errors = [], {}
    with ThreadPoolExecutor(max_workers=min(n, MAX_PARALLEL)) as pool:
        futures = {pool.submit(generate, prompt, refs, out_dir, nm, **kwargs): nm for nm in names}
        for future, nm in futures.items():
            try:
                results.append(future.result())
            except Exception as error:  # one failed variant shouldn't lose the others
                errors[nm] = str(error)
    return results, errors


def load_sidecar(image: Path) -> dict:
    sidecar = image.with_suffix(".json")
    return json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}


def _free_name(out_dir: Path, name: str, taken: set[str] = frozenset()) -> str:
    candidate, n = name, 2
    while candidate in taken or (out_dir / f"{candidate}.png").exists():
        candidate = f"{name}_v{n}"
        n += 1
    return candidate


def _events(stdout: str) -> list[dict]:
    events = []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
