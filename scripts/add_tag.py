"""
add_tag.py

곡정보.xlsx의 '색인' 시트에 (번호, 타입, 값) 행을 append.

vocab 검증:
  - 느낌: docs/spec/vocab.md의 8개만 (활기찬·장엄한·서정적·고요한·기쁜·애원하는·선포·묵상적)
  - 역할: 10개 (입당·봉헌·성체·파견·묵상·감사·찬미·화답·주님의기도·마침)
  - 시기: 5개 (대림·성탄·사순·부활·연중)
  - 성월: 1월~12월
  - 성경: 정규 형식 {책}{장}[:{절시작}[-{절끝}]] (validation 약식)
  - 대축일·키워드·곡모음집: 자유

중복 검사:
  - 이미 동일 (번호, 타입, 값) 행이 존재하면 skip
  - 새 행에 추가될 때 'append'

사용:
    python scripts/add_tag.py 2 키워드 갈릴래아
    python scripts/add_tag.py 2 느낌 활기찬 선포        # 여러 값
    python scripts/add_tag.py 12,87 성월 5월              # 여러 곡 (쉼표 구분)
    python scripts/add_tag.py 1-10 시기 부활              # 범위
    python scripts/add_tag.py 50 성경 마태28:16-20

xlsx 잠금 시 PermissionError → 종료.
적용 후 rebuild 안내 (자동 호출 안 함).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from openpyxl import load_workbook

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "source" / "곡정보.xlsx"

# vocab (docs/spec/vocab.md와 동기화 필요)
VOCAB = {
    "느낌": {"활기찬", "장엄한", "서정적", "고요한", "기쁜", "애원하는", "선포", "묵상적"},
    "역할": {"입당", "봉헌", "성체", "파견", "묵상", "감사", "찬미", "화답", "주님의기도", "마침"},
    "시기": {"대림", "성탄", "사순", "부활", "연중"},
    "성월": {f"{m}월" for m in range(1, 13)},
}
VALID_TYPES = {"성경", "성월", "시기", "대축일", "역할", "느낌", "키워드", "곡모음집"}

SCRIPTURE_RE = re.compile(r"^[1-2]?[가-힣]+\d+(?::\d+(?:-\d+)?)?$")


def parse_target_nums(raw: str) -> list[int]:
    """'2', '12,87', '1-10', '32,38,40-45' 등을 곡 번호 리스트로."""
    nums: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk or "~" in chunk:
            chunk = chunk.replace("~", "-")
            a, b = chunk.split("-", 1)
            nums.extend(range(int(a), int(b) + 1))
        else:
            nums.append(int(chunk))
    return sorted(set(nums))


def validate_value(type_name: str, value: str) -> str | None:
    """반환: 위반 사유 문자열 또는 None(통과)."""
    if type_name in VOCAB:
        allowed = VOCAB[type_name]
        if value not in allowed:
            sample = ", ".join(sorted(allowed))
            return f"vocab 위반 (허용: {sample})"
        return None
    if type_name == "성경":
        if not SCRIPTURE_RE.match(value):
            return "성경 정규 형식 위반 — 예: 마태28:16-20, 시편23, 요한6:51"
        return None
    # 대축일, 키워드, 곡모음집: 자유
    return None


def num_int(v) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(str(v)))
    except (ValueError, TypeError):
        return None


def main() -> None:
    p = argparse.ArgumentParser(
        description="곡정보.xlsx의 색인 시트에 태그 추가",
    )
    p.add_argument("targets", help="곡 번호. 예: 2, 12,87, 1-10")
    p.add_argument("type", help=f"타입 ({'/'.join(sorted(VALID_TYPES))})")
    p.add_argument("values", nargs="+", help="값 (여러 개 가능)")
    p.add_argument("--dry-run", action="store_true", help="xlsx에 쓰지 않고 결과만 출력")
    args = p.parse_args()

    if args.type not in VALID_TYPES:
        raise SystemExit(
            f"타입 위반: {args.type!r}\n허용: {', '.join(sorted(VALID_TYPES))}"
        )

    # 값 vocab 검증 (먼저 — 실패 시 xlsx 열기 전에 종료)
    rejected: list[tuple[str, str]] = []
    accepted_values: list[str] = []
    for v in args.values:
        v = v.strip()
        if not v:
            continue
        reason = validate_value(args.type, v)
        if reason:
            rejected.append((v, reason))
        else:
            accepted_values.append(v)

    if rejected:
        print(f"[reject] vocab 위반 {len(rejected)}건:")
        for v, r in rejected:
            print(f"  - {v!r}: {r}")
        if not accepted_values:
            raise SystemExit("적용할 값이 없습니다.")

    if not accepted_values:
        raise SystemExit("적용할 값이 없습니다.")

    nums = parse_target_nums(args.targets)
    if not nums:
        raise SystemExit("곡 번호를 파싱하지 못했습니다.")

    if not XLSX.exists():
        raise SystemExit(f"xlsx 없음: {XLSX}")

    try:
        wb = load_workbook(XLSX)
    except PermissionError:
        raise SystemExit(
            f"xlsx 잠김 — 엑셀에서 곡정보.xlsx를 닫고 다시 시도하세요.\n  {XLSX}"
        )

    if "색인" not in wb.sheetnames or "곡목록" not in wb.sheetnames:
        raise SystemExit("'색인' 또는 '곡목록' 시트가 없습니다")

    # 곡 번호 존재 확인
    ws_list = wb["곡목록"]
    valid_nums: set[int] = set()
    for ri in range(2, ws_list.max_row + 1):
        n = num_int(ws_list.cell(row=ri, column=1).value)
        if n is not None:
            valid_nums.add(n)
    invalid = [n for n in nums if n not in valid_nums]
    if invalid:
        print(f"[warn] 곡목록에 없는 번호 {len(invalid)}개 무시: {invalid[:10]}{'...' if len(invalid) > 10 else ''}")
        nums = [n for n in nums if n in valid_nums]

    if not nums:
        raise SystemExit("유효한 번호가 없습니다.")

    # 기존 (번호, 타입, 값) 집합 (중복 체크)
    ws_index = wb["색인"]
    existing: set[tuple[int, str, str]] = set()
    for ri in range(2, ws_index.max_row + 1):
        n = num_int(ws_index.cell(row=ri, column=1).value)
        t = ws_index.cell(row=ri, column=2).value
        v = ws_index.cell(row=ri, column=3).value
        if n is None or not t or not v:
            continue
        existing.add((n, str(t).strip(), str(v).strip()))

    added = 0
    duplicate = 0
    for num in nums:
        for v in accepted_values:
            key = (num, args.type, v)
            if key in existing:
                duplicate += 1
                continue
            if not args.dry_run:
                ws_index.append([str(num), args.type, v])
                for col in range(1, 4):
                    ws_index.cell(row=ws_index.max_row, column=col).number_format = "@"
            existing.add(key)
            added += 1

    if added > 0 and not args.dry_run:
        try:
            wb.save(XLSX)
        except PermissionError:
            raise SystemExit(
                f"저장 실패 — xlsx가 잠긴 것 같습니다.\n  {XLSX}"
            )

    print()
    print(f"=== add-tag 결과 ===")
    print(f"  대상 곡: {len(nums)}개 — {nums[:10]}{'...' if len(nums) > 10 else ''}")
    print(f"  타입:    {args.type}")
    print(f"  값:      {accepted_values}")
    print(f"  추가:    {added}건")
    print(f"  중복:    {duplicate}건")
    if rejected:
        print(f"  거부:    {len(rejected)}건 (vocab 위반)")
    if args.dry_run:
        print(f"  모드:    DRY-RUN (xlsx 미저장)")
    if added > 0 and not args.dry_run:
        print()
        print("  ⚠ xlsx만 수정됨. JSON 재빌드 필요:")
        print("     python scripts/rebuild.py")


if __name__ == "__main__":
    main()
