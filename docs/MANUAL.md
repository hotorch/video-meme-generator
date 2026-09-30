# 밈 제너레이터 사용 매뉴얼

> 밈 영상 하나와 내 사진을 넣으면, 영상 속 주인공이 내가 된 밈이 나옵니다.
> 저장소: https://github.com/hotorch/video-meme-generator · 만든 사람: YouTube @ai.sam_hottman

---

## 1. 한눈에 보기

| 항목 | 내용 |
|---|---|
| 무엇을 하나 | 레퍼런스 영상 속 인물을 내 캐릭터(사진·캐릭터 시트·반려동물)로 바꾼 밈 영상을 만듭니다 |
| 영상 생성 | Higgsfield **Genjutsu** (object-swap / motion-transfer) |
| 이미지 생성 | **Codex CLI** (ChatGPT 로그인, 추천) — 옷 입힌 룩, 캐릭터 새 각도, 사물 이미지 |
| 두뇌 | Claude Code + 이 저장소의 스킬 5개 |
| 손 | `memegen` 파이썬 CLI (영상 처리, 비용 계산, 생성 요청, 기록) |
| 지원 OS | Windows · macOS · Linux (WSL 필요 없음) |
| 질문 | **비용에 대해 딱 한 번**. 나머지는 Claude가 스스로 정하고 마지막에 요약 |

**사용 흐름 한 줄 요약**

`설치 → 온보딩(내 캐릭터 등록, 한 번) → "이 영상에 나 넣어줘 <주소>" → 비용 질문 1번 → 완성본`

---

## 2. 작동 원리

### 2-1. 손과 두뇌

- **손 = `memegen` CLI**: 영상 받기, 자르기, 정수 초 맞추기, 장면표 만들기, 비용 계산, 생성 요청과 기다리기, 원본 소리 복원처럼 **정해진 일**을 합니다. 모든 명령은 JSON으로 결과를 돌려줍니다.
- **두뇌 = Claude + 스킬**: 영상을 보고 누구를 바꿀지, 어떤 모드가 맞는지, 프롬프트를 어떻게 쓸지, 결과가 통과인지 **판단하는 일**을 합니다.
- CLI는 판단 결과(JSON, 프롬프트)를 검사해서 틀리면 막습니다. 예를 들어 검사를 통과하지 않은 프롬프트로는 생성이 되지 않습니다.

### 2-2. 작업 단위 = 밈 하나 = 폴더 하나

밈 하나를 만들 때마다 `work/<날짜-시각>-<이름>/` 폴더가 생깁니다. 중간에 멈춰도 이 폴더만 보면 이어서 할 수 있습니다.

| 폴더 | 내용 |
|---|---|
| `01_input/` | 원본 복사본, 보낼 영상(`prepared.mp4`), 4초 테스트 영상 |
| `02_analysis/` | 장면표, 분석(`analysis.json`), 캐스팅(`cast.json`), 얼굴 차이(`face_gap.md`), 최종 프롬프트 |
| `03_assets/` | 실제로 보낸 이미지, 룩 이미지, Codex로 만든 이미지 |
| `04_renders/` | 테이크 영상, 원본과 나란히 놓은 비교 시트, 검수 기록 |
| `05_final/` | 완성본 mp4 (원본 소리 포함) |
| `manifest.json` | 단계, 비용, 테이크, 고른 생성 방식 |

### 2-3. 품질 관문 (Gate)

| 관문 | 언제 | 무엇을 보나 |
|---|---|---|
| Gate 1 | 영상 분석 후 | 컷 수, 얼굴 크기, 바꿀 사람 수 — 이 영상으로 될지 |
| Gate 2 | 캐릭터 등록 후 | 한 사람만 나오는지, 얼굴이 선명한지, 글자·워터마크가 없는지 (7점 이상) |
| Gate L | 룩 생성 후 | 신원·의상·자세·깨끗함 네 항목 모두 7점 이상이어야 생성 가능 |
| 프롬프트 검사 | 생성 직전 | 토큰, 실명, `@Image` 표기, 검열 위험 단어, 얼굴 차이 기록 |
| Gate 3 | 결과가 나온 뒤 | 비교 시트와 얼굴 크롭을 직접 보고 판단. 애매하면 통과가 아님 |

