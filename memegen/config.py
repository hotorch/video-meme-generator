"""Paths and credentials. Everything is resolved relative to MEMEGEN_HOME (default: cwd)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def home() -> Path:
    return Path(os.getenv("MEMEGEN_HOME") or Path.cwd()).resolve()


@dataclass(frozen=True)
class Settings:
    home: Path
    hf_key: str | None
    codex_bin: str = "codex"
    codex_model: str | None = None  # None = whatever ~/.codex/config.toml says
    run_plan: str | None = None     # probe-first | full | prep-only: answers the cost question for every unit

    @property
    def work_dir(self) -> Path:
        """One sub-folder per meme video (see memegen/project.py SCAFFOLD)."""
        return self.home / "work"

    @property
    def assets_dir(self) -> Path:
        return self.home / "assets" / "characters"


def load_settings() -> Settings:
    root = home()
    load_dotenv(root / ".env")
    key = os.getenv("HF_KEY")
    if not key and os.getenv("HF_API_KEY") and os.getenv("HF_API_SECRET"):
        key = f"{os.environ['HF_API_KEY']}:{os.environ['HF_API_SECRET']}"
    return Settings(
        home=root,
        hf_key=key or None,
        codex_bin=os.getenv("MEMEGEN_CODEX_BIN") or "codex",
        codex_model=os.getenv("MEMEGEN_CODEX_MODEL") or None,
        run_plan=os.getenv("MEMEGEN_RUN_PLAN") or None,
    )
