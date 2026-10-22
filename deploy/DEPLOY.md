# HabitFlow → облако: Vercel + Turso

Перенос приложения с локальной SQLite-базы на облачную Turso и деплой на Vercel,
чтобы оно открывалось по публичной ссылке. Секреты — только в переменных окружения.

## Структура
```
deploy/
├─ api/index.py          # serverless-функция: весь REST API + доступ к Turso по HTTP
├─ public/index.html     # тот же интерфейс, что и в локальной версии
├─ vercel.json           # все /api/* → api/index.py
├─ requirements.txt      # сторонних зависимостей нет (только stdlib)
├─ migrate_to_turso.py   # создаёт таблицы в Turso и переносит данные из habits.db
├─ .env.example          # шаблон переменных окружения
└─ DEPLOY.md
```

## Шаг 1. Облачная база Turso
```bash
# установка CLI (один раз)
curl -sSfL https://get.tur.so/install.sh | bash

turso auth signup            # или: turso auth login
turso db create habitflow    # создаём базу
turso db show habitflow --url          # → libsql://habitflow-<org>.turso.io
turso db tokens create habitflow       # → токен доступа
```

## Шаг 2. Переменные окружения
Локально (`.env`, в git не попадает):
```bash
TURSO_URL=libsql://habitflow-<org>.turso.io
TURSO_TOKEN=<token>
```
Перенос данных из локальной базы:
```bash
python migrate_to_turso.py            # создаст таблицы и скопирует привычки/отметки
```

## Шаг 3. Деплой на Vercel
```bash
npm i -g vercel
vercel login
vercel                     # превью-деплой
vercel --prod              # продакшн: выдаёт публичную ссылку
```
Переменные в Vercel: **Project → Settings → Environment Variables** →
`TURSO_URL`, `TURSO_TOKEN` (Environment: Production + Preview), затем `vercel --prod` ещё раз.

## Шаг 4. Проверка
```bash
curl https://<project>.vercel.app/api/health
# {"ok": true, "backend": "turso", "configured": true}

curl https://<project>.vercel.app/api/habits
```

## Почему ключи не в коде
- `TURSO_URL` и `TURSO_TOKEN` читаются только через `os.environ`.
- `.env` и `.env.local` перечислены в `.gitignore`.
- В репозиторий попадает лишь `.env.example` с пустыми значениями.
