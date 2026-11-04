# 멀티 머신 운영 가이드

**갱신일:** 2026-11-04
**적용 버전:** schema v2.1 / 데이터 git 동기화 정책(2026-11-04 결정)

같은 Claude 계정으로 여러 머신(Windows 데스크톱, 다른 PC, claude.ai 클라우드 세션)을 번갈아 쓰며 이 프로젝트를 운영할 때의 규약. 핵심은 **"git이 유일한 동기화 수단이다. 세션은 pull로 시작해 push로 끝난다"**.

## 목적

- 어느 머신에서 세션을 열어도 같은 코드·문서·데이터로 작업한다.
- 머신을 옮길 때 "어느 쪽이 최신인가"를 사람이 기억하지 않아도 된다.
- 로컬 머신이 포맷되거나 사라져도 GitHub 저장소만으로 완전히 복구된다 (2026-11-04 실제 발생. [배경](#배경-2026-11-04-데이터-유실과-복구) 참조).

## 원칙 요약

| 항목 | 규칙 |
|---|---|
| 동기화 수단 | **git만** 사용. 클라우드 드라이브·USB 복사 금지 |
| 기본 브랜치 | `master`. 로컬 머신은 master 직접 커밋 |
| 큰 패치 | 작업 브랜치 → master 병합 (선택) |
| 클라우드 세션 | `claude/<주제>` 브랜치에서 작업 → 사용자가 master에 병합 |
| 세션 시작 | `git pull` 선행 + 작업 트리 깨끗한지 확인 |
| 세션 종료 | 즉시 커밋 + `git push`. 미푸시 상태로 머신을 떠나지 않는다 |
| 커밋 메시지 | Conventional Commits (`type(scope): 한국어 요약`) |
| 데이터 파일 | `data/` 전부 커밋 대상 (원본 PDF·`source/` 제외) |
| 머신별 설정 | `.claude/settings.local.json` (gitignore) |

## 1. 새 머신 셋업 절차

### 1-1. 공통 (모든 OS)

```bash
git clone https://github.com/estesca/mass_song_recommendation.git
cd mass_song_recommendation
pip install -r server/requirements.txt      # openpyxl·xlsx2csv·fastapi 등
python scripts/rebuild.py --check           # stale_vs_* 가 모두 false 여야 함
```

`rebuild.py --check`가 `stale_vs_xlsx: true` 또는 `stale_vs_songs: true`를 보이면 `python scripts/rebuild.py`로 재빌드 후 커밋한다. clone 직후라면 보통 정상이다.

이 시점에 다음이 모두 있어야 한다 (git에 포함되므로 clone으로 자동 확보):

| 파일 | 역할 |
|---|---|
| `data/source/곡정보.xlsx` | 사람 편집 SSoT (4시트) |
| `data/songs.json` | 파생 운영 데이터 (스킬이 읽음) |
| `data/songs_index.json` | 경량 색인 (모드 B 후보 필터) |
| `data/source/선곡표.xlsx` | 미사별 선곡 기록 (ADR-008) |
| `data/song_impressions.json` | 곡별 사용경험 집계 (ADR-008) |
| `data/impression_log.jsonl` | 소감 raw 로그 (ADR-008) |

### 1-2. Windows 추가 사항

1. 어시스턴트 서버를 쓸 경우 `server/.env.example`을 `server/.env`로 복사하고 `ANTHROPIC_API_KEY` 입력 (`.env`는 gitignore).
2. 악보 OMR(Audiveris) 작업을 하는 머신이라면 `.claude/settings.local.json`에 아래 권한을 넣는다 (이 파일은 gitignore되므로 머신마다 따로 둔다).

```jsonc
// .claude/settings.local.json — Windows + Audiveris 머신 전용
{
  "permissions": {
    "allow": [
      "Bash(winget search *)",
      "Bash(winget install *)",
      "Bash(where audiveris *)",
      "Read(//c/Program Files/Audiveris/**)",
      "Bash(\"C:/Program Files/Audiveris/Audiveris.exe\" -version)",
      "Bash(\"C:/Program Files/Audiveris/Audiveris.exe\" -help)",
      "Bash(\"C:/Program Files/Audiveris/Audiveris.exe\" -batch -transcribe -export -output data/raw/audiveris_sample -sheets 90 95 138 168 274 -- archive/source/청소년청년성가집.pdf)"
    ]
  }
}
```

3. 원본 성가집 PDF(`source/청소년청년성가집.pdf`)는 저작권 때문에 git에 넣지 않는다. 가사 재추출·OMR이 필요한 머신에만 수동으로 배치한다. 현재 추천·라벨링·선곡 기록 흐름은 PDF 없이 동작한다.

### 1-3. 클라우드 세션 (claude.ai)

별도 셋업 없음. 세션이 저장소를 자동 clone하며, 데이터가 git에 있으므로 `/recommend-hymns` 등 데이터 의존 스킬도 그대로 동작한다. 단, 작업은 `claude/<주제>` 브랜치에서 이루어지므로 세션 종료 후 [3-3](#3-3-클라우드-세션-브랜치-병합)의 병합 절차가 필요하다.

### 1-4. settings.json vs settings.local.json 경계

| 파일 | 내용 | git |
|---|---|---|
| `.claude/settings.json` | **모든 머신 공통**: OS 무관한 명령(awk 등), WebFetch 도메인 | 커밋 |
| `.claude/settings.local.json` | **그 머신에서만** 의미 있는 것: Windows 경로, winget, 설치형 도구, 개인 실험 권한 | gitignore |

판단 기준: "다른 OS의 머신에서 이 항목이 무의미하거나 깨지는가?" → 예라면 local.

## 2. 데이터 동기화

### 2-1. 정책

**데이터 파일은 모두 git으로 동기화한다.** 2026-11-04 결정. 이전에는 저작권·개인기록 사유로 xlsx·사이드카를 gitignore했으나, 로컬 머신 포맷으로 선곡표·소감 로그가 유실됐고 가사는 어차피 `songs.json`에 커밋돼 있었으므로 분리의 실익이 없었다.

- 커밋 대상: `data/` 아래 전부 (`songs.v1.bak.json`·OMR 산출물 제외)
- 커밋 제외: 원본 PDF, 루트 `source/`, `pages/`, 크롤링 raw(`scripts/crawler/data/`)

### 2-2. 데이터를 바꾼 뒤 할 일

| 바꾼 것 | 이어서 할 것 |
|---|---|
| `곡정보.xlsx` (엑셀 직접 편집·`/add-tag`·`/clean-lyrics`·편집기) | `python scripts/rebuild.py` → `songs.json`·`songs_index.json`까지 **세 파일 함께 커밋** |
| `선곡표.xlsx` (`/log-setlist`) | 그대로 커밋 |
| `song_impressions.json`·`impression_log.jsonl` (`/log-impression`) | 그대로 커밋 |

xlsx만 커밋하고 파생 JSON을 빠뜨리면 다른 머신에서 `rebuild.py --check`가 stale을 보고한다. 그 머신에서 재빌드해 커밋하면 되지만, 원칙은 **바꾼 머신에서 세 파일을 한 커밋으로**.

### 2-3. xlsx 충돌

`곡정보.xlsx`는 바이너리라 git이 자동 병합하지 못한다. 두 머신이 같은 파일을 동시에 고치면 충돌한다. 예방책은 하나뿐이다. **세션 시작 시 pull, 종료 시 push.** 그래도 충돌이 나면:

```bash
git checkout --theirs data/source/곡정보.xlsx     # 또는 --ours, 최신이라 판단되는 쪽
python scripts/rebuild.py
git add data/ && git commit
```

버린 쪽의 변경은 `git show <커밋>:data/songs.json`으로 꺼내 비교해서 수동으로 다시 넣는다. 선곡표·소감 로그는 행 append 전용이라 양쪽을 합치는 편이 맞다 (`impression_log.jsonl`은 텍스트라 git이 대개 자동 병합한다).

### 2-4. 유실 시 복구

`songs.json`만 살아 있으면 카탈로그는 완전 복구된다.

```bash
python scripts/export_to_xlsx.py --force   # songs.json → 곡정보.xlsx (v2.1 7컬럼)
python scripts/init_setlist_xlsx.py        # 빈 선곡표.xlsx (없을 때만)
python scripts/rebuild.py                  # songs.json·songs_index.json 재생성 + sha 동기화
```

`export_to_xlsx.py`는 평상시 실행 금지(사용자 편집 덮어씀). 재해 복구 전용.

## 3. 브랜치·커밋 규약

### 3-1. 브랜치

- **로컬 머신(Windows·다른 PC): master 직접 커밋.** 1인 프로젝트라 브랜치 오버헤드가 과하다.
- **큰 패치(스키마 변경, 스킬 대규모 재작성 등)**: `feat/<주제>` 브랜치에서 작업하고 끝나면 master에 병합. 병합 전 `git pull origin master`로 최신화. 필수가 아니라 선택.
- **클라우드 세션: `claude/<주제>` 브랜치.** 클라우드 세션은 master에 직접 푸시하지 않는다. 종료 후 사용자가 로컬에서 병합한다 (3-3).
- master는 항상 "어느 머신에서 clone해도 바로 돌아가는 상태"를 유지한다. 깨진 중간 상태는 브랜치에 둔다.

### 3-2. 커밋 메시지: Conventional Commits

```
<type>(<scope>): <한국어 요약>

<본문 — 선택. 무엇을 왜 바꿨는지>
```

| type | 용도 |
|---|---|
| `feat` | 기능 추가 (스킬·스크립트·서버) |
| `fix` | 버그·오류 수정 |
| `docs` | 문서만 (매뉴얼·트래커·ADR·STATUS) |
| `data` | 데이터 변경 (xlsx·사이드카·songs.json). 이 프로젝트 고유 타입 |
| `refactor` | 동작 변화 없는 구조 변경 |
| `chore` | 설정·gitignore·의존성·정리 |

scope는 스프린트 ID(`S-012`) 또는 영역(`recommend`, `server`, `tracker`)을 쓰고 없으면 생략한다. 요약은 한국어, 50자 내외.

예:

```
feat(S-012): Google Sheets 프리셋 + render_output.py 프로토타입
data: 11월 첫째·둘째 주일 선곡표 기록
docs(tracker): S-012 체크리스트 Step 1 완료 마킹
chore: Windows 전용 권한을 settings.local.json으로 이동
```

기존 커밋 12개(`S-007: …`, `Complete S-008: …`)는 소급 수정하지 않는다.

### 3-3. 클라우드 세션 브랜치 병합

클라우드 세션이 `claude/xxx`를 푸시하고 끝났을 때, 로컬 머신에서:

```bash
git fetch origin
git checkout master && git pull origin master
git merge --ff-only origin/claude/xxx        # 깔끔하면 fast-forward
# ff가 안 되면: git merge origin/claude/xxx   (merge 커밋 생성)
git push origin master
git push origin --delete claude/xxx          # 정리 (선택)
```

PR로 검토하고 싶을 때는 클라우드 세션에 "PR 만들어줘"라고 요청한다. 기본은 PR 없이 로컬 병합.

## 4. 세션 시작·종료 체크리스트

### 4-1. 시작 (모든 머신 공통)

```bash
git status            # 작업 트리가 깨끗한가? 지난 세션에서 커밋 안 한 게 남았으면 먼저 처리
git pull origin master
python scripts/rebuild.py --check   # 데이터 작업을 할 세션이면
```

그 다음 `/quick-start`. 스킬이 이 단계를 Step 0으로 포함한다.

클라우드 세션은 자동 clone이므로 pull이 필요 없지만, `git log --oneline -3`으로 master 최신 커밋이 기대한 것인지 한 번 확인한다. 다른 머신에서 push를 잊었다면 여기서 드러난다.

### 4-2. 종료 (모든 머신 공통)

1. [RESUME.md의 세션 종료 절차](../status/RESUME.md#세션-종료-시-claude가-할-일) 대로 체크리스트·STATUS 갱신
2. 데이터를 바꿨다면 `python scripts/rebuild.py` 후 `rebuild.py --check`로 stale 없음 확인
3. `git add -A && git commit` (3-2 형식)
4. `git push origin master` (클라우드: `claude/xxx` 브랜치)
5. `git status`로 미푸시 커밋이 없는지 마지막 확인

**push 전에 머신을 떠나지 않는다.** 이것 하나가 모든 충돌과 유실을 막는다.

## 5. 검증

새 머신 셋업 또는 pull 직후 다음이 모두 통과하면 정상:

```bash
python scripts/rebuild.py --check        # stale 없음
python scripts/_verify_v2.py             # schema_version 2.1, 495곡
python scripts/_verify_index.py          # sha 일치, 495곡
```

추천 스킬 동작 확인은 `/recommend-hymns` 로 한 주일치 모드 A 추천을 돌려본다.

## 6. 트러블슈팅

### `git pull` 시 "Your local changes would be overwritten"

지난 세션에서 커밋을 안 한 것. 먼저 `git stash` → pull → `git stash pop` 하거나, 변경이 의미 있으면 커밋 후 pull.

### pull 직후 `rebuild.py --check`가 stale 보고

다른 머신이 xlsx만 커밋하고 파생 JSON을 빠뜨린 것. `python scripts/rebuild.py` 실행 후 `data: 파생 JSON 재빌드`로 커밋.

### 곡정보.xlsx 병합 충돌

[2-3](#2-3-xlsx-충돌) 참조.

### 스킬이 `s:/song_recommendation/...` 경로를 찾는다

2026-11-04 이전 스킬 캐시. 저장소를 pull하면 해결된다. 스킬·스크립트는 모두 저장소 루트 기준 상대 경로(cwd = 프로젝트 루트) 또는 `Path(__file__)` 기준을 쓴다. 새 코드에 절대 경로를 넣지 않는다.

### Windows에서 Claude가 Audiveris·winget 권한을 매번 묻는다

[1-2](#1-2-windows-추가-사항)의 `settings.local.json`이 없는 것.

## 배경: 2026-11-04 데이터 유실과 복구

- 원래 운영하던 Windows 머신(`s:/song_recommendation`)이 포맷됐고, gitignore돼 있던 `곡정보.xlsx`·`선곡표.xlsx`·`song_impressions.json`·`impression_log.jsonl`·`songs_index.json`·원본 PDF가 함께 사라졌다. git 히스토리·Google Drive 어디에도 사본이 없었다.
- 다행히 `data/songs.json`(v2.1, 2026-04-30 빌드, 495곡·가사 493곡·조표·박자·색인 포함)은 커밋돼 있었다. 이것에서 `export_to_xlsx.py`(v2.1 7컬럼 대응으로 수정)로 `곡정보.xlsx`를 재생성하고 `rebuild.py`로 라운드트립한 결과, 495곡 전 필드가 원본 `songs.json`과 동일함을 확인했다. **카탈로그는 손실 없이 복구됐다.**
- 복구 불가: 선곡표 기록, 소감 로그(사용자가 로컬에서 몇 차례 사용한 분), 원본 PDF. 선곡표·소감은 빈 파일로 초기화했다. PDF는 사용자가 보유본을 다시 배치해야 한다.
- 이 사건으로 데이터 gitignore를 해제하고 git 동기화 정책을 채택했다.

## 관련 문서

- [docs/status/RESUME.md](../status/RESUME.md) — 세션 시작·종료 절차
- [docs/tracker/work_management.md](../tracker/work_management.md) — 작업 단위 관리
- [docs/manuals/server_runtime.md](server_runtime.md) — 서버 실행
- [ADR-008 사용 경험 사이드카](../spec/decisions/ADR-008-usage-data-sidecars.md) — 사용 경험 사이드카
- [.claude/skills/quick-start/SKILL.md](../../.claude/skills/quick-start/SKILL.md) — 세션 시작 스킬
