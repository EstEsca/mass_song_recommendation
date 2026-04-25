# 문서 디렉토리

프로젝트 문서는 **카테고리별**로 정리되어 있다. 목적에 맞는 폴더에서 시작하라.

## 카테고리

| 디렉토리 | 다루는 것 | 누가 자주 보나 |
|---|---|---|
| [tracker/](tracker/README.md) | 작업 트래커 — 스프린트·이슈·고려사항 + 작업 관리 정책 | 사용자 + Claude |
| [spec/](spec/README.md) | Claude가 정확성을 위해 참조하는 정책·스키마·ADR | 주로 Claude |
| [manuals/](manuals/README.md) | 사용자가 따라하는 절차 가이드 (서버 실행 등) | 주로 사용자 |
| [status/](status/README.md) | 프로젝트 현황 스냅샷 (PROJECT·STATUS·RESUME) | 사용자 + Claude |
| [study/](study/INDEX.md) | 학습 노트 (ADR 이해, OCR 패턴 등) | 사용자 (배움 기록) |

## 빠른 진입점

- **세션 재개** → [status/RESUME.md](status/RESUME.md)
- **현재 작업 맥락** → [tracker/sprints/CURRENT.md](tracker/sprints/CURRENT.md)
- **작업 항목 확인** → [/ISSUES.md](../ISSUES.md) (root 유지)
- **데이터 스키마** → [spec/schema.md](spec/schema.md)
- **태그 vocab** → [spec/vocab.md](spec/vocab.md)
- **새 스프린트 만들기** → `/add-sprint` 스킬
- **새 이슈 등록** → `/add-issue` 스킬
- **고려사항 등록** → `/add-consideration` 스킬

## 작업 관리 모델

세 가지 단위(이슈·고려사항·스프린트)의 관계는 [tracker/work_management.md](tracker/work_management.md) 참조.

```
스프린트 (큰 맥락) ──── 포함 이슈 (작은 작업) ──── 결과
       │                       │
       └── 관련 고려사항 ── 미래 검토 항목
```

## 디렉토리 트리

```
docs/
├── README.md (이 파일)
├── tracker/
│   ├── README.md
│   ├── work_management.md
│   ├── CONSIDERATIONS.md
│   ├── sprints/
│   └── sprints_checklist/
├── spec/
│   ├── README.md
│   ├── schema.md
│   ├── vocab.md
│   ├── lyrics_format.md
│   ├── skills_policy.md
│   └── decisions/ (ADR-001~006)
├── manuals/
│   ├── README.md
│   └── server_runtime.md
├── status/
│   ├── README.md
│   ├── PROJECT.md
│   ├── STATUS.md
│   └── RESUME.md
└── study/
    ├── INDEX.md
    └── ...
```

## 정책

- 새 문서를 추가할 때 카테고리 폴더에 두고, 해당 폴더 README 인덱스에 한 줄 추가.
- cross-link는 상대 경로(`../spec/schema.md`) 사용. 절대 경로 권장 안 함.
- 폴더 외부에서 직접 링크할 일이 적은 문서는 카테고리 README의 인덱스로만 발견 가능하게.
