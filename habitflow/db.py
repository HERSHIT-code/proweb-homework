# -*- coding: utf-8 -*-
"""HabitFlow — слой доступа к данным (SQLite / Turso).

Локально используется стандартный модуль sqlite3 (файл habits.db).
Если заданы переменные окружения TURSO_URL и TURSO_TOKEN — тот же SQL
уходит в облачную libSQL-базу Turso через HTTP API /v2/pipeline.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("HABITS_DB", BASE_DIR / "habits.db"))
TURSO_URL = os.environ.get("TURSO_URL", "").rstrip("/")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN", "")

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS habits (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       TEXT    NOT NULL,
        color      TEXT    NOT NULL DEFAULT '#4ade80',
        created_at TEXT    NOT NULL DEFAULT (date('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS checkins (
        habit_id   INTEGER NOT NULL,
        day        TEXT    NOT NULL,
        created_at TEXT    NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (habit_id, day)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_checkins_day ON checkins(day)",
]

JSON_TYPES = {int: "integer", str: "text", float: "real", type(None): "null"}


# --------------------------------------------------------------------------- raw SQL
def _turso(sql: str, args: list | None = None) -> list[dict]:
    """Выполнить один запрос в Turso через HTTP-протокол libSQL."""
    payload = {
        "requests": [
            {"type": "execute", "stmt": {"sql": sql,
                                         "args": [_val(a) for a in (args or [])]}},
            {"type": "close"},
        ]
    }
    req = urllib.request.Request(
        TURSO_URL + "/v2/pipeline",
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + TURSO_TOKEN,
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    first = data["results"][0]
    if first.get("type") == "error":
        raise RuntimeError(first["error"].get("message", "turso error"))
    res = first.get("response", {}).get("result", {}) or {}
    cols = [c["name"] for c in res.get("cols", [])]
    rows = []
    for row in res.get("rows", []):
        rows.append({c: _unval(v) for c, v in zip(cols, row)})
    return rows


def _val(v):
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": str(int(v))}
    return {"type": JSON_TYPES.get(type(v), "text"), "value": str(v)}


def _unval(cell):
    if not isinstance(cell, dict):
        return cell
    t, v = cell.get("type"), cell.get("value")
    if t == "null":
        return None
    if t == "integer":
        return int(v)
    if t == "real":
        return float(v)
    return v


def use_turso() -> bool:
    return bool(TURSO_URL and TURSO_TOKEN)


def query(sql: str, args: tuple | list = ()) -> list[dict]:
    if use_turso():
        return _turso(sql, list(args))
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql, args)
        if cur.description is None:
            conn.commit()
            return []
        return [dict(r) for r in cur.fetchall()]


def migrates() -> None:
    if use_turso():
        for stmt in SCHEMA:
            _turso(stmt)
    else:
        with sqlite3.connect(DB_PATH) as conn:
            for stmt in SCHEMA:
                conn.execute(stmt)
            conn.commit()


# --------------------------------------------------------------------------- helpers
def today() -> str:
    return dt.date.today().isoformat()


def _shift(day: str, delta: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=delta)).isoformat()


def _streak(days: set[str]) -> int:
    """Текущая серия: считаем подряд идущие дни до сегодня (или до вчера)."""
    cursor = today()
    if cursor not in days:
        cursor = _shift(cursor, -1)
        if cursor not in days:
            return 0
    n = 0
    while cursor in days:
        n += 1
        cursor = _shift(cursor, -1)
    return n


def _best(days: list[str]) -> int:
    best = run = 0
    prev = None
    for d in sorted(days):
        run = run + 1 if prev and _shift(prev, 1) == d else 1
        best = max(best, run)
        prev = d
    return best


# --------------------------------------------------------------------------- CRUD
def list_habits() -> list[dict]:
    habits = query("SELECT id, name, color, created_at FROM habits ORDER BY id")
    out = []
    t = today()
    for h in habits:
        rows = query("SELECT day FROM checkins WHERE habit_id = ? ORDER BY day", (h["id"],))
        days = [r["day"] for r in rows]
        dset = set(days)
        last14 = [1 if _shift(t, -i) in dset else 0 for i in range(13, -1, -1)]
        done30 = round(sum(1 for d in days if d >= _shift(t, -29)) / 30 * 100)
        out.append({**h,
                    "streak": _streak(dset),
                    "best": _best(days),
                    "total": len(days),
                    "done30": done30,
                    "done_today": t in dset,
                    "last14": last14})
    return out


def create_habit(name: str, color: str = "#4ade80") -> dict:
    query("INSERT INTO habits (name, color) VALUES (?, ?)", (name, color))
    row = query("SELECT id, name, color FROM habits ORDER BY id DESC LIMIT 1")[0]
    return row


def delete_habit(habit_id: int) -> bool:
    exists = query("SELECT id FROM habits WHERE id = ?", (habit_id,))
    if not exists:
        return False
    query("DELETE FROM checkins WHERE habit_id = ?", (habit_id,))
    query("DELETE FROM habits WHERE id = ?", (habit_id,))
    return True


def toggle(habit_id: int, day: str | None = None) -> dict | None:
    if not query("SELECT id FROM habits WHERE id = ?", (habit_id,)):
        return None
    day = day or today()
    found = query("SELECT day FROM checkins WHERE habit_id = ? AND day = ?", (habit_id, day))
    if found:
        query("DELETE FROM checkins WHERE habit_id = ? AND day = ?", (habit_id, day))
        return {"done": False, "day": day}
    query("INSERT INTO checkins (habit_id, day) VALUES (?, ?)", (habit_id, day))
    return {"done": True, "day": day}


def stats() -> dict:
    habits = list_habits()
    return {
        "habits": len(habits),
        "done_today": sum(1 for h in habits if h["done_today"]),
        "best_streak": max([h["best"] for h in habits], default=0),
        "avg30": round(sum(h["done30"] for h in habits) / len(habits)) if habits else 0,
    }