### 2-4. 두 가지 모드 (가장 중요한 원리)

| | object-swap | motion-transfer |
|---|---|---|
| 얼굴형 | **원본 배우의 얼굴형이 남음** (턱, 볼, 머리 크기) | 내 얼굴형으로 바뀜 |
| 배경·다른 사람 | 원본 그대로 | 다시 그려짐 (색감·주변 인물이 조금 바뀜) |
| 잘 맞는 경우 | 사물 교체, 얼굴이 작거나 원본과 닮은 경우, 원본을 픽셀 그대로 지켜야 할 때 | **얼굴이 크게 나오는 대부분의 밈** |

> 실험 결과: object-swap에서는 프롬프트를 길게 쓰든, 비우든, 해상도를 올리든 얼굴형이 같았습니다. 얼굴형까지 바뀌는 건 motion-transfer뿐이었습니다. 애매하면 같은 4초 구간으로 두 모드를 모두 테스트해서 고릅니다.

### 2-5. 그 밖의 원리

- **정수 초 맞추기**: Genjutsu는 초 단위로 올림해서 값을 받고, 결과는 대략 정수 초만큼만 돌려줍니다(12.04초 → 12.0초). 그래서 보낼 때 13초로 늘리고(값은 같음), 마무리할 때 원래 12.04초로 되돌립니다.
- **얼굴 차이 문장**: 원본 배우와 내 얼굴이 크게 다르면(성별, 머리, 안경, 수염, 턱) 프롬프트에 "원본은 X, 결과는 Y" 문장을 차이마다 한 줄씩 넣습니다. 없으면 원본의 특징이 새어 나옵니다.
- **프롬프트로 안 되는 건 영상으로**: "더 크게", "더 갸름하게" 같은 문장은 거의 효과가 없습니다. 키나 얼굴 폭이 중요하면 보내는 영상 자체를 보정합니다(키 휘기, 얼굴 가로 압축).
- **테스트 통과 ≠ 전체 통과**: 긴 영상에서 사람이 작아지는 구간은 원본 얼굴로 돌아가기도 해서, 전체 결과도 따로 검수합니다.

---

## 3. 설치

### 3-1. 준비물

| | Windows (PowerShell) | macOS | 확인 명령 |
|---|---|---|---|
| Claude Code (Claude 유료 요금제) | claude.com/claude-code 안내대로 설치 + Git for Windows | 안내대로 설치 | `claude --version` |
| uv (파이썬 자동 설치) | `winget install astral-sh.uv` | `brew install uv` | `uv --version` |
| ffmpeg | `winget install Gyan.FFmpeg` | `brew install ffmpeg` | `ffmpeg -version` |
| Node.js (Codex용) | `winget install OpenJS.NodeJS.LTS` | `brew install node` | `node -v` |
| Codex CLI (추천) | `npm i -g @openai/codex` | 같음 | `codex --version` |
| Higgsfield 계정 | higgsfield.ai 가입 | 같음 | — |

> Windows: `winget` 으로 설치한 뒤에는 **터미널을 새로 열어야** 명령이 잡힙니다.

### 3-2. 받기

```bash
git clone https://github.com/hotorch/video-meme-generator.git
cd video-meme-generator
uv sync
uv run memegen doctor
```

`doctor` 결과에서 `ffmpeg`, `ffprobe` 가 `true` 면 설치 완료입니다. `generation` 은 영상 생성 연결 상태, `onboarded` 는 내 캐릭터 등록 여부를 알려 줍니다.

---

## 4. 영상 생성 연결 (둘 중 하나)

| | A. Higgsfield MCP (추천) | B. REST API 키 |
|---|---|---|
| 결제 | 구독 **크레딧** | API 잔액에서 **쓴 만큼** (구독과 별개) |
| 준비 | Claude에 커넥터 추가 + 로그인 | 키를 `.env` 에 붙여 넣기 |
| 4초 테스트 | 12 크레딧 | $1.27 |

