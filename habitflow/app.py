# -*- coding: utf-8 -*-
"""HabitFlow — HTTP-сервер (только стандартная библиотека Python).

Запуск:  python app.py  →  http://127.0.0.1:8000
API:     GET/POST /api/habits, DELETE /api/habits/{id},
         POST /api/habits/{id}/toggle, GET /api/stats, GET /api/health
"""
from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import db

BASE_DIR = Path(__file__).resolve().parent
STATIC = BASE_DIR / "static"
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HABIT_RE = re.compile(r"^/api/habits/(\d+)$")
TOGGLE_RE = re.compile(r"^/api/habits/(\d+)/toggle$")


class Handler(BaseHTTPRequestHandler):
    server_version = "HabitFlow/1.0"

    # ------------------------------------------------------------------ utils
    def _send(self, code: int, payload=None, ctype: str = "application/json; charset=utf-8"):
        body = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def log_message(self, fmt, *args):  # тише в консоли
        print("[%s] %s" % (self.command, self.path))

    # ------------------------------------------------------------------ routes
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/health":
            return self._send(200, {"ok": True, "backend": "turso" if db.use_turso() else "sqlite"})
        if path == "/api/habits":
            db.migrates()
            return self._send(200, db.list_habits())
        if path == "/api/stats":
            return self._send(200, db.stats())
        return self._static(path or "/")

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/habits":
            body = self._json_body()
            name = str(body.get("name", "")).strip()
            color = str(body.get("color") or "#4ade80")
            if not 1 <= len(name) <= 80:
                return self._send(400, {"error": "Название должно быть от 1 до 80 символов"})
            if not re.match(r"^#[0-9a-fA-F]{6}$", color):
                color = "#4ade80"
            db.migrates()
            return self._send(201, db.create_habit(name, color))

        m = TOGGLE_RE.match(path)
        if m:
            day = self._json_body().get("day")
            if day and not DAY_RE.match(str(day)):
                return self._send(400, {"error": "day должен быть в формате YYYY-MM-DD"})
            res = db.toggle(int(m.group(1)), day)
            if res is None:
                return self._send(404, {"error": "Привычка не найдена"})
            return self._send(200, res)

        return self._send(404, {"error": "Не найдено"})

    def do_DELETE(self):
        path = self.path.split("?")[0]
        m = HABIT_RE.match(path)
        if not m:
            return self._send(404, {"error": "Не найдено"})
        if not db.delete_habit(int(m.group(1))):
            return self._send(404, {"error": "Привычка не найдена"})
        return self._send(204, None)

    # ------------------------------------------------------------------ static
    def _static(self, path: str):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (STATIC / rel).resolve()
        if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
            return self._send(404, {"error": "Файл не найден"})
        ctype = {"html": "text/html; charset=utf-8", "css": "text/css; charset=utf-8",
                 "js": "application/javascript; charset=utf-8", "svg": "image/svg+xml",
                 "png": "image/png", "ico": "image/x-icon"}.get(target.suffix.lstrip("."), "text/plain")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main(port: int = 8000):
    db.migrates()
    print("HabitFlow: http://127.0.0.1:%d  (backend: %s)" % (port, "turso" if db.use_turso() else "sqlite"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    import os
    main(int(os.environ.get("PORT", "8000")))
