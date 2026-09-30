---
name: meme-video
description: End-to-end driver for the meme video generator (reference video + characters → Higgsfield Genjutsu swap → final mp4) — one work unit per meme under work/, stage by stage with the review gates (Gate 1 clip, Gate 2 assets, Gate L looks, prompt check, Gate 3 output), one cost question before spending (4 s test first or straight to the full run), resuming from `memegen status`. Use this whenever the user hands over a reference clip or URL and wants people swapped for themselves, their pet or celebrities, says "밈 만들어줘", "이 영상에 나 넣어줘", "이어서 해줘", asks where a meme project stands or what it will cost, or wants everything set up "genjutsu 직전까지".
---

# Meme video (orchestrator)

> Run every `memegen …` below as `uv run memegen …` — the same on Windows, macOS and Linux. No shell-only commands: `memegen frame` for frames, `memegen trash` instead of deleting, `memegen upload-put` for MCP uploads, temporary files inside the work unit (never `/tmp`).

`memegen` (Python) is the hands, you are the brain: you watch, decide, review and write the JSON/prompt files;
the CLI validates them and does the deterministic work. Every command prints JSON. Each meme is one work unit
`work/<YYYYMMDD-HHMM>-<slug>/` (01_input … 05_final, logs, README.md, manifest.json);
`memegen status <unit>` tells you where it stopped — start there when resuming.

## How much to ask: exactly one question, about money
People hate being asked at every step, and long runs happen while they're away. So decide everything yourself
(clip, casting, mode, looks, prompt, retries) and record why in the unit files. The **only** question is the
cost question below, asked **once per unit, right after ingest** (the duration is known then, nothing is paid
yet, and the user is usually still at the keyboard). After the answer, run to the end without asking again.