**A. MCP 커넥터**
1. higgsfield.ai 가입, 요금제 선택
2. claude.ai 또는 Claude 데스크톱 → 설정 → 커넥터 → 사용자 지정 커넥터 추가 → 이름 `Higgsfield`, 주소 `https://mcp.higgsfield.ai/mcp` → 로그인
   - 또는 터미널에서 `claude mcp add --transport http higgsfield https://mcp.higgsfield.ai/mcp` 후 Claude Code의 `/mcp` 에서 로그인
3. Claude에게 "힉스필드 잔액 알려줘" → 크레딧이 보이면 완료

> 웹 요금제의 "무제한" 혜택은 MCP 호출에 적용되지 않습니다.

**B. REST API 키**
1. console.higgsfield.ai 에서 API 키 생성 (`KEY_ID`, `KEY_SECRET`)
2. 콘솔에서 API 잔액 충전
3. `cp .env.example .env` (Windows PowerShell도 같음) → `.env` 에 `HF_KEY=KEY_ID:KEY_SECRET`
4. `uv run memegen doctor` 의 `generation` 이 `REST API ready` 면 완료

---

## 5. 온보딩 (처음 한 번, 약 10분)

저장소 폴더에서 `claude` 를 켜고 **"온보딩 해줘"** 라고 말하면 `meme-onboarding` 스킬이 다섯 단계로 안내합니다.

| 단계 | 하는 일 | 내가 할 일 |
|---|---|---|
| 1/5 설치 확인 | `doctor` 결과를 보고 빠진 것을 OS에 맞게 설치 안내 | 안내된 명령 실행 |
| 2/5 영상 생성 연결 | MCP 또는 REST 중 하나가 동작하는지 확인 | 커넥터 로그인 또는 키 입력 |
| 3/5 내 캐릭터 등록 | 사진을 한 사람만 나오게 잘라 `assets/characters/<이름>/` 에 등록 | 사진·시트 넘기기, **키와 체형** 알려 주기 |
| 4/5 더 넣을 캐릭터 (선택) | 반려동물, 허락받은 친구, 자주 쓸 사물 등록 | 원하면 사진 넘기기 |
| 5/5 기본값 저장 | 질문 3개를 한 번에 묻고 Claude 메모리와 `.env` 에 저장 | 3개 고르기 |

**5/5에서 묻는 3가지**

| 질문 | 선택지 |
|---|---|
| 생성 방식 기본값 | 매번 물어보기 (추천) / 항상 4초 테스트 먼저 / 항상 바로 전체 |
| 해상도 기본값 | 720p (선명) / 480p (저렴) |
| 두 번째 인물이 필요할 때 | 원본 그대로 두기 (추천) / 매번 물어보기 / 특정 캐릭터 |

**좋은 사진**

- 정면 얼굴이 크게 나온 사진 1장 + 여러 각도가 한 장에 담긴 깨끗한 시트 1장 (또는 사진 3~5장: 정면, 3/4, 옆, 전신)
- 한 사람만, 선글라스·마스크 없이, 글자나 워터마크 없이
- 사진을 여러 장 겹쳐 넣으면 얼굴이 넓어지고 사진 속 옷이 섞이니, **사람당 1~2장**이 가장 좋습니다

> `assets/` 안의 사진과 캐릭터는 모두 내 컴퓨터에만 있고 git에 올라가지 않습니다. 기억(메모리) 덕분에 다음 세션부터는 캐릭터와 기본값을 다시 묻지 않습니다.

---

## 6. 이미지 생성: Codex CLI 가이드 (추천)

### 6-1. 왜 Codex인가

