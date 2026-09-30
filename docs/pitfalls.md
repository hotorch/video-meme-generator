# 실제로 겪은 함정 (다시 밟지 않게)

여러 날 실제로 돌리며 부딪힌 것들입니다. 새 함정을 고치면 `tests/test_core.py` 에 시험 하나, 여기에 한 줄.

- **object-swap 은 원본 배우의 얼굴형을 남긴다.** 프롬프트 길이·해상도·이미지 수를 바꿔도 같았다 → 얼굴이 보이면 motion-transfer 가 기본. 애매하면 같은 4초로 두 모드 테스트.
- **테스트(4초) 통과 ≠ 전체 통과.** 사람이 작아지는 긴 영상에서 전체 생성이 원본 얼굴로 돌아간 적이 있다. 전체 테이크도 따로 검수.
- **Genjutsu 는 대략 정수 초만 돌려준다** (12.04초 → 12.0초, 끝이 잘림). `prepare` 가 정수 초로 패딩, `finalize` 가 원래 길이로 자른다. `trimmed.mp4` 를 보내지 말 것.
- **소스 오디오가 영상보다 짧으면 `-shortest` 가 영상을 잘랐다** → `restore_audio` 는 `apad` + 길이 지정.
- **얼굴 차이가 크면 프롬프트에 대비 문장** (원본은 X, 결과는 Y). 짧게, 큰 차이마다 한 문장. 원본에만 있는 소품(선글라스)은 그 앞에 "유지" 문장.
- **"더 크게", "더 갸름하게" 문장은 거의 안 먹는다.** 구동 영상을 직접 고친다(`docs/references/driving-video-fixes.md`). 키 보정 휘기는 어깨 아래만 늘린다(머리까지 키우면 얼굴이 커 보임).
- **신원 이미지는 한 사람당 1–2장.** 깨끗한 멀티뷰 시트 한 장이 셀카 여러 장보다 나았다. 셀카를 겹치면 얼굴이 넓어지고 셀카 속 셔츠가 옷으로 샌다.
- **원본 인물 크롭을 이미지로 보내면 `ip_detected`.** 원본 인물을 지키려면 object-swap 이나 "유지" 문장으로.
- **유명인 이미지는 object-swap 에서 조용히 무시될 수 있다** (완료·과금, 얼굴은 원본 그대로). 한 번 무시되면 motion-transfer 로 바꾸거나 그 교체를 뺀다.
- **실제 방송 영상은 `nsfw` 로 막힐 수 있다.** 프롬프트엔 피부·목·가슴 같은 말 대신 "complexion". 너무 가까운 룩 이미지도 막혔다.
- **음악 영상은 자막(가사)을 지어낸다** → "no subtitles, no captions, no on-screen lyrics".
- **motion-transfer 는 교체 안 한 사람·군중도 다시 그린다.** 인원·위치 고정 문장, 꼭 그대로여야 하면 object-swap. 원본을 마스크로 다시 붙이는 합성은 두 번 실패했다.
- **MCP 업로드 PUT 에는 `If-None-Match: *` 헤더가 필수** (서명에 포함). 프리셋 추천이 오면 `declined_preset_id` 로 다시 보낸다.
- **결과를 모르는 제출은 다시 보내지 않는다.** 타임아웃 난 MCP 제출이 실제로는 만들어져 140 크레딧이 나갔다. REST 는 `take wait`, MCP 는 `show_generations` 먼저.
- **MCP `count: 2` 의 가격은 변형 1개당.** 합계로 적었다가 크레딧 기록이 틀렸다. 크레딧은 `balance`/`transactions` 로 맞춘다.
- **Codex 병렬 생성이 다른 스레드의 이미지를 집어왔다** → `imagegen/codex.py` 가 스레드 폴더를 먼저 본다. 그래도 변형끼리 md5 가 다른지 확인.
- **Codex 룩이 얼굴을 둥글게 만들면 스왑이 더 나빠진다.** 룩은 필요할 때만(`look_decision`), 얼굴 크롭으로 검수.
- **`render --budget` 기본 $15 가 30초 720p($20.43)를 막았다** → 기본 $25.
- **Windows 는 텍스트 기본 인코딩이 cp949 라 한글 JSON 이 깨진다** → 모든 `read_text`/`write_text`/subprocess 에 `encoding="utf-8"`, 출력도 UTF-8 로 재설정(`cli.py` 맨 위). 새 코드도 반드시 명시.
- **npm 으로 깐 Codex 는 Windows 에서 `codex.cmd`** → 실행 전 `shutil.which()` 로 실제 경로를 찾는다. yt-dlp 는 `python -m yt_dlp` 로(PATH 에 기대지 않음).
- **스킬을 심볼릭 링크로 두었더니 Windows git 이 텍스트 파일로 받았다** → `.claude/skills/` 에 실제 폴더로 둔다.
- **`curl`, `mv ~/.Trash`, `/tmp` 를 스킬에 적어 두면 Windows 에서 막힌다** → 같은 일을 하는 `memegen` 명령(upload-put, trash, frame)을 쓴다.
