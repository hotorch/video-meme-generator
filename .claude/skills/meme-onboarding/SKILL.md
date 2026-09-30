---
name: meme-onboarding
description: First-time setup course for the meme generator — check the install and the Higgsfield connection, register the user's own character (photos or a character sheet → assets/characters/<slug>, type me) plus optional pets, friends and props, ask their few standing preferences once, and save them to Claude's memory and .env so later memes run without questions. Use this when `memegen doctor` shows `onboarded: false` (no `me` character yet), when the user is new ("처음이에요", "온보딩 해줘", "어떻게 시작해요", "세팅해줘"), wants to register or replace their own face/character, their pet or a friend ("내 사진 등록", "우리 고양이도 넣고 싶어"), or wants to change their saved defaults.
---

# Meme onboarding (one-time course)

> Run every `memegen …` below as `uv run memegen …` — the same on Windows, macOS and Linux. No shell-only
> commands: `memegen trash` instead of deleting, temporary files inside the repo (never `/tmp`).

Goal: after about 10 minutes the user has (1) a working install and generation backend, (2) their own
character in the **global asset library** `assets/characters/`, reused by every meme, and (3) their standing
preferences remembered, so the next "이 영상에 나 넣어줘" needs at most the one cost question — or none.

Assets are personal: everything under `assets/` is gitignored and never leaves the machine except as Genjutsu
inputs. Say so once when asking for photos. Speak Korean, plainly; the user may be a beginner.

## Course (5 steps, show progress as "1/5 …")
**1/5 설치 확인** — `memegen doctor`. Fix every `false` among ffmpeg/ffprobe with the `hints` for its `os`
(Windows: `winget …`, then a new terminal). Codex is optional (only for dressing characters); mention it once.

**2/5 영상 생성 연결** — `doctor.generation` tells which backend is ready. Neither ready → explain the two options
from README "API 연결" in three lines (MCP connector = subscription credits, recommended; REST key = pay as you
go) and wait until one works. MCP check: call the Higgsfield `balance` tool. Don't continue without a backend
unless the user wants to prepare only.

**3/5 내 캐릭터 등록** — ask for their photos or character sheet (drag the files in, or paste paths).
Best input: one large frontal face photo + one clean multi-view sheet (or 3–5 photos: front, 3/4, side, full
body), only them in frame, no sunglasses/masks. Then follow the meme-character skill, part A:
- `memegen asset new me --name "<their name or nickname>" --type me --species human`
- `memegen asset add me <files>` → crop single views (`asset crop`; a clean multi-view sheet whole) →
  `memegen asset show me` → **send them the views sheet** and ask "이게 본인 맞나요?" only if something looks off.
- Bible = identity traits only. Ask for what photos can't show and users care most about: **height and build**
  (e.g. "185 cm, slim, long legs") and anything they're sensitive about (face shape). Their words are ground truth
  and go verbatim into the bible — these drive every later prompt and review.
- Review each view (Gate 2, ≥ 7) with `memegen asset review`.

**4/5 더 넣고 싶은 캐릭터 (선택)** — one question: pets, friends, props they'll reuse? For each:
- pet → `--type fixed --species cat|dog …`, same crop flow;
- a friend → only with that person's consent; `--type fixed`;
- a public figure → collected photos only (meme-character part C), never generated; parody use;
- a prop (car, product) → `assets/props/<slug>/`.
Skip entirely if they say no — it can be done any time later.

**5/5 기본 설정 저장** — ONE AskUserQuestion call with these three questions (the only questions of the course
besides the photos and height):
1. **생성 방식 기본값**: "매번 물어보기 (추천)" / "항상 4초 테스트 먼저" / "항상 바로 전체"
2. **해상도 기본값**: "720p (선명, 초당 7 크레딧·$0.68)" / "480p (싸게, 초당 3 크레딧·$0.32)"
3. **두 번째 인물이 필요할 때**: "원본 그대로 두기 (추천)" / "매번 물어보기" / (Other: a character slug, e.g. a friend)

Then save — memory is what makes later sessions work without re-asking:
- **Claude's memory** (the persistent memory of this Claude Code install): one `user` memory "my meme character
  is `<slug>` (<bible>), always the main role, keep <height/face rule>", and one `feedback` memory with the three
  defaults and why. Future sessions read these before casting. If memory isn't available, say so and rely on the
  files below.
- **Files**: the bible in `assets/characters/<slug>/character.json` (already), and in `.env` (create from
  `.env.example` if missing): `MEMEGEN_RUN_PLAN=probe-first` or `full` when they chose "always …" (leave it unset
  for "ask every time").

## Finish
One short Korean summary: what's installed, which backend, the registered characters (send `views_sheet.jpg`),
the saved defaults, and the next step: "이제 밈 영상 주소나 파일을 주면서 '이 영상에 나 넣어줘' 라고 하면 됩니다."
If they already gave a video, hand over to the meme-video skill right away.

## Changing things later
- "내 사진 바꿔줘", "키가 작게 나와" → meme-character part B (old files go to the Trash via `memegen trash`),
  then update the bible and the memory entry.
- "기본값 바꿔줘" → re-ask only the question that changes, update memory and `.env`.