| | Codex CLI image_gen | Higgsfield 이미지 모델 / Soul |
|---|---|---|
| 신원 유지 | 레퍼런스 사진을 붙여 얼굴·머리·액세서리를 잘 유지 | 얼굴이 바뀌거나 어색한 결과가 잦았음 |
| 비용 | ChatGPT 요금제 안에서 사용 (API 키 불필요) | Higgsfield 크레딧 차감 |
| 이 키트의 선택 | **모든 이미지 생성은 Codex** | 쓰지 않음 |

Codex는 **필수가 아닙니다.** 내 사진을 그대로 넣는 기본 흐름에는 필요 없고, 아래 경우에만 씁니다.

| 쓰는 곳 | 예 |
|---|---|
| 룩(Gate L) | 영상 속 옷·소품이 곧 웃음 포인트일 때, 내 캐릭터에게 그 옷을 입힌 스튜디오 사진 |
| 캐릭터 수정·새 각도 | "키가 작게 그려졌어", "옆모습이 없어" → 기존 사진을 참고해 새로 그림 |
| 사물 이미지 | "트럭을 검정 SUV로" 처럼 이미지가 없는 사물 |
| 가상의 인물 | 실존하지 않는 캐릭터 (실존 인물은 처음부터 그리지 않음) |

### 6-2. 설치와 로그인

```bash
npm i -g @openai/codex
codex login
codex login status
uv run memegen doctor
```

- `codex login` 은 브라우저로 **ChatGPT 계정**에 로그인합니다 (ChatGPT 유료 요금제 필요, API 키 불필요).
- `doctor` 의 `codex (looks / image gen)` 가 `true` 면 준비 완료입니다.
- Windows에서는 npm이 `codex.cmd` 로 설치하는데, `memegen` 이 알아서 찾아 실행합니다.
- 다른 경로의 codex나 특정 모델을 쓰려면 `.env` 에 `MEMEGEN_CODEX_BIN=...`, `MEMEGEN_CODEX_MODEL=...`

### 6-3. 작동 원리

1. `memegen` 이 캐릭터의 사진(뷰)을 레퍼런스로 붙여 `codex exec` 를 실행합니다 (`-i` 로 이미지 첨부).
2. Codex에게 "내장 image_gen을 정확히 한 번 호출하고, 레퍼런스와 같은 사람으로, 요청한 것만 바꿔라"는 지시를 보냅니다.
3. 결과 PNG를 작업 폴더로 복사하고, 옆에 기록 파일(`.json`: 프롬프트, 레퍼런스, 스레드 id)을 남깁니다.
4. 레퍼런스와 결과를 나란히 놓은 **검수 시트**(`*_review.jpg`)를 만듭니다.
5. 여러 장은 최대 3장까지 동시에 만듭니다. 한 장에 약 1~2분 걸립니다.

> 동시에 여러 장을 만들 때 다른 스레드의 이미지를 가져오던 문제가 있었는데, 지금은 각 스레드 폴더의 이미지를 먼저 쓰도록 고쳐져 있습니다.

### 6-4. 명령 예시

보통은 Claude에게 말로 시키면 됩니다("옷을 영상처럼 입혀줘", "옆모습을 하나 만들어줘"). 직접 쓸 때는 이렇습니다.

```bash
# 작업 폴더 안에 새 이미지 (내 캐릭터 me 를 레퍼런스로, 2장)
uv run memegen image gen <작업이름> --ref me --shot full-body --angle three-quarter --name me_suit --n 2 --prompt "Full-body three-quarter view, standing, wearing a navy suit, slight smile"

# 캐릭터 자체를 고칠 때 (assets/characters/me/source/generated/ 에 저장)
uv run memegen image gen --char me --name four_view_fixed --n 2 --aspect landscape --no-clean --ref me:hero --prompt "Same four poses, realistic adult proportions about 8 heads tall, long legs; keep face, hair, outfit exactly"

# 룩: cast.json 에 적은 look 을 바탕으로 인물별 후보 생성 → 검수 → 승인
uv run memegen look gen <작업이름>
uv run memegen look approve <작업이름> --cast A --chosen 03_assets/looks/A_me_2.png --identity 8 --outfit 9 --pose 8 --clean 9
```

