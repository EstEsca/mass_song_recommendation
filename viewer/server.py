"""
viewer/server.py — [DEPRECATED — v2 미대응 (2026-04-25~)] songs.json 편집용 로컬 HTTP 서버.

⚠️ v2 SSoT가 data/source/곡정보.xlsx로 변경되었으므로 이 단독 서버는 더 이상 사용하지 않는다.
   - songs.json에 직접 쓰기 → v2에서는 빌드 산출물이라 다음 rebuild에 덮어쓰여짐
   - 가사 4필드(본문/절별/절구조/참조URL) 편집 모델 → v2 가사는 단일 문자열
   - 신뢰도/검증완료 필드 → v2에서 폐기됨

   대신 server/app.py(FastAPI)를 사용하라. server/app.py는 v2 어댑터를 통해
   viewer/index.html을 그대로 마운트한 상태로 곡정보.xlsx에 안전하게 쓰고 자동 rebuild를 호출한다.

       python -m uvicorn server.app:app --reload   # 권장
       /editor/  경로에 viewer/index.html이 마운트됨

   본 파일은 호환성 유지용으로만 남기며, **단독 실행 금지**.

사용 (레거시 — v1 시절 동작 설명):
    python viewer/server.py          # 기본 포트 8765
    python viewer/server.py 9000     # 임의 포트

엔드포인트:
    GET  /api/songs           — songs.json 전체 반환
    PUT  /api/songs/<번호>    — 해당 곡의 가사 필드 패치 + 사용자수정시각 기록
    GET  /...                 — viewer/ 디렉토리 정적 파일 (index.html 등)
"""
import sys as _sys

print(
    "⚠ viewer/server.py는 DEPRECATED — v2 미대응.\n"
    "  대신: python -m uvicorn server.app:app --reload\n"
    "  편집기 경로: http://localhost:8000/editor/\n",
    file=_sys.stderr,
)
_sys.exit(2)

import json
import os
import shutil
import sys
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(ROOT)
SONGS_PATH = os.path.join(PROJECT_ROOT, "data", "songs.json")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/songs":
            self._serve_songs()
            return
        super().do_GET()

    def do_PUT(self):
        parsed = urlparse(self.path)
        prefix = "/api/songs/"
        if parsed.path.startswith(prefix):
            num = parsed.path[len(prefix):]
            self._update_song(num)
            return
        self.send_error(404)

    def _serve_songs(self):
        try:
            with open(SONGS_PATH, "rb") as f:
                data = f.read()
        except OSError as e:
            self.send_error(500, "songs.json read failed: %s" % e)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _update_song(self, num):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        try:
            patch = json.loads(raw) if raw else {}
        except json.JSONDecodeError as e:
            self._send_json(400, {"ok": False, "error": "invalid json: %s" % e})
            return

        try:
            with open(SONGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except OSError as e:
            self._send_json(500, {"ok": False, "error": "read failed: %s" % e})
            return

        songs = data.get("songs", {})
        if num not in songs:
            self._send_json(404, {"ok": False, "error": "song %s not found" % num})
            return

        song = songs[num]
        changed = []

        # Top-level 검증완료 toggle (independent of lyrics edits)
        if "검증완료" in patch:
            val = patch["검증완료"]
            if not isinstance(val, bool):
                self._send_json(400, {"ok": False, "error": "검증완료 must be boolean"})
                return
            song["검증완료"] = val
            changed.append("검증완료")

        lyrics_patch = patch.get("가사") or {}
        allowed = ("본문", "절별", "절구조", "참조URL")
        for key in allowed:
            if key in lyrics_patch:
                value = lyrics_patch[key]
                if key == "참조URL":
                    if not isinstance(value, list):
                        self._send_json(400, {"ok": False, "error": "참조URL must be a list of strings"})
                        return
                    cleaned = []
                    for url in value:
                        if not isinstance(url, str):
                            self._send_json(400, {"ok": False, "error": "참조URL items must be strings"})
                            return
                        u = url.strip()
                        if not u:
                            continue
                        if not (u.startswith("http://") or u.startswith("https://")):
                            self._send_json(400, {"ok": False, "error": "참조URL must start with http(s)://"})
                            return
                        cleaned.append(u)
                    value = cleaned
                song.setdefault("가사", {})[key] = value
                changed.append("가사." + key)

        if not changed:
            self._send_json(400, {"ok": False, "error": "no editable fields in patch"})
            return

        # Only content edits bump 사용자수정시각; 검증완료 toggle alone does not.
        touched_content = any(c.startswith("가사.") for c in changed)
        now = datetime.now().isoformat(timespec="seconds")
        if touched_content:
            song["사용자수정시각"] = now

        tmp = SONGS_PATH + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            shutil.move(tmp, SONGS_PATH)
        except OSError as e:
            self._send_json(500, {"ok": False, "error": "write failed: %s" % e})
            return

        resp = {"ok": True, "changed": changed}
        if touched_content:
            resp["사용자수정시각"] = now
        if "검증완료" in changed:
            resp["검증완료"] = song.get("검증완료", False)
        self._send_json(200, resp)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    addr = ("127.0.0.1", port)
    print("viewer serving on http://127.0.0.1:%d/  (Ctrl+C to stop)" % port)
    print("songs.json = %s" % SONGS_PATH)
    HTTPServer(addr, Handler).serve_forever()


if __name__ == "__main__":
    main()
