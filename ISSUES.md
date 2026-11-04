# 이슈 목록

> **작업 관리 정책**: 이슈는 [작업 관리 정책](docs/tracker/work_management.md)의 한 단위다.
> 큰 맥락은 [스프린트](docs/tracker/sprints/CURRENT.md), 미래 검토 아이디어는 [고려사항](docs/tracker/CONSIDERATIONS.md)에서 관리.

## 상태 범례
| 상태 | 설명 |
|------|------|
| 시작 전 | 아이디어 또는 할 일로 등록됨 |
| 진행 중 | 현재 작업 중 |
| 스킵 | 보류 또는 우선순위 밀림 |
| 리뷰 중 | 구현 완료, 검토 필요 |
| 완료 | 작업 종료 |

## 담당자 범례
| 기호 | 의미 |
|------|------|
| 🤖 | Claude 단독 (자동화 가능) |
| 🤝 | 협업 (Claude 제안 → 사용자 승인) |
| 👤 | 사용자 단독 (저작권 보유 자료, 최종 판단) |
| 🚧 | 외부 블로킹 (기관 응답 대기 등) |

## 이슈

| # | 상태 | 담당자 | 제목 | 설명 | 등록일 |
|---|------|--------|------|------|--------|
| 1 | 완료 | 🤖 | 곡목록 추출 | 청소년청년성가집 PDF에서 495곡 목록 추출 → 곡목록.csv | 2026-04-09 |
| 2 | 완료 | 🤖 | 성가 추천 스킬 생성 | /recommend-hymns 스킬 구현 (전례 말씀 기반 선곡) | 2026-04-09 |
| 3 | 완료 | 🤖 | song_list_index_sample 반영 | (#29 Stage A에 흡수) v2 마이그레이션 시점 색인 엑셀 데이터가 곡정보.xlsx 색인 시트로 통합됨. enrich-liturgy-index는 deprecated, /add-tag로 대체. | 2026-04-10 |
| 4 | 완료 | 🤝 | 출력 표 양식 도구화 | (스프린트로 흡수, 2026-11-04 종결) 외부→내부 방향은 S-009, 내부→외부 방향은 S-012로 분리 정의됨. 계획 문서 docs/plans/issue-4-output-layout.md는 존재하지 않아 참조 제거. | 2026-04-10 |
| 5 | 스킵 | 👤 | 곡 비고란 데이터 입력 | (v2에서 폐기) `색인.비고` 필드 자체가 v2.0에서 제거됨. 자유 메모는 `색인.키워드`(자유)로 흡수. 이슈 자체 무의미. | 2026-04-10 |
| 6 | 스킵 | 🤝 | 미사곡 가사 기반 전례 매칭 자동화 | (도구로 대체) /label-lyrics + /add-tag로 사용자 명시 요청 시 색인 보강 가능. "자동화"는 v2 정책(색인 자동 보완 금지)과 충돌하므로 보류. | 2026-04-10 |
| 7 | 완료 | 🤖 | maria.catholic.or.kr 크롤러 | robots.txt 준수 크롤러 작성 및 527곡 수집 | 2026-04-14 |
| 8 | 완료 | 🤖 | find-lyrics / repair-lyrics 스킬 분리 | 두 스킬 구현, 역할 분리 (ADR-002) | 2026-04-16 |
| 9 | 완료 | 🤖 | 프로젝트 문서 구조 확립 | PROJECT/STATUS/RESUME/ADR 체계 구축 | 2026-04-16 |
| 10 | 완료 | 🤖 | 색인 엑셀에 가사 시트 병합 | (#30 Stage B에 흡수) 곡정보.xlsx의 4시트(곡목록·요약·색인·가사) 통합 구조로 해결됨. | 2026-04-16 |
| 11 | 완료 | 🤖 | 색인 엑셀 결측 필드 보완 | (#36으로 대체) /label-lyrics + /add-tag 도구 제공됨. 일괄 라벨링은 #36에서 진행. | 2026-04-16 |
| 12 | 완료 | 🤖 | recommend-hymns 실전 테스트 | (#37로 재정의) v2 재작성으로 옛 테스트는 무효. 모드 B 회귀 테스트는 #37 참조. | 2026-04-16 |
| 13 | 스킵 | 🤖 | 가사 입력 CSV 템플릿 설계 | (v2에서 불필요) 곡정보.xlsx의 `가사` 시트가 직접 입력 인터페이스. 별도 CSV 템플릿 무의미. | 2026-04-16 |
| 14 | 스킵 | 👤 | 322곡 가사 수작업 입력 | (전제 무너짐) v2 시점 가사 확보율 99.6% (493/495). 322곡 수작업 전제 무효. 잔여 2곡만 잠재 작업. | 2026-04-16 |
| 15 | 시작 전 | 🤝 | 실전 선곡 운영 및 피드백 | Phase 3. 성가대 실사용 로그 누적 | 2026-04-16 |
| 16 | 시작 전 | 🚧 | CBCK/교구청 공식 요청 | 가사 라이선스 또는 DB 접근 권한 문의 | 2026-04-16 |
| 17 | 스킵 | 🤖 | maria 매칭 정밀도 향상 | (목표 초과 + 우선순위 낮음) v2 마이그레이션 시점 173곡 매칭(원 목표 150곡+ 초과). 가사 확보율 99.6%이므로 추가 발굴 가치 작음. | 2026-04-16 |
| 18 | 스킵 | 🤖 | /recommend-hymns 실전 테스트 | (날짜 지남 + #37로 대체) 4/19 더미 호출은 v1 시절 계획. v2 모드 B 회귀 테스트는 #37 참조. | 2026-04-16 |
| 19 | 완료 | 🤖 | 색인 엑셀 결측 필드 자동 보완 | (정책 명문화 완료) 자동 보완 금지 정책은 docs/spec/schema.md + feedback_no_auto_field_fill.md + label-lyrics SKILL에 명시. 운영 도구는 /label-lyrics(사용자 승인 워크플로우)로 제공. | 2026-04-16 |
| 20 | 완료 | 🤖 | songs.json 중앙 데이터 생성 | data/songs.json 495곡, 172곡 가사 확보. 스키마 v1.0 | 2026-04-16 |
| 21 | 완료 | 🤖 | 정책 문서 체계 구축 | schema.md, skills_policy.md, ADR-003/004/005 | 2026-04-16 |
| 22 | 완료 | 🤖 | extract-sheet-lyrics v3 구현 | 페이지 경계, 코드 필터, 하이픈, 절 마커 + songs.json 사용 | 2026-04-16 |
| 23 | 완료 | 🤖 | validate-lyrics 스킬 신규 | (#27과 중복, 그 후 v2 deprecated) #27에서 lyrics_format.md + 검증 스킬 구현. v2.0에서 가사 객체 평탄화로 절별/절구조 검증이 무의미해져 deprecated 처리. | 2026-04-16 |
| 24 | 스킵 | 🤝 | 가사 형식 스펙 협의 | (전제 소멸, 2026-11-04) lyrics_format.md v1.0은 S-002에서 확정됨. 이를 소비하던 validate/fix-lyrics-format 스킬이 v2에서 deprecated되어 추가 협의 불필요. 구조 마커 관련 잔여는 #39. | 2026-04-16 |
| 25 | 완료 | 🤖 | 기존 스킬 SKILL.md 갱신 | find-lyrics → get-lyrics-data-local + crawl-lyrics로 분리. 크롤러 색인 문서 포함 | 2026-04-17 |
| 26 | 완료 | 🤖 | 495곡 PDF 추출(v3) 실행 | 434곡(87.7%) 가사 확보. songs.json 반영 | 2026-04-17 |
| 27 | 완료 | 🤖 | validate-lyrics-format 스킬 구현 | 가사 형식 검증 스킬 + lyrics_format.md 작성. 434곡 검증 완료 | 2026-04-17 |
| 28 | 스킵 | 🤖 | fix-lyrics-format 스킬 구현 | (분리 + v2 deprecated) clean-lyrics(본문 정리) + structure-lyrics(절 마커)로 책임 분리됨. fix-lyrics-format 자체는 v2 미대응으로 deprecated. | 2026-04-17 |
| 29 | 완료 | 🤖 | **스키마 v2.0 마이그레이션 (Stage A)** | songs.json v1→v2 변환. 신뢰도·외부ID·가사 중첩 제거, 색인 8카테고리(요약+성경/성월/시기/대축일/역할/느낌/키워드/곡모음집), 가사 평탄화. 작곡자 이름 86건 정리, 가톨릭성가 173곡 자동 태깅. ADR-006, schema.md v2.0, vocab.md, migrate_v1_to_v2.py, 신뢰도 백업 xlsx 산출. | 2026-04-25 |
| 30 | 완료 | 🤖 | **xlsx SSoT 빌드 파이프라인 (Stage B)** | data/source/곡정보.xlsx (4시트: 곡목록·요약·색인 tall·가사) + build_songs_json.py + build_song_index.py + rebuild.py + sha256 동기화 검증. round-trip 테스트 통과. | 2026-04-25 |
| 31 | 완료 | 🤖 | **에디터 v2 어댑터 (Stage C)** | server/app.py에 v2↔v1 어댑터(`_adapt_v2_to_v1`) + xlsx writer + 409 Conflict + 자동 rebuild. viewer/index.html 1741줄 무수정. viewer/server.py deprecated. | 2026-04-25 |
| 32 | 완료 | 🤖 | **가사 스킬 v2 정리 (Stage D)** | clean-lyrics·crawl-lyrics·structure-lyrics 리팩토링 (xlsx 직접 편집 + 자동병합 비활성). 6개 스킬 deprecated 처리: validate-lyrics-format / get-lyrics-data-local / repair-lyrics / extract-sheet-lyrics / enrich-liturgy-index / fix-lyrics-format. apply_to_xlsx.py 신규(jsonl→xlsx). | 2026-04-25 |
| 33 | 완료 | 🤖 | **recommend-hymns v2 재작성 (Stage E)** | 모드 A(Classic) + 모드 B(Funnel, experimental) 토글. filter_candidates.py(Hard filter + Soft scoring + Diversity) + serialize_candidates.py(JSON→Wide TSV, ~5배 압축). boost_tags 지원. 주당 토큰 39K→8~10K(~75% 감축 목표). | 2026-04-25 |
| 34 | 완료 | 🤖 | **add-tag 스킬 신설 (Stage F)** | 자연어 "N번 곡에 X 태그 추가" → 스크립트(add_tag.py)로 곡정보.xlsx 색인 시트 append. vocab 검증(느낌/역할/시기/성월/성경 정규형식) + 중복 체크 + xlsx 잠금 처리. 단일/복수/범위 곡 지원. | 2026-04-25 |
| 35 | 완료 | 🤖 | **label-lyrics 스킬 + apply_labels (Stage G)** | LLM이 가사 본문 분석 → 요약(40~60자)·느낌(vocab)·키워드 제안 → 사용자 검토 → apply_labels.py가 곡정보.xlsx의 요약/색인 시트에 반영. vocab 위반 거부, 중복 skip. | 2026-04-25 |
| 36 | 시작 전 | 🤝 | 495곡 일괄 라벨링 (Stage G 후속) | `/label-lyrics`로 전체 곡의 요약·느낌·키워드 라벨링. 한 세션 10~15곡씩 점진. 사용자 명시 요청 시 진행. recommend-hymns 모드 B 정확도의 핵심 변수. | 2026-04-25 |
| 37 | 시작 전 | 🤝 | recommend-hymns 모드 B 실전 회귀 테스트 | v2 재작성 후 4주일치 추천을 모드 A vs 모드 B로 비교. 겹치는 곡 ≥60% 목표. boost_tags 효과 확인. | 2026-04-25 |
| 38 | 시작 전 | 🤖 | Stage H 보류 항목 재검토 (3개월 후) | C-05 벡터 임베딩, C-06 성경 역색인, C-07 전례력 캐시 도입 여부를 사용 데이터(fail case)에 따라 재평가. (2026-11-04 재개 시점에 기한 도래 확인. 그러나 fail case 기록이 아직 없어 평가 불가 → #37 회귀 테스트 이후로 순연.) | 2026-04-25 |
| 39 | 시작 전 | 👤 | 원본 성가집 PDF 재배치 | 로컬 머신 포맷으로 `source/청소년청년성가집.pdf` 유실. 보유본을 새 머신 `source/`에 배치 (gitignore 유지). 가사 재추출·OMR(S-007 조표) 작업 전 필요. | 2026-11-04 |
| 40 | 시작 전 | 👤 | 유실된 선곡표·소감 로그 재입력 | 포맷 전 `/log-setlist`·`/log-impression`으로 남긴 기록 유실. 기억나는 주일 선곡을 `/log-setlist`로 다시 기록. 주보·메신저 등 외부 사본이 있으면 S-009(외부 선곡표 import) 활성화로 일괄 복구 검토. | 2026-11-04 |
| 41 | 시작 전 | 🤖 | `/structure-lyrics` 구현 (S-003 잔여) | 마커 없는 가사 본문에 [N절]/[후렴] 구조 마커 자동 부여. 스킬은 DRAFT로 존재, 스크립트 미구현. 반년간 모드 A 추천이 구조 없이 동작했으므로 실수요(fail case)가 확인될 때 착수. | 2026-11-04 |
| 42 | 시작 전 | 👤 | 영문 원곡 2곡 가사 수작업 입력 (S-003 잔여) | 가사 미확보 2곡(495 중). 곡정보.xlsx 가사 시트에 직접 입력 후 rebuild. | 2026-11-04 |