| 옵션 | 뜻 |
|---|---|
| `--ref` | `<slug>` (알맞은 뷰 자동 선택) · `<slug>:<뷰이름>` · 파일 경로. 여러 번 쓸 수 있음 |
| `--shot` / `--angle` | 자동 선택할 뷰의 구도 (close-up, medium, full-body / front, three-quarter, side) |
| `--n` | 만들 장수 (1~4) |
| `--aspect` | portrait · landscape · square |
| `--no-clean` | 단색 배경·한 사람 규칙을 끔 (시트·턴어라운드처럼 여러 컷일 때) |

### 6-5. 잘 만드는 요령

- **바뀌는 것만 적습니다** (옷, 자세, 각도, 표정, 소품). 얼굴을 글로 다시 설명하면 레퍼런스와 경쟁합니다.
- **클로즈업 레퍼런스를 꼭 포함**해 얼굴을 고정합니다.
- 룩은 **50mm 렌즈, 2.5m 거리** 구도로. 광각은 얼굴을 넓게 만듭니다.
- 너무 가까운 클로즈업 룩은 영상 생성에서 검열(`nsfw`)에 걸린 적이 있습니다. 중간·전신 구도로.
- 검수는 썸네일이 아니라 **얼굴을 잘라 원본 사진과 나란히** 봅니다. 얼굴이 둥글어진 룩을 넣으면 결과가 더 나빠집니다.
- 실존 인물은 처음부터 그리지 않습니다. 수집한 실제 사진을 레퍼런스로 옷과 자세만 바꿉니다.

### 6-6. 문제 해결

| 증상 | 해결 |
|---|---|
| `codex not found` | `npm i -g @openai/codex` 후 터미널 새로 열기 |
| `doctor` 에서 codex가 `false` | `codex login` 다시, `codex login status` 확인 |
| `codex produced no image` | 로그 `work/<작업>/logs/codex_<이름>.jsonl` 확인. 요금제 한도나 로그인 만료가 흔한 원인 |
| 얼굴이 달라짐 | 클로즈업 레퍼런스 추가, 프롬프트에서 얼굴 묘사 빼기, `--n 2` 로 후보 늘리기 |
| 시간이 오래 걸림 | 정상입니다 (장당 1~2분). 여러 인물은 동시에 만듭니다 |

---

## 7. 스킬 소개

| 스킬 | 이렇게 말하면 | 하는 일 |
|---|---|---|
| `meme-onboarding` | "온보딩 해줘", "내 사진 등록", "우리 고양이도" | 설치·연결 확인, 내 캐릭터 등록, 기본값을 메모리에 저장 |
| `meme-video` | "이 영상에 나 넣어줘 <주소>", "이어서 해줘", "얼마 들어?" | 전체 흐름. 비용 질문 1번, 분석부터 완성본까지 |
| `meme-character` | "키가 작게 나왔어", "시트 잘라줘", "유명인 넣고 싶어" | 캐릭터 등록·수정, 유명인 사진 수집(위키미디어 커먼즈) |
| `meme-look` | "옷도 영상처럼 입혀줘", "힙하게" | 룩이 필요한지 판단 → Codex로 생성 → 검수·승인 |
| `genjutsu-prompt` | "프롬프트 짜줘", "왜 얼굴이 바뀌었지" | 영상과 이미지를 이해한 뒤 프롬프트 작성·검사·재촬영 수정 |

### meme-video (전체 흐름)
1. 영상을 받아 장면표를 만들고 길이를 잽니다.
2. **비용 질문 1번** (아래 8장). 메모리나 `.env` 에 기본값이 있으면 묻지 않습니다.
3. 분석: 누가 어디서 무엇을 하는지, 누구를 바꿀지, 어느 모드가 맞는지.
4. 캐스팅 → 룩 판단 → 프롬프트 → 생성 → 검수 → 마무리.
5. 재시도는 한 편에 최대 3번, 같은 실패를 같은 입력으로 반복하지 않습니다. 어떤 경우에도 가장 나은 테이크로 완성본을 만듭니다.

