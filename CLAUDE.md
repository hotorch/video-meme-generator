# 밈 제너레이터 (video-meme-generator) — Claude 작업 안내

레퍼런스 영상 + 내 캐릭터 → [Higgsfield Genjutsu](https://docs.higgsfield.ai/docs/models/genjutsu) 로 인물을 바꾼 밈 영상.
`memegen`(Python CLI)이 손, Claude(스킬)가 두뇌. Windows · macOS · Linux 공통. 사용자는 초보자일 수 있다 → 한국어로, 쉬운 말로.

## 세션을 시작하면
1. **기억을 먼저 본다.** 사용자의 메모리에 내 캐릭터 slug·키/체형·기본값(생성 방식, 해상도, 두 번째 인물)이 있으면 그대로 쓰고 다시 묻지 않는다.
2. `uv run memegen doctor` — `onboarded: false`(내 캐릭터 없음)거나 사용자가 처음이면 → **`meme-onboarding`** (설치·연결·내 캐릭터 등록·기본값 저장, 한 번만).
3. 그다음부터는 영상만 받으면 된다 → `meme-video`.

## 스킬
| 요청 | 스킬 |
|---|---|
| 처음 사용, "온보딩", 내 사진·반려동물·친구 등록, 기본값 바꾸기 | `meme-onboarding` |
| 영상/URL + "밈 만들어줘", "이 영상에 나 넣어줘", "이어서", 비용 | `meme-video` (전체 흐름) |
| 캐릭터 시트 자르기, "키가 작게/얼굴이 둥글게 나와", 유명인 사진 수집 | `meme-character` |
| 인물에게 영상 속 옷을 입힐지, 룩 생성·검수 | `meme-look` |
| Genjutsu 프롬프트 작성·검사, "왜 얼굴이 바뀌었지" | `genjutsu-prompt` |

## 원칙
- **질문은 돈에 대해 한 번만.** 영상을 받으면 `memegen cost` 로 "4초 테스트 먼저 / 바로 전체 / 생성 직전까지만" 을 한 번 묻고 끝까지 간다. 메모리·`run_plan`·`MEMEGEN_RUN_PLAN`·사용자의 말로 답이 있으면 묻지 않는다.
- **어셋은 사용자 것.** `assets/` 전부 git 제외. 신원은 사용자가 준 사진·시트만(Soul·AI 아바타 금지). 실존 인물은 수집한 사진으로만, 프롬프트에 실명 금지.
- **키·체형·얼굴형은 사용자의 말이 정답.** 작게/둥글게 나오면 바로 고치고 메모리의 설명도 고친다.
- 원본 영상은 자르지 않는다(최대 30초). 원본 파일은 건드리지 않고, 지울 땐 `memegen trash`.
- 명령은 항상 `uv run memegen …`. 셸 전용 명령 대신 `memegen frame / upload-put / trash`, 임시 파일은 작업 폴더 안에.
- 결과는 비교 시트와 얼굴 크롭을 **직접 보고** 판단한다. 애매하면 통과가 아니다. 결정과 이유는 작업 폴더에 남기고 마지막에 한 번 요약.

## 어디에 뭐가
- 작업 폴더 `work/<날짜-이름>/` (01_input … 05_final, manifest.json) — 이어서 할 땐 `memegen status <unit>`
- 캐릭터 `assets/characters/<slug>/` · 사물 `assets/props/` · 명령 전체 `uv run memegen --help`
- 정책·절차 `docs/references/` (sourcing, look, generation-backends, driving-video-fixes)
- **실제로 겪은 함정 `docs/pitfalls.md`** · 실험 기록 `docs/findings.md` — 모드 선택, 얼굴 차이, 검열, 비용 판단 전에 읽는다
- 코드를 고쳤으면 `uv run pytest -q`, 새 함정은 시험 하나 + `docs/pitfalls.md` 한 줄
