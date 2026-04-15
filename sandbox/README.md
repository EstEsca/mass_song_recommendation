# 스킬 테스트 샌드박스

스킬을 실제 데이터에 영향 없이 테스트하는 공간입니다.

## 구조

```
sandbox/
├── README.md                    # 이 파일
├── data/                        # 샘플 입력 데이터
│   └── 곡목록_sample.csv        # 1~30번만 포함된 축소판
├── output/                      # 스킬 실행 결과 저장
│   ├── 선곡기록_test.csv        # recommend-hymns 테스트 결과
│   ├── 가사_test.json           # find-lyrics 테스트 결과
│   └── ISSUES_test.md           # add-issue 테스트 결과
└── skills/                      # 샌드박스 전용 스킬 복사본 (선택)
```

## 사용 방법

### 1. 스킬 실행 시 샌드박스 경로 지정

기존 스킬은 `s:/song_recommendation/` 경로의 실제 파일을 참조합니다.
샌드박스에서 테스트하려면 스킬 실행 시 파일 경로를 샌드박스로 지정하세요:

```
/recommend-hymns
→ "곡목록 파일은 sandbox/data/곡목록_sample.csv 를 사용하고,
   결과는 sandbox/output/선곡기록_test.csv 에 저장해줘"

/find-lyrics 1
→ "결과는 sandbox/output/가사_test.json 에 저장해줘"

/add-issue 테스트 이슈
→ "sandbox/output/ISSUES_test.md 에 추가해줘"
```

### 2. 샌드박스 초기화

테스트 후 output 폴더를 비우면 깨끗한 상태로 복귀:

```bash
rm sandbox/output/*
```

### 3. 테스트 체크리스트

스킬 배포 전 확인사항:
- [ ] `/recommend-hymns` — 전례 말씀 수집 → 카테고리별 선곡 → 선정 이유 출력
- [ ] `/find-lyrics` — 대상 곡 확인 → 웹 검색 → 결과 기록
- [ ] `/add-issue` — ISSUES.md에 행 추가, 번호 자동 증가

## 주의

- `sandbox/` 폴더는 실제 운영 데이터와 **완전 분리**되어야 함
- 스킬이 샌드박스 경로 지정을 제대로 따르는지 확인 필요
- PDF 페이지 이미지(`pages/`)는 용량상 복사하지 않음. 원본 경로 공유.