### meme-character (캐릭터)
- 캐릭터 = `assets/characters/<slug>/` 폴더 = 설명(`character.json`) + 원본(`source/`) + 잘린 뷰(`views/`, 이것만 영상 생성에 보냄).
- 설명(bible)에는 신원 특징만 적습니다: 얼굴형, 머리, **키와 체형**. 옷은 영상에 따라 바뀌므로 적지 않습니다.
- 사용자가 "키가 작게 나왔다"고 하면 그 말이 정답입니다. Codex로 고쳐 다시 그리고, 예전 파일은 휴지통으로 옮깁니다.

### meme-look (룩)
- **기본은 사진을 바로 넣는 것.** 아래 조건일 때만 룩을 만듭니다.
  > 몸·옷이 화면에 보임 **AND** (옷·소품이 곧 그 장면 **OR** 손에 든 소품이 있음 **OR** "이 캐릭터가 이 옷을 입은 것" 자체가 웃음 포인트)
- 원본 인물의 얼굴은 절대 보내지 않고, 목 아래만 잘라 옷 참고용으로 씁니다.

### genjutsu-prompt (프롬프트)
- 프롬프트 길이는 원본과 결과가 **얼마나 다른지**에 맞춥니다. 한 사람만 바꾸면 1~3문장, 새 장소·새 소품으로 다시 연출하면 긴 설명.
- 문장마다 이유가 있어야 합니다: 바뀌는 것, 누구에게 어떤 이미지, 충돌 해결, 실패 방지. 원본을 다시 설명하는 문장은 뺍니다.
- 토큰은 `<<<video_1>>>`, `<<<image_1>>>` 만. 실명은 쓰지 않습니다. 내가 쓴 `@Image 1` 프롬프트는 문장을 그대로 두고 토큰만 바꿉니다.

---

## 8. 밈 만들기

```
이 영상에 나 넣어줘 https://www.youtube.com/shorts/XXXXXXXX
왼쪽에 의자에 앉은 사람 = 나
```

영상을 받자마자 한 번만 묻습니다.

```
chair-jump (12초) 생성 방식을 골라 주세요
  1. 테스트 먼저 (추천)  — 4초만 480p로 한 번 (≈$1.27 / 12 크레딧). 괜찮으면 묻지 않고 바로 전체 생성
  2. 바로 전체 생성      — 원본 12초, 720p (≈$8.85 / 91 크레딧)
  3. 생성 직전까지만     — 분석·캐스팅·프롬프트까지만 준비 (비용 0)
```

고르고 나면 끝까지 갑니다. 완성본: `work/<날짜-이름>/05_final/<이름>.mp4`. 대기열에 따라 한 편에 10~40분.

**고치고 싶을 때 이렇게 말하기**

- "얼굴이 원본 배우랑 너무 닮았어" → 모드 변경, 얼굴 차이 문장
- "나를 더 크게 해줘" / "얼굴이 너무 둥글어" → 보내는 영상 보정
- "선글라스는 그대로 써줘" / "차는 이 사진으로 바꿔줘"
- "오른쪽 사람은 원본 그대로 둬줘"
- "480p로 싸게 전체 한 번" / "이번엔 테스트 없이 바로"
- "어디까지 했어?" / "이어서 해줘"

---

## 9. 비용

Genjutsu는 **넣은 영상 길이(초, 올림)** 로 값을 매깁니다. 두 모드는 같은 값입니다. 실패·검열(`nsfw`, `ip_detected`)은 환불, 마음에 안 드는 완성 결과는 환불되지 않습니다.

| 길이 | MCP 480p | MCP 720p | REST 480p | REST 720p |
|---|---|---|---|---|
| 4초 테스트 | 12 cr | 28 cr | $1.27 | $2.72 |
| 10초 | 30 cr | 70 cr | $3.18 | $6.81 |
| 20초 | 60 cr | 140 cr | $6.36 | $13.62 |
| 30초 (최대) | 90 cr | 210 cr | $9.54 | $20.43 |