Before anything, read the user's memory (saved by the meme-onboarding skill): their own character slug and bible
(height, build, face rules), default run plan, default resolution and what to do with a second person. Use them
for casting and the cost step without asking. No `me` character (`doctor.onboarded: false`) → run meme-onboarding
first (it's short), then come back.

Skip the question when the answer already exists:
- `memegen cost <unit>` shows `run_plan` (recorded earlier) or `default_from_env` (`MEMEGEN_RUN_PLAN` in `.env`), or
- the user's memory holds a default ("always probe first" / "always full") — record it with `--choose`, or
- the user already said it ("바로 돌려", "테스트 먼저", "genjutsu 직전까지", "묻지 말고 끝까지" = full), or
- it's a batch of several units: ask once for the whole batch, not per unit.

Ask with AskUserQuestion, numbers from `memegen cost <unit>` (show REST $ if `HF_KEY` is set, else MCP credits):

> **"<slug> (<N>초) 생성 방식을 골라 주세요"**
> 1. **테스트 먼저 (추천)** — 영상에서 4초만 잘라 480p로 한 번 (≈$1.27 / 12 크레딧). 결과가 괜찮으면 묻지 않고 바로 전체 생성으로 넘어갑니다.
> 2. **바로 전체 생성** — 원본 전체 <N>초, 720p (≈$X / Y 크레딧). 테스트를 건너뛰어 더 빠르지만, 교체가 틀리면 그 비용을 다시 씁니다.
> 3. **생성 직전까지만** — 분석·캐스팅·프롬프트까지 준비하고 멈춥니다 (비용 0).

Record it: `memegen cost <unit> --choose probe-first|full|prep-only [--resolution 480p]` (an "Other" answer like
"480p로 전체" → `--choose full --resolution 480p`). Then tell the user in one line that you'll report at the end.

## Stages
| # | Stage | Do | Gate / output |
|---|---|---|---|
| 0 | doctor | `memegen doctor`: ffmpeg required; `generation` says REST (`HF_KEY`) or MCP | fix what's missing first |
| 1 | new + ingest | `memegen new <slug> --brief "…" --source <video/URL>` | `02_analysis/reference_sheet.jpg` |
| 1b | **cost question** | `memegen cost <unit>` → ask once (above) → `--choose` | `run_plan` in the manifest |
| 2 | analyze | Watch it: reference sheet + full-res frames (and `/watch` if installed). Write `02_analysis/analysis.json`: **trim = the whole clip** (0 → duration, max 30 s; trim only if the user asks or the source is > 30 s), cuts, cast, mode, risks, Gate 1 | `memegen prepare <unit>` → prepared.mp4 (padded to whole seconds) |
| 3 | cast | Map the brief to characters in `02_analysis/cast.json` (asset / public_figure / keep). Missing character → meme-character skill | characters exist, views reviewed (Gate 2) |
| 4 | route + looks | `memegen route show <unit>`: build_asset → decide → **direct** (default) or **look** (meme-look skill). Repeat until `ready` | Gate L for look routes |
| 5 | prompt | genjutsu-prompt skill: face gap → draft → write → `memegen prompt check` | stamped prompt |
| 6 | dry-run | `memegen render <unit> --dry-run` (add `--probe --probe-start <s>` for the test) | request + inputs sheet; `prep-only` stops here and reports |
| 7 | probe → render | per `run_plan`, via REST or MCP (`docs/references/generation-backends.md`) | `04_renders/take_N.mp4` + compare sheet |
| 8 | QA | Gate 3 on the compare sheet + face crops next to the identity image. Write `04_renders/take_N_review.json`; fix the cause (genjutsu-prompt failure table) | approved take |
| 9 | finalize | `memegen finalize <unit> --take N` (original audio back, cut to the real length) | `05_final/<slug>.mp4` + report |

### Stage 7 by plan
Backend: REST (`memegen render`) when `HF_KEY` is set, otherwise the Higgsfield MCP connector; the user can ask
for either. MCP jobs are recorded with `memegen take add` so costs, Gate 3 and finalize work the same way.

- **probe-first**: pick the 4 s with the biggest face, the most swapped people and ideally a cut. If the mode is
  genuinely unclear (see below), run **both modes on the same 4 s** (2 × 12 credits) and keep the winner.
  Probe right → full run immediately, no question. Probe wrong → fix one cause, re-probe once; still wrong →
  full run with the best setup and say so in the report (or stop if nothing plausible is left).
- **full**: straight to the full run. If it fails Gate 3, you may re-take (fix one cause per take).
- **Retry budget**: at most 3 full takes per unit unless the user allows more. Never repeat the same failure
  with the same inputs. Whatever happens, finalize the best take so the user never gets nothing.
- Remember: a good 4 s probe does not guarantee the full run (long shots where the face gets small can drift back
  to the original face). Judge the full take on its own.

## Judgement that matters (learned on real runs)
- **Mode.** Object-swap keeps the *source actor's* face geometry (jaw, cheeks, head size) no matter the prompt,
  resolution or images. Motion-transfer is the mode where the face shape follows the reference; it redraws the
  scene (slightly different light/colours, other people get redrawn too), so name what must stay.
  Default: **motion-transfer for visible faces**. Object-swap when the source face already resembles the new
  person, faces are small, the job is mostly an object/prop swap, or unswapped people must stay pixel-exact
  (a high-quality single-person clip with a car swap won with object-swap).
- **Casting.** One or two swapped people is realistic; tiny background faces rarely swap. The user's own
  character (type `me`) is the main role unless they say otherwise. Describe each target by what is *visible*
  (seat, cap, sweater) — the same words become the prompt's binding cues.
- **Identity image.** One clean multi-view sheet of the same person (several angles, little text) as the single
  identity image beat a stack of separate views in motion-transfer; a stack of selfies widened the face, and a
  selfie's shirt leaked into the outfit. Keep images per person to 1–2.
- **Face gap.** A big difference between the performer and the new person (sex, hair, glasses, beard, jaw)
  leaks through unless the prompt names it — genjutsu-prompt §3e.
- **Geometry beats wording.** "Taller", "slimmer face" in the prompt barely work in motion-transfer, because it
  follows the driving video's shapes. When height or face width matters, edit the driving video instead
  (`docs/references/driving-video-fixes.md`): warp heights apart, squeeze a face horizontally.
- **Never send crops of the source's own people** as images (`ip_detected`), never write real names.
- **Honesty at every gate**: borderline is not a pass. Say what's still wrong in the report.
- **Show, don't tell**: send the compare sheet / face crops / final mp4 (SendUserFile) with one line on what to
  look at. Record decisions in the unit (JSON, review notes, `take add --notes`) — the next session resumes
  from files.

## Report at the end (Korean, short)
Per unit: final path, mode, takes and cost (REST $ or credits, from `memegen take status`), Gate 3 scores and the
remaining problems, plus one line on what you decided without asking and why.
