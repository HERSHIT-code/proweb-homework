# -*- coding: utf-8 -*-
"""HabitFlow API — Vercel Python Serverless Function + облачная БД Turso.

Все маршруты /api/* приходят сюда (см. rewrites в vercel.json).
Переменные окружения (Vercel → Settings → Environment Variables):
    TURSO_URL    = libsql://<db>-<org>.turso.io
    TURSO_TOKEN  = <database token>
В коде ключей нет — только os.environ.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sqlite3
import tempfile
import urllib.request
from http.server import BaseHTTPRequestHandler

TURSO_URL = os.environ.get("TURSO_URL", "").rstrip("/")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN", "")

_DB_PATH = os.environ.get("SQLITE_PATH") or os.path.join(tempfile.gettempdir(), "habitflow.db")
_SCHEMA_READY = False

DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HABIT_RE = re.compile(r"^/api/habits/(\d+)$")
TOGGLE_RE = re.compile(r"^/api/habits/(\d+)/toggle$")

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        color TEXT NOT NULL DEFAULT '#4ade80',
        created_at TEXT NOT NULL DEFAULT (date('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS checkins (
        habit_id INTEGER NOT NULL,
        day TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (habit_id, day)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_checkins_day ON checkins(day)",
]

JNUM = {int, float}


# --------------------------------------------------------------------- Turso HTTP
def _val(v):
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "real", "value": str(v)}
    return {"type": "text", "value": str(v)}


def _unval(cell):
    if not isinstance(cell, dict):
        return cell
    t = cell.get("type")
    if t == "null":
        return None
    if t == "integer":
        return int(cell["value"])
    if t == "real":
        return float(cell["value"])
    return cell.get("value")


def _sqlite_sql(stmt: str, args=()):
    """Fallback: локальный SQLite в /tmp, когда Turso не настроен.

    Нужен только для демо-деплоя без облачной БД — данные живут до перезапуска
    инстанса. Как только заданы TURSO_URL/TURSO_TOKEN, используется Turso.
    """
    global _SCHEMA_READY
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        if not _SCHEMA_READY:
            for st in SCHEMA:
                conn.execute(st)
            conn.commit()
            _SCHEMA_READY = True
        cur = conn.execute(stmt, tuple(args))
        rows = [dict(r) for r in cur.fetchall()] if cur.description else []
        conn.commit()
        return rows
    finally:
        conn.close()


def sql(stmt: str, args=()):
    if not (TURSO_URL and TURSO_TOKEN):
        return _sqlite_sql(stmt, args)
    payload = {"requests": [{"type": "execute", "stmt": {"sql": stmt,
                                                         "args": [_val(a) for a in args]}},
                            {"type": "close"}]}
    req = urllib.request.Request(
        TURSO_URL + "/v2/pipeline",
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + TURSO_TOKEN, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    first = data["results"][0]
    if first.get("type") == "error":
        raise RuntimeError(first.get("error", {}).get("message", "turso error"))
    result = (first.get("response") or {}).get("result") or {}
    cols = [c["name"] for c in result.get("cols", [])]
    return [{c: _unval(v) for c, v in zip(cols, row)} for row in result.get("rows", [])]


# --------------------------------------------------------------------- доменные функции
def today() -> str:
    return dt.date.today().isoformat()


def shift(day: str, d: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=d)).isoformat()


def streak(days: set) -> int:
    cur = today()
    if cur not in days:
        cur = shift(cur, -1)
        if cur not in days:
            return 0
    n = 0
    while cur in days:
        n += 1
        cur = shift(cur, -1)
    return n


def best(days) -> int:
    b = run = 0
    prev = None
    for d in sorted(days):
        run = run + 1 if prev and shift(prev, 1) == d else 1
        b = max(b, run)
        prev = d
    return b


def migrate():
    for st in SCHEMA:
        sql(st)


def list_habits():
    out = []
    t = today()
    for h in sql("SELECT id, name, color, created_at FROM habits ORDER BY id"):
        days = [r["day"] for r in sql("SELECT day FROM checkins WHERE habit_id = ? ORDER BY day", (h["id"],))]
        dset = set(days)
        out.append({**h,
                    "streak": streak(dset),
                    "best": best(days),
                    "total": len(days),
                    "done30": round(sum(1 for d in days if d >= shift(t, -29)) / 30 * 100),
                    "done_today": t in dset,
                    "last14": [1 if shift(t, -i) in dset else 0 for i in range(13, -1, -1)]})
    return out


def stats(habits):
    return {"habits": len(habits),
            "done_today": sum(1 for h in habits if h["done_today"]),
            "best_streak": max([h["best"] for h in habits], default=0),
            "avg30": round(sum(h["done30"] for h in habits) / len(habits)) if habits else 0}


# --------------------------------------------------------------------- handler
class handler(BaseHTTPRequestHandler):
    server_version = "HabitFlow/1.0-vercel"

    def _send(self, code: int, payload=None):
        body = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode())
        except Exception:
            return {}

    def log_message(self, *a):
        pass

    # routes -------------------------------------------------------------
    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path in ("/api/health", "/health"):
                return self._send(200, {"ok": True, "backend": "turso",
                                        "configured": bool(TURSO_URL and TURSO_TOKEN)})
            if path == "/api/habits":
                migrate()
                return self._send(200, list_habits())
            if path == "/api/stats":
                return self._send(200, stats(list_habits()))
            return self._send(404, {"error": "Не найдено"})
        except Exception as e:
            return self._send(500, {"error": str(e)})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            if path == "/api/habits":
                b = self._body()
                name = str(b.get("name", "")).strip()
                color = str(b.get("color") or "#4ade80")
                if not 1 <= len(name) <= 80:
                    return self._send(400, {"error": "Название должно быть от 1 до 80 символов"})
                if not re.match(r"^#[0-9a-fA-F]{6}$", color):
                    color = "#4ade80"
                migrate()
                sql("INSERT INTO habits (name, color) VALUES (?, ?)", (name, color))
                row = sql("SELECT id, name, color FROM habits ORDER BY id DESC LIMIT 1")[0]
                return self._send(201, row)

            m = TOGGLE_RE.match(path)
            if m:
                hid = int(m.group(1))
                day = self._body().get("day") or today()
                if not DAY_RE.match(str(day)):
                    return self._send(400, {"error": "day должен быть YYYY-MM-DD"})
                if not sql("SELECT id FROM habits WHERE id = ?", (hid,)):
                    return self._send(404, {"error": "Привычка не найдена"})
                if sql("SELECT day FROM checkins WHERE habit_id = ? AND day = ?", (hid, day)):
                    sql("DELETE FROM checkins WHERE habit_id = ? AND day = ?", (hid, day))
                    return self._send(200, {"done": False, "day": day})
                sql("INSERT INTO checkins (habit_id, day) VALUES (?, ?)", (hid, day))
                return self._send(200, {"done": True, "day": day})

            return self._send(404, {"error": "Не найдено"})
        except Exception as e:
            return self._send(500, {"error": str(e)})

    def do_DELETE(self):
        path = self.path.split("?")[0]
        try:
            m = HABIT_RE.match(path)
            if not m:
                return self._send(404, {"error": "Не найдено"})
            hid = int(m.group(1))
            if not sql("SELECT id FROM habits WHERE id = ?", (hid,)):
                return self._send(404, {"error": "Привычка не найдена"})
            sql("DELETE FROM checkins WHERE habit_id = ?", (hid,))
            sql("DELETE FROM habits WHERE id = ?", (hid,))
            return self._send(204, None)
        except Exception as e:
            return self._send(500, {"error": str(e)})