- 지금 영상의 비용: `uv run memegen cost <작업이름>`
- 쓴 비용: `uv run memegen take status <작업이름>`
- Codex 이미지 생성은 ChatGPT 요금제 안에서 돌아가 추가 비용이 없습니다.

---

## 10. 명령 모음

| 명령 | 하는 일 |
|---|---|
| `uv run memegen doctor` | 설치·연결·온보딩 상태 |
| `uv run memegen new <이름> --source <영상/URL> --brief "…"` | 작업 폴더 생성 + 영상 받기 |
| `uv run memegen cost <작업>` | 테스트/전체 비용표, `--choose` 로 답 기록 |
| `uv run memegen status [<작업>]` | 작업 목록 / 진행 단계 |
| `uv run memegen prepare <작업>` | 분석 검증 → 보낼 영상 만들기 (정수 초) |
| `uv run memegen route show <작업>` | 인물별 다음 할 일 |
| `uv run memegen prompt check <작업>` | 프롬프트 검사 |
| `uv run memegen render <작업> --dry-run` | 보낼 요청과 비용만 확인 |
| `uv run memegen render <작업> --probe` | REST로 4초 테스트 |
| `uv run memegen take add <작업> <결과>` | MCP로 만든 결과 기록 |
| `uv run memegen finalize <작업> --take N` | 원본 소리 복원 → 완성본 |
| `uv run memegen image gen …` | Codex 이미지 생성 |
| `uv run memegen asset list` | 등록된 캐릭터 |
| `uv run memegen frame <영상> <초>` | 프레임 한 장 저장 |
| `uv run memegen trash <경로>` | 휴지통으로 이동 (영구 삭제 없음) |

---

## 11. 좋은 결과를 위한 팁과 문제 해결

**좋은 영상 고르기**

| | 권장 |
|---|---|
| 길이 | 4~30초 (30초 넘으면 앞 30초) |
| 바꿀 사람 수 | 1~2명 |
| 얼굴 | 크게, 정면에 가깝게 |
| 컷 | 적을수록 |
| 피할 것 | 실제 방송·연예인 영상 (검열·IP 차단) |

**자주 겪는 문제**

| 증상 | 원인과 해결 |
|---|---|
| 얼굴이 원본 배우를 닮음 | object-swap의 한계 → motion-transfer |
| 원본의 머리·안경·수염이 남음 | 얼굴 차이 문장 추가 |
| 선글라스가 사라짐 | "안경만은 원본에서" 문장을 얼굴 차이 문장 앞에 |
| 키가 작게, 얼굴이 둥글게 | 프롬프트 말고 보내는 영상 보정 |
| 자막·가사가 생김 | 음악 영상 → "no subtitles, no captions, no on-screen lyrics" |
| 주변 사람이 바뀜 | motion-transfer의 특징 → 인원·위치 고정 문장, 꼭 그대로면 object-swap |
| `nsfw` / `ip_detected` | 환불됨. 방송 영상, 원본 인물 사진을 이미지로 보냄, 피부·노출 단어가 흔한 원인 |
| 끝이 잘림 | `prepared.mp4` 를 보내면 자동 해결 (정수 초 패딩) |
| Windows에서 명령을 못 찾음 | 설치 후 터미널·Claude Code 새로 열기, `doctor` 의 `hints` 실행 |

더 자세한 기록: 저장소의 `docs/pitfalls.md` (실제로 겪은 함정), `docs/findings.md` (실험 기록).

---

## 12. 책임 있게 쓰기

- 다른 사람의 얼굴은 **허락을 받고** 씁니다.
- 실존 인물은 패러디·개인 용도로만, 초상권과 플랫폼 정책을 확인합니다.
- 속이거나 해치려는 용도(가짜 뉴스, 사칭, 성적 합성)로는 절대 쓰지 않습니다.
- 이 키트를 응용해 콘텐츠를 만들면 출처를 적어 주세요: `video-meme-generator by @ai.sam_hottman (YouTube) · hotorch (GitHub)`
