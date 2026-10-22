# SPEC — HabitFlow (техническая спецификация)

Документ построен на основе `PRD.md` (v1.0). Описывает архитектуру MVP, контракты API и модель данных.

## 1. Стек
| Слой | Технология | Почему |
|---|---|---|
| Backend | Python 3.11, `http.server` + `sqlite3` (только stdlib) | нулевые зависимости, запускается одной командой |
| БД (локально) | SQLite, файл `habits.db` | простота, транзакции, SQL |
| БД (облако, этап 2) | Turso (libSQL, HTTP API `/v2/pipeline`) | совместима с SQLite, бесплатный тариф |
| Frontend | HTML + CSS + vanilla JS (`static/index.html`) | без сборки, отдаётся тем же сервером |
| Деплой (этап 2) | Vercel Python Serverless (`api/index.py`) | публичная ссылка, переменные окружения |

## 2. Архитектура
```
браузер (static/index.html)
        │  fetch JSON
        ▼
HTTP-сервер (app.py)  ──►  слой доступа к данным (db.py)
                                   │
                            SQLite  /  Turso HTTP
```
Слои разделены: `app.py` — только маршрутизация и сериализация, `db.py` — SQL.
Так локальная и облачная версии используют один и тот же код (`TURSO_URL`/`TURSO_TOKEN` включают облако).

## 3. Модель данных
```sql
CREATE TABLE habits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
    color      TEXT    NOT NULL DEFAULT '#4ade80',
    created_at TEXT    NOT NULL DEFAULT (date('now'))
);

CREATE TABLE checkins (
    habit_id  INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    day       TEXT    NOT NULL,              -- YYYY-MM-DD
    created_at TEXT   NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (habit_id, day)
);
CREATE INDEX idx_checkins_day ON checkins(day);
```
Серия и процент **не хранятся**, а вычисляются из `checkins` — единственный источник правды.

## 4. REST API
Базовый путь `/api`. Формат — JSON, кодировка UTF-8.

| Метод | Путь | Тело | Ответ |
|---|---|---|---|
| GET | `/api/habits` | — | `200 [{id, name, color, streak, best, done30, done_today, last14:[0/1]}]` |
| POST | `/api/habits` | `{name, color?}` | `201 {id, name, color}` / `400 {error}` |
| DELETE | `/api/habits/{id}` | — | `204` / `404` |
| POST | `/api/habits/{id}/toggle` | `{day?}` (по умолчанию сегодня) | `200 {done:true|false}` |
| GET | `/api/stats` | — | `200 {habits, done_today, best_streak, avg30}` |
| GET | `/api/health` | — | `200 {ok:true, backend:"sqlite"|"turso"}` |

**Ошибки:** `{"error": "human readable message"}` с кодом 400/404/500. Все даты — UTC, `YYYY-MM-DD`.

## 5. Алгоритмы
- **streak**: идём от сегодня назад по датам; если сегодня не отмечено — старт со вчера; считаем подряд идущие дни.
- **best**: проход по сортированным датам, считается максимальная длина непрерывной последовательности.
- **done30**: `COUNT(checkins WHERE day >= today-29) / 30 * 100`, округление до целого.

## 6. Валидация и безопасность
- `name`: trim, длина 1–80, иначе `400`.
- SQL только с параметрами (`?`) — защита от инъекций.
- `day` проверяется регуляркой `^\d{4}-\d{2}-\d{2}$`.
- На этапе 2 секреты (`TURSO_URL`, `TURSO_TOKEN`) — только в переменных окружения Vercel, не в коде.

## 7. Запуск локально
```bash
python app.py          # http://127.0.0.1:8000
```

## 8. Критерии приёмки
1. `POST /api/habits` создаёт привычку → она видна в `GET /api/habits` с `streak:0`.
2. Двойной `POST /api/habits/{id}/toggle` за сегодня возвращает `true`, затем `false`.
3. Удаление привычки удаляет её отметки (каскад).
4. После перезапуска сервера данные сохраняются (файл `habits.db`).
5. Вёрстка не ломается на ширине 360 px.
