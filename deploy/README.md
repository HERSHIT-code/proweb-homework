# HabitFlow — облачная версия (Vercel + Turso)

Полное описание деплоя: **см. `DEPLOY.md`**.

Коротко:
1. `turso db create habitflow` → `turso db show habitflow --url` → `turso db tokens create habitflow`
2. В Vercel: `TURSO_URL`, `TURSO_TOKEN` в Environment Variables.
3. `vercel --prod` → публичная ссылка вида `https://habitflow-xxxx.vercel.app`.
4. `python migrate_to_turso.py` — создаёт таблицы в Turso и копирует данные из локальной `habits.db`.

Приложение переиспользует тот же код, что локальная версия: отличий в бизнес-логике нет,
меняется только слой БД (SQLite → Turso HTTP `/v2/pipeline`) и хостинг (localhost → Vercel).
