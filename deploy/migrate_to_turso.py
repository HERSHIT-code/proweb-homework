# -*- coding: utf-8 -*-
"""Перенос данных HabitFlow из локальной SQLite в облачную Turso.

Использование:
    set TURSO_URL=libsql://...
    set TURSO_TOKEN=...
    python migrate_to_turso.py
Скрипт создаёт схему в Turso и копирует таблицы habits / checkins (дубликаты пропускаются).
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.request

TURSO_URL = os.environ.get("TURSO_URL", "").rstrip("/")
TURSO_TOKEN = os.environ.get("TURSO_TOKEN", "")
DB_PATH = os.environ.get("HABITS_DB", os.path.join(os.path.dirname(__file__), "..", "habitflow", "habits.db"))

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


def ex(sql: str, args=()):
    if not (TURSO_URL and TURSO_TOKEN):
        sys.exit("Задайте TURSO_URL и TURSO_TOKEN в переменных окружения")
    body = {"requests": [{"type": "execute",
                          "stmt": {"sql": sql,
                                   "args": [{"type": "null"} if a is None else
                                            {"type": "integer", "value": str(a)} if isinstance(a, int) else
                                            {"type": "text", "value": str(a)} for a in args]}},
                         {"type": "close"}]}
    req = urllib.request.Request(TURSO_URL + "/v2/pipeline", data=json.dumps(body).encode(),
                                 method="POST",
                                 headers={"Authorization": "Bearer " + TURSO_TOKEN,
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.loads(r.read().decode())["results"][0]
    if res.get("type") == "error":
        raise RuntimeError(res["error"].get("message"))
    return res


def main():
    for st in SCHEMA:
        ex(st)
    print("schema ok")

    if not os.path.exists(DB_PATH):
        print("локальной базы нет — схема создана, данных для переноса нет")
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        habits = [dict(r) for r in conn.execute("SELECT id, name, color, created_at FROM habits")]
        checkins = [dict(r) for r in conn.execute("SELECT habit_id, day FROM checkins")]

    for h in habits:
        ex("INSERT OR IGNORE INTO habits (id, name, color, created_at) VALUES (?, ?, ?, ?)",
           (h["id"], h["name"], h["color"], h["created_at"]))
    print("habits:", len(habits))
    for c in checkins:
        ex("INSERT OR IGNORE INTO checkins (habit_id, day) VALUES (?, ?)", (c["habit_id"], c["day"]))
    print("checkins:", len(checkins))
    print("готово: данные перенесены в Turso")


if __name__ == "__main__":
    main()
