"""
일회성 도구: docs 카테고리 재배치에 따른 경로 일괄 치환.

대상: .claude/skills/*/SKILL.md, scripts/*.py, ROOT의 README.md/ISSUES.md
docs/ 내부 파일은 다루지 않음 (상대 경로가 복잡해서 수동 Edit이 안전).

치환 규칙:
  docs/schema.md         → docs/spec/schema.md
  docs/vocab.md          → docs/spec/vocab.md
  docs/skills_policy.md  → docs/spec/skills_policy.md
  docs/lyrics_format.md  → docs/spec/lyrics_format.md
  docs/CONSIDERATIONS.md → docs/tracker/CONSIDERATIONS.md
  docs/work_management.md → docs/tracker/work_management.md
  docs/PROJECT.md        → docs/status/PROJECT.md
  docs/STATUS.md         → docs/status/STATUS.md
  docs/RESUME.md         → docs/status/RESUME.md
  docs/decisions/        → docs/spec/decisions/
  docs/sprints/          → docs/tracker/sprints/  (sprints_checklist 먼저 처리해야 충돌 없음)
  docs/sprints_checklist/ → docs/tracker/sprints_checklist/

또한 상대 경로 변형(../../docs/X)도 같은 패턴.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

# 순서 중요: sprints_checklist를 sprints보다 먼저
RULES: list[tuple[str, str]] = [
    ("docs/sprints_checklist", "docs/tracker/sprints_checklist"),
    ("docs/sprints", "docs/tracker/sprints"),
    ("docs/decisions", "docs/spec/decisions"),
    ("docs/schema.md", "docs/spec/schema.md"),
    ("docs/vocab.md", "docs/spec/vocab.md"),
    ("docs/skills_policy.md", "docs/spec/skills_policy.md"),
    ("docs/lyrics_format.md", "docs/spec/lyrics_format.md"),
    ("docs/CONSIDERATIONS.md", "docs/tracker/CONSIDERATIONS.md"),
    ("docs/work_management.md", "docs/tracker/work_management.md"),
    ("docs/PROJECT.md", "docs/status/PROJECT.md"),
    ("docs/STATUS.md", "docs/status/STATUS.md"),
    ("docs/RESUME.md", "docs/status/RESUME.md"),
]

TARGET_DIRS = [
    ROOT / ".claude" / "skills",
    ROOT / "scripts",
]
TARGET_ROOT_FILES = [
    ROOT / "README.md",
    ROOT / "ISSUES.md",
]
EXTS = {".md", ".py"}

# docs/ 내부 깊이 변화로 인한 root 외부 참조의 ../ 깊이 추가.
# (적용 대상 디렉토리 prefix → 치환 규칙 리스트)
# 우선순위: 더 깊은 (specific) prefix가 먼저
DEPTH_RULES: list[tuple[str, list[tuple[str, str]]]] = [
    # 3단계 (depth 3 → depth 3) 동일하지만 옛 2단계 기준 → 3단계 root 참조: ../../ → ../../../
    ("docs/spec/decisions", [
        ("../../ISSUES.md", "../../../ISSUES.md"),
        ("../../scripts/", "../../../scripts/"),
        ("../../.claude/", "../../../.claude/"),
        ("../../server/", "../../../server/"),
        ("../../viewer/", "../../../viewer/"),
        ("../../data/", "../../../data/"),
    ]),
    ("docs/tracker/sprints/", [
        ("../../ISSUES.md", "../../../ISSUES.md"),
        ("../../scripts/", "../../../scripts/"),
        ("../../.claude/", "../../../.claude/"),
        ("../../server/", "../../../server/"),
        ("../../viewer/", "../../../viewer/"),
        ("../../data/", "../../../data/"),
    ]),
    ("docs/tracker/sprints_checklist/", [
        ("../../ISSUES.md", "../../../ISSUES.md"),
        ("../../scripts/", "../../../scripts/"),
        ("../../.claude/", "../../../.claude/"),
        ("../../server/", "../../../server/"),
        ("../../data/", "../../../data/"),
    ]),
    # 2단계 (1→2) — 이전 docs/X.md (1단계 root 참조 ../) → 새 docs/CAT/X.md (2단계 root 참조 ../../)
    ("docs/tracker/", [
        ("../ISSUES.md", "../../ISSUES.md"),
    ]),
    ("docs/spec/", [
        ("../ISSUES.md", "../../ISSUES.md"),
    ]),
    ("docs/status/", [
        ("../ISSUES.md", "../../ISSUES.md"),
    ]),
]


SELF_PATH = Path(__file__).resolve()


def gather_files() -> list[Path]:
    files: list[Path] = []
    for d in TARGET_DIRS:
        if not d.exists():
            continue
        for ext in EXTS:
            files.extend(d.rglob(f"*{ext}"))
    for f in TARGET_ROOT_FILES:
        if f.exists():
            files.append(f)
    # docs/ 내부 (depth 보정 대상)
    docs_dir = ROOT / "docs"
    if docs_dir.exists():
        for ext in EXTS:
            files.extend(docs_dir.rglob(f"*{ext}"))
    # 자기 자신 제외 (RULES에 옛 경로가 문자열로 있어 self-match 발생)
    return [f for f in files if f.resolve() != SELF_PATH]


def transform(text: str, file_path: Path | None = None) -> tuple[str, int]:
    n = 0
    for old, new in RULES:
        if old in text:
            new_text = text.replace(old, new)
            n += text.count(old)
            text = new_text
    # depth 보정 (docs/ 내부 파일 한정, prefix 매칭)
    if file_path is not None:
        rel = str(file_path.resolve()).replace("\\", "/")
        for prefix, rules in DEPTH_RULES:
            # prefix 매칭: rel이 .../prefix... 포함
            if f"/{prefix}" in rel:
                for old, new in rules:
                    if old in text:
                        new_text = text.replace(old, new)
                        n += text.count(old)
                        text = new_text
                # 가장 specific prefix 적용 후 종료 (다른 덜 specific prefix 적용 방지)
                break
    return text, n


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="변경 없이 결과만 출력")
    args = parser.parse_args()

    files = gather_files()
    print(f"[scan] {len(files)}개 파일 점검")

    total_changes = 0
    changed_files = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new_text, n = transform(text, f)
        if n > 0:
            total_changes += n
            changed_files.append((f, n))
            if not args.dry_run:
                f.write_text(new_text, encoding="utf-8")

    print(f"\n=== {'DRY-RUN' if args.dry_run else '적용'} 결과 ===")
    print(f"  변경된 파일: {len(changed_files)}개")
    print(f"  치환 횟수:    {total_changes}건\n")
    for f, n in changed_files:
        rel = f.relative_to(ROOT)
        print(f"  [{n:>3}] {rel}")


if __name__ == "__main__":
    main()
