"""ffmpeg/ffprobe/yt-dlp wrappers: probe, ingest, trim, normalize, scene detection, audio restore."""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from memegen.hf.endpoints import OBJECT_SWAP_MIN_PIXELS


class ToolError(RuntimeError):
    pass


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise ToolError(f"{cmd[0]} failed ({proc.returncode}): {proc.stderr.strip()[-800:]}")
    return proc


def require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise ToolError(f"'{tool}' not found on PATH")
    return path


@dataclass
class VideoInfo:
    path: str
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    vcodec: str

    @property
    def pixels(self) -> int:
        return self.width * self.height

    def to_dict(self) -> dict:
        return asdict(self) | {"pixels": self.pixels}


def probe(path: str | Path) -> VideoInfo:
    out = _run([
        "ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path),
    ]).stdout
    data = json.loads(out)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        raise ToolError(f"{path} has no video stream")
    num, _, den = video.get("avg_frame_rate", "0/1").partition("/")
    fps = float(num) / float(den) if float(den or 0) else 0.0
    duration = float(data["format"].get("duration") or video.get("duration") or 0)
    # rotation metadata (phone footage) swaps displayed width/height
    rotation = 0
    for side in video.get("side_data_list", []) or []:
        rotation = int(side.get("rotation", rotation) or 0)
    width, height = int(video["width"]), int(video["height"])
    if abs(rotation) in (90, 270):
        width, height = height, width
    return VideoInfo(
        path=str(path), duration=duration, width=width, height=height, fps=round(fps, 3),
        has_audio=any(s["codec_type"] == "audio" for s in data["streams"]), vcodec=video.get("codec_name", ""),
    )


def is_url(source: str) -> bool:
    return bool(re.match(r"^https?://", source))


def ingest(source: str, dest: Path) -> Path:
    """Copy a local file or download a URL (YouTube/TikTok/X/...) to dest (mp4)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if is_url(source):  # yt-dlp is a dependency: run it with this interpreter, no PATH lookup (Windows-safe)
        _run([
            sys.executable, "-m", "yt_dlp", "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
            "--merge-output-format", "mp4", "--no-playlist", "-o", str(dest), source,
        ])
    else:
        src = Path(source).expanduser()
        if not src.exists():
            raise ToolError(f"{src} does not exist")
        if src.suffix.lower() == ".mp4":
            shutil.copy2(src, dest)
        else:  # transcode anything else to mp4
            _run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-c:v", "libx264", "-c:a", "aac", str(dest)])
    return dest


def trim(src: Path, dest: Path, start: float, end: float) -> Path:
    """Frame-accurate trim (re-encode) to [start, end]."""
    if end <= start:
        raise ToolError(f"invalid trim range {start}–{end}")
    _run([
        "ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dest),
    ])
    return dest


def scale_for_min_pixels(width: int, height: int, min_pixels: int = OBJECT_SWAP_MIN_PIXELS) -> tuple[int, int]:
    """Smallest even-sized upscale (same aspect) with width*height >= min_pixels; unchanged if already big enough."""
    if width * height >= min_pixels:
        return width - width % 2, height - height % 2
    factor = (min_pixels / (width * height)) ** 0.5
    w, h = int(width * factor + 0.999), int(height * factor + 0.999)
    w, h = w + w % 2, h + h % 2
    return w, h


def normalize(src: Path, dest: Path, *, min_pixels: int = OBJECT_SWAP_MIN_PIXELS) -> Path:
    """H.264/yuv420p/AAC MP4, upscaled (lanczos) if below Genjutsu object-swap's per-frame pixel minimum."""
    info = probe(src)
    w, h = scale_for_min_pixels(info.width, info.height, min_pixels)
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", f"scale={w}:{h}:flags=lanczos,setsar=1",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dest),
    ])
    return dest


def pad_to_whole_seconds(src: Path, dest: Path) -> Path:
    """Clone the last frame (and pad silence) up to the next whole second.

    Genjutsu bills whole seconds anyway and returns about floor(seconds) of video, so a 12.04 s clip sent as-is
    comes back ~12.0 s and loses its ending. Padded to 13 s it comes back long enough; `finalize` trims it back.
    """
    info = probe(src)
    extra = math.ceil(round(info.duration, 2)) - info.duration
    if extra < 0.01:
        shutil.copy2(src, dest)
        return dest
    audio = ["-af", f"apad=pad_dur={extra:.3f}", "-c:a", "aac", "-b:a", "192k"] if info.has_audio else ["-an"]
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(src),
        "-vf", f"tpad=stop_mode=clone:stop_duration={extra:.3f}", *audio,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
        "-t", f"{info.duration + extra:.3f}", "-movflags", "+faststart", str(dest),
    ])
    return dest


def detect_scenes(path: Path, threshold: float = 0.35) -> list[float]:
    """Timestamps (s) of hard cuts, via ffmpeg's scene score."""
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-vf", f"select='gt(scene,{threshold})',showinfo",
         "-an", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return [round(float(t), 3) for t in re.findall(r"pts_time:([0-9.]+)", proc.stderr)]


def extract_frame(video: Path, t: float, dest: Path, width: int = 480) -> Path:
    _run([
        "ffmpeg", "-y", "-v", "error", "-ss", f"{max(t, 0):.3f}", "-i", str(video), "-frames:v", "1",
        "-vf", f"scale={width}:-2", str(dest),
    ])
    return dest


def restore_audio(generated: Path, audio_source: Path, dest: Path, duration: float | None = None) -> Path:
    """Put the (trimmed) reference audio back onto the generated video and cut to `duration` (the clip's real
    length, dropping the whole-second padding). Audio shorter than the video is padded with silence instead of
    cutting the video (`-shortest` used to do that). Without a cut the video stream is copied untouched."""
    length = duration or probe(generated).duration
    video_codec = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p"] if duration \
        else ["-c:v", "copy"]
    audio = ["-i", str(audio_source), "-map", "0:v:0", "-map", "1:a:0", "-af", "apad", "-c:a", "aac", "-b:a", "192k"] \
        if probe(audio_source).has_audio else ["-map", "0:v:0"]
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(generated), *audio, *video_codec, "-t", f"{length:.3f}",
          "-movflags", "+faststart", str(dest)])
    return dest
