"""Phase 0 spike — answer what the Higgsfield docs don't say, record results in docs/findings.md.

Experiments:
  swap1      object-swap, 1 image                         -> baseline quality/latency/cost
  motion1    motion-transfer, 1 image                     -> baseline
  swap2      object-swap, 2 images, prompt binds image 2 to the LEFT person and image 1 to the RIGHT
             -> does Genjutsu follow the prompt's "image N" references, or just image order / position?
  cuts       object-swap on a clip with a hard cut        -> does identity survive cuts?

Usage:
  python scripts/spike_genjutsu.py --video one_person.mp4 \
      --image-a assets/characters/me/views/hero.png \
      [--video2 two_people.mp4 --image-b other.png] [--video-cuts cut_clip.mp4] \
      [--only swap1,motion1] [--yes]
Without --yes it only prints the plan + USD cost (no credits spent).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from memegen.config import load_settings  # noqa: E402
from memegen.hf import endpoints as ep  # noqa: E402
from memegen.hf.client import HiggsfieldClient, output_urls  # noqa: E402
from memegen.video import contact_sheet as cs  # noqa: E402
from memegen.video import ffmpeg as ff  # noqa: E402

PRESERVE = "Keep the background, camera motion, lighting and timing exactly as in the source video."


def prepare_video(src: Path, out_dir: Path, name: str) -> Path:
    info = ff.probe(src)
    clip = src
    if info.duration > ep.GENJUTSU_MAX_SECONDS:
        clip = ff.trim(src, out_dir / f"{name}_trim.mp4", 0, 10)
    return ff.normalize(clip, out_dir / f"{name}_prepared.mp4")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video", type=Path, required=True, help="clip with ONE clear person (4-30s)")
    parser.add_argument("--image-a", type=Path, required=True, help="identity image A (e.g. you)")
    parser.add_argument("--video2", type=Path, help="clip with TWO people, left and right")
    parser.add_argument("--image-b", type=Path, help="identity image B (clearly different person)")
    parser.add_argument("--video-cuts", type=Path, help="clip with at least one hard cut")
    parser.add_argument("--resolution", default="720p")
    parser.add_argument("--only", default="", help="comma list of experiments")
    parser.add_argument("--yes", action="store_true", help="actually submit (spends credits)")
    args = parser.parse_args()

    settings = load_settings()
    if not settings.hf_key:
        print("HF_KEY missing (.env)")
        return 1
    hf = HiggsfieldClient(settings.hf_key)
    out_dir = ROOT / "scripts" / "out" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, args.only.split(",")))

    def up(path: Path) -> str:
        print(f"  upload {path.name}")
        return hf.upload_file(path)

    video1 = prepare_video(args.video, out_dir, "v1")
    url_v1, url_a = up(video1), up(args.image_a)
    experiments: list[tuple[str, str, dict, Path | None]] = []  # (name, model, body, reference video)

    experiments.append(("swap1", ep.GENJUTSU_OBJECT_SWAP, {
        "video_url": url_v1, "image_urls": [url_a],
        "prompt": f"Replace the main person with the person shown in image 1. {PRESERVE}",
        "resolution": args.resolution}, video1))
    experiments.append(("motion1", ep.GENJUTSU_MOTION_TRANSFER, {
        "video_url": url_v1, "image_urls": [url_a],
        "prompt": "The person in image 1 performs exactly the motion of the person in the source video.",
        "resolution": args.resolution}, video1))
    if args.video2 and args.image_b:
        video2 = prepare_video(args.video2, out_dir, "v2")
        url_v2, url_b = up(video2), up(args.image_b)
        experiments.append(("swap2", ep.GENJUTSU_OBJECT_SWAP, {
            "video_url": url_v2, "image_urls": [url_a, url_b],
            "prompt": ("Replace the person on the LEFT with the person shown in image 2. "
                       "Replace the person on the RIGHT with the person shown in image 1. " + PRESERVE),
            "resolution": args.resolution}, video2))
    if args.video_cuts:
        video3 = prepare_video(args.video_cuts, out_dir, "v3")
        experiments.append(("cuts", ep.GENJUTSU_OBJECT_SWAP, {
            "video_url": up(video3), "image_urls": [url_a],
            "prompt": f"Replace the main person in every shot with the person shown in image 1. {PRESERVE}",
            "resolution": args.resolution}, video3))
    if only:
        experiments = [e for e in experiments if e[0] in only]

    results: dict[str, dict] = {}
    print("\nPlan:")
    total = 0.0
    for name, model, body, ref_video in experiments:
        usd = ep.genjutsu_cost_usd(ff.probe(ref_video).duration, body["resolution"])
        total += usd
        results[name] = {"model": model, "body": body, "estimate_usd": usd}
        print(f"  {name:8s} {model:45s} ${usd}")
    print(f"  total ${total:.2f}")
    if not args.yes:
        print("\nDry run. Re-run with --yes to submit.")
        (out_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        return 0

    tickets = {}
    for name, model, body, _ in experiments:
        tickets[name] = hf.submit(model, body)["request_id"]
        results[name]["request_id"] = tickets[name]
        results[name]["submitted_at"] = time.time()
        print(f"submitted {name}: {tickets[name]}")

    for name, model, body, ref_video in experiments:
        result = hf.wait(tickets[name], on_update=lambda r, n=name: print(f"  {n}: {r.get('status')}"))
        entry = results[name]
        entry["status"], entry["seconds"] = result.get("status"), round(time.time() - entry["submitted_at"], 1)
        entry["error"] = result.get("error")
        files = []
        for i, url in enumerate(output_urls(result)):
            suffix = Path(url.split("?")[0]).suffix or ".bin"
            files.append(str(hf.download(url, out_dir / f"{name}_{i}{suffix}")))
        entry["files"] = files
        if ref_video and files:
            entry["output_video"] = ff.probe(Path(files[0])).to_dict()
            entry["compare_sheet"] = str(cs.compare_sheet(ref_video, Path(files[0]), out_dir / f"{name}_compare.jpg"))
        print(f"{name}: {entry['status']} in {entry['seconds']}s -> {files}")

    (out_dir / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nResults: {out_dir / 'results.json'}  — review the *_compare.jpg sheets and fill docs/findings.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
