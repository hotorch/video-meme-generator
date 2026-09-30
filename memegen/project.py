"""One meme video = one work unit: work/<YYYYMMDD-HHMM>-<slug>/ with a fixed scaffold + resumable manifest.

Every unit has exactly the same layout (SCAFFOLD), so any step, person or agent can find things by path:

    README.md            what this unit is, the scaffold, where it stopped (regenerated on every stage)
    manifest.json        name, brief, stages done, costs, takes, generated images, upload cache
    01_input/            source.mp4 (as ingested) · trimmed.mp4 · prepared.mp4 (what Genjutsu gets)
    02_analysis/         reference_sheet.jpg · analysis.json · cast.json · prepared_sheet.jpg
    03_assets/refs/      copies of the character views sent to Genjutsu for this unit
    03_assets/looks/     per cast member: outfit ref cut from the video + codex looks + review sheet (Gate L)
    03_assets/generated/ other codex-generated images (<name>.png + <name>.json: prompt, refs, thread id)
    04_renders/          take_N.mp4 · take_N_compare.jpg · take_N_review.json
    05_final/            <slug>.mp4 (audio restored) · report.md
    logs/                raw codex / API logs
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

STAGES = ["ingest", "analyze", "cast", "assets", "render", "qa", "finalize"]

SCAFFOLD = {
    "01_input": "source.mp4 (as ingested) · trimmed.mp4 · prepared.mp4 (what Genjutsu gets)",
    "02_analysis": "reference_sheet.jpg · analysis.json · cast.json · prepared_sheet.jpg",
    "03_assets/refs": "copies of the character views sent to Genjutsu for this unit",
    "03_assets/looks": "per cast member: outfit ref from the video, codex look variants, review sheet (Gate L)",
    "03_assets/generated": "other codex-generated images: <name>.png + <name>.json (prompt, refs, thread id)",
    "04_renders": "take_N.mp4 · take_N_compare.jpg · take_N_review.json",
    "05_final": "<slug>.mp4 (audio restored) · report.md",
    "logs": "raw codex / API logs",
}


def slugify(text: str, fallback: str = "meme") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or fallback


class Project:
    def __init__(self, root: Path):
        self.root = root

    # layout (keep in sync with SCAFFOLD)
    @property
    def manifest_path(self) -> Path: return self.root / "manifest.json"
    @property
    def input_dir(self) -> Path: return self.root / "01_input"
    @property
    def analysis_dir(self) -> Path: return self.root / "02_analysis"
    @property
    def assets_dir(self) -> Path: return self.root / "03_assets"
    @property
    def refs_dir(self) -> Path: return self.assets_dir / "refs"
    @property
    def looks_dir(self) -> Path: return self.assets_dir / "looks"
    @property
    def generated_dir(self) -> Path: return self.assets_dir / "generated"
    @property
    def cast_path(self) -> Path: return self.analysis_dir / "cast.json"
    @property
    def renders_dir(self) -> Path: return self.root / "04_renders"
    @property
    def final_dir(self) -> Path: return self.root / "05_final"
    @property
    def logs_dir(self) -> Path: return self.root / "logs"
    @property
    def source_video(self) -> Path: return self.input_dir / "source.mp4"
    @property
    def prepared_video(self) -> Path: return self.input_dir / "prepared.mp4"
    @property
    def slug(self) -> str: return self.root.name.split("-", 2)[-1]

    @classmethod
    def create(cls, work_dir: Path, name: str, brief: str = "") -> "Project":
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
        root = work_dir / f"{stamp}-{slugify(name)}"
        n = 2
        while root.exists():
            root = work_dir / f"{stamp}-{slugify(name)}-{n}"
            n += 1
        project = cls(root)
        project.ensure_scaffold()
        project.save({"name": name, "brief": brief, "created": dt.datetime.now().isoformat(timespec="seconds"),
                      "stages": {}, "costs": [], "takes": [], "generated": []})
        return project

    @classmethod
    def open(cls, path: str | Path, work_dir: Path | None = None) -> "Project":
        candidate = Path(path)
        if not candidate.exists() and work_dir is not None:
            matches = sorted(work_dir.glob(f"*{path}*"))
            if len(matches) == 1:
                candidate = matches[0]
            elif len(matches) > 1:
                raise FileNotFoundError(f"'{path}' matches several units: {[m.name for m in matches]}")
        if not (candidate / "manifest.json").exists():
            raise FileNotFoundError(f"no work unit at {path}")
        project = cls(candidate.resolve())
        project.ensure_scaffold()
        return project

    @classmethod
    def list_all(cls, work_dir: Path) -> list["Project"]:
        return [cls(p.parent) for p in sorted(work_dir.glob("*/manifest.json"))]

    def ensure_scaffold(self) -> None:
        for sub in SCAFFOLD:
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def save(self, data: dict[str, Any]) -> None:
        self.manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self.write_readme(data)

    def update(self, **fields: Any) -> dict[str, Any]:
        data = self.load()
        data.update(fields)
        self.save(data)
        return data

    def mark(self, stage: str, **info: Any) -> None:
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage}")
        data = self.load()
        data["stages"][stage] = {"done": dt.datetime.now().isoformat(timespec="seconds"), **info}
        self.save(data)

    def add_cost(self, what: str, estimate: dict | None) -> None:
        data = self.load()
        data["costs"].append({"what": what, **(estimate or {})})
        self.save(data)

    def next_stage(self) -> str | None:
        done = self.load()["stages"]
        return next((s for s in STAGES if s not in done), None)

    def status(self) -> dict[str, Any]:
        data = self.load()
        files = {sub: sorted(p.name for p in (self.root / sub).iterdir() if not p.name.startswith("."))
                 for sub in SCAFFOLD if (self.root / sub).exists()}
        return {"unit": str(self.root), "name": data["name"], "brief": data.get("brief", ""),
                "stages_done": list(data["stages"]), "next": self.next_stage(),
                "takes": len(data.get("takes", [])), "generated": len(data.get("generated", [])), "files": files}

    def write_readme(self, data: dict[str, Any]) -> None:
        stages = "\n".join(f"- [{'x' if s in data['stages'] else ' '}] {s}" for s in STAGES)
        layout = "\n".join(f"| `{sub}/` | {what} |" for sub, what in SCAFFOLD.items())
        (self.root / "README.md").write_text(
            f"# {data['name']}\n\n"
            f"> {data.get('brief') or '(no brief)'}\n\n"
            f"created {data.get('created', '')} · unit `{self.root.name}`\n\n"
            f"## Progress\n{stages}\n\n"
            f"## Layout\n| folder | contents |\n|---|---|\n{layout}\n\n"
            f"Resume: `memegen status {self.root.name}` (this file is regenerated from manifest.json).\n", encoding="utf-8")
