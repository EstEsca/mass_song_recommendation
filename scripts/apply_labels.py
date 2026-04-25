"""
apply_labels.py

LLM이 생성한 라벨링 결과 jsonl을 곡정보.xlsx에 반영한다.

입력 jsonl 한 줄 예시:
{"번호": 1, "요약": "부활하신 예수께서 제자들에게 갈릴래아로 가 만남을 전하라 하심",
 "느낌": ["활기찬", "선포"], "키워드": ["부활", "갈릴래아", "사명", "목자"]}

반영 방식:
  - 요약 시트(B열): 곡당 1셀. 비어있으면 채움. 이미 있으면 skip(--force로 덮어쓰기).
  - 색인 시트(tall): "느낌"·"키워드" 타입의 새 행 append. 중복은 skip.
  - 성경·시기·대축일·성월·역할·곡모음집은 이 스크립트에서 다루지 않음 (수동 또는 add-tag).

vocab 검증:
  - 느낌: docs/spec/vocab.md의 느낌 vocab만 허용 (활기찬·장엄한·서정적·고요한·기쁜·애원하는·선포·묵상적)
  - 키워드: 자유 (제약 없음)
  - 위반 값은 적용 안 하고 보고에 포함

xlsx 잠금 시 PermissionError → 종료.
적용 후 rebuild 안내 (자동 호출 안 함 — 사용자 다른 작업 후 일괄 rebuild 가능).

사용:
    python scripts/apply_labels.py path/to/proposals.jsonl
    python scripts/apply_labels.py path/to/proposals.jsonl --force --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "source" / "곡정보.xlsx"

# vocab (docs/spec/vocab.md와 동기화 필요)
FEELING_VOCAB = {
    "활기찬", "장엄한", "서정적", "고요한", "기쁜",
    "애원하는", "선포", "묵상적",
}


def load_records(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{ln} JSON parse error: {e}")
            if "번호" not in rec:
                raise SystemExit(f"{path}:{ln} '번호' 필드 없음")
            records.append(rec)
    return records


def num_int(v) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(str(v)))
    except (ValueError, TypeError):
        return None


def index_summary_rows(wb) -> dict[int, int]:
    """요약 시트: 번호 → row index 매핑."""
    ws = wb["요약"]
    out = {}
    for ri in range(2, ws.max_row + 1):
        n = num_int(ws.cell(row=ri, column=1).value)
        if n is not None:
            out[n] = ri
    return out


def index_existing_tags(wb) -> set[tuple[int, str, str]]:
    """색인 시트: 기존 (번호, 타입, 값) 집합 (중복 검사용)."""
    ws = wb["색인"]
    out = set()
    for ri in range(2, ws.max_row + 1):
        n = num_int(ws.cell(row=ri, column=1).value)
        t = ws.cell(row=ri, column=2).value
        v = ws.cell(row=ri, column=3).value
        if n is None or not t or not v:
            continue
        out.add((n, str(t).strip(), str(v).strip()))
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="라벨링 결과 jsonl을 곡정보.xlsx에 반영")
    p.add_argument("jsonl", help="라벨링 제안 jsonl 경로")
    p.add_argument("--force", action="store_true",
                   help="요약이 이미 있어도 덮어쓰기")
    p.add_argument("--dry-run", action="store_true",
                   help="xlsx에 쓰지 않고 결과만 출력")
    args = p.parse_args()

    src = Path(args.jsonl)
    if not src.exists():
        raise SystemExit(f"jsonl 없음: {src}")
    if not XLSX.exists():
        raise SystemExit(f"xlsx 없음: {XLSX}")

    records = load_records(src)
    print(f"[load] {len(records)}건 ← {src}")

    try:
        wb = load_workbook(XLSX)
    except PermissionError:
        raise SystemExit(
            f"xlsx 잠김 — 엑셀에서 곡정보.xlsx를 닫고 다시 시도하세요.\n  {XLSX}"
        )

    for sheet in ("곡목록", "요약", "색인"):
        if sheet not in wb.sheetnames:
            raise SystemExit(f"'{sheet}' 시트가 없습니다")

    summary_rows = index_summary_rows(wb)
    existing_tags = index_existing_tags(wb)
    ws_summary = wb["요약"]
    ws_index = wb["색인"]

    # 통계
    counts = dict(
        summary_set=0,
        summary_skipped_existing=0,
        summary_no_row=0,
        feeling_added=0,
        feeling_dup=0,
        feeling_vocab_violation=0,
        keyword_added=0,
        keyword_dup=0,
    )
    vocab_violations: list[str] = []
    no_row_samples: list[int] = []

    for rec in records:
        num = num_int(rec.get("번호"))
        if num is None:
            counts["summary_no_row"] += 1
            continue

        # 1) 요약
        summary = (rec.get("요약") or "").strip()
        if summary:
            row = summary_rows.get(num)
            if row is None:
                counts["summary_no_row"] += 1
                if len(no_row_samples) < 10:
                    no_row_samples.append(num)
            else:
                cell = ws_summary.cell(row=row, column=2)
                existing = (cell.value or "").strip() if isinstance(cell.value, str) else cell.value
                if existing and not args.force:
                    counts["summary_skipped_existing"] += 1
                else:
                    if not args.dry_run:
                        cell.value = summary
                        cell.alignment = Alignment(vertical="top", wrap_text=True)
                        cell.number_format = "@"
                    counts["summary_set"] += 1

        # 2) 느낌 (vocab 제약)
        for v in rec.get("느낌") or []:
            v = str(v).strip()
            if not v:
                continue
            if v not in FEELING_VOCAB:
                counts["feeling_vocab_violation"] += 1
                vocab_violations.append(f"번호 {num} 느낌={v!r} (vocab 위반)")
                continue
            key = (num, "느낌", v)
            if key in existing_tags:
                counts["feeling_dup"] += 1
                continue
            if not args.dry_run:
                ws_index.append([str(num), "느낌", v])
                # 새 행 텍스트 서식
                for col in range(1, 4):
                    ws_index.cell(row=ws_index.max_row, column=col).number_format = "@"
            existing_tags.add(key)
            counts["feeling_added"] += 1

        # 3) 키워드 (자유)
        for v in rec.get("키워드") or []:
            v = str(v).strip()
            if not v:
                continue
            key = (num, "키워드", v)
            if key in existing_tags:
                counts["keyword_dup"] += 1
                continue
            if not args.dry_run:
                ws_index.append([str(num), "키워드", v])
                for col in range(1, 4):
                    ws_index.cell(row=ws_index.max_row, column=col).number_format = "@"
            existing_tags.add(key)
            counts["keyword_added"] += 1

    # 저장
    saved = False
    if not args.dry_run and any(
        counts[k] > 0
        for k in ("summary_set", "feeling_added", "keyword_added")
    ):
        try:
            wb.save(XLSX)
            saved = True
        except PermissionError:
            raise SystemExit(
                f"저장 실패 — xlsx가 잠긴 것 같습니다.\n  {XLSX}"
            )

    print("\n=== 라벨링 적용 결과 ===")
    print(f"  요약 적용:                  {counts['summary_set']}곡")
    print(f"  요약 skip(이미 있음):       {counts['summary_skipped_existing']}곡")
    print(f"  요약 행 없음:               {counts['summary_no_row']}곡")
    print(f"  느낌 추가:                  {counts['feeling_added']}건")
    print(f"  느낌 skip(중복):            {counts['feeling_dup']}건")
    print(f"  느낌 vocab 위반:            {counts['feeling_vocab_violation']}건")
    print(f"  키워드 추가:                {counts['keyword_added']}건")
    print(f"  키워드 skip(중복):          {counts['keyword_dup']}건")
    if args.dry_run:
        print("  모드: DRY-RUN (xlsx 미저장)")

    if vocab_violations:
        print("\n  [vocab 위반 샘플]")
        for v in vocab_violations[:5]:
            print(f"    - {v}")

    if no_row_samples:
        print("\n  [요약 행 없음 샘플 번호]")
        print(f"    {no_row_samples}")

    if saved:
        print("\n  ⚠ xlsx만 수정됨. JSON 재빌드 필요:")
        print("     python scripts/rebuild.py")


if __name__ == "__main__":
    main()
