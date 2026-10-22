# AI-course-projects

Учебные проекты по курсу **AI-конструирование** (PROWEB, группа 2596): от mini-проекта
до full-stack приложения с облачной базой. Всё собрано в диалоге с ИИ-моделью,
код читаемый и запускается без установки зависимостей.

## Проекты

| Папка | Что это | Стек | Как запустить |
|---|---|---|---|
| [`mini_project/`](mini_project) | **Focus Timer** — помодоро-таймер со списком задач, сохранение в localStorage | HTML/CSS/JS, Web Audio API | открыть `index.html` |
| [`landing/`](landing) | **KofeLab** — одностраничник вымышленной кофейни: герой, услуги с ценами, форма заявки, адаптив | HTML/CSS/JS | открыть `index.html` |
| [`habitflow/`](habitflow) | **HabitFlow** — full-stack трекер привычек: PRD + SPEC + REST API + SQLite | Python stdlib (`http.server`, `sqlite3`), vanilla JS | `python app.py` → http://127.0.0.1:8000 |
| [`deploy/`](deploy) | **HabitFlow в облаке** — serverless-версия для Vercel и облачная БД Turso, ключи только в env | Python, Vercel, libSQL/Turso | см. `deploy/DEPLOY.md` |

### HabitFlow: документы и API
- Требования: [`habitflow/PRD.md`](habitflow/PRD.md) · Техническая спецификация: [`habitflow/SPEC.md`](habitflow/SPEC.md)
- `GET/POST /api/habits`, `DELETE /api/habits/{id}`, `POST /api/habits/{id}/toggle`, `GET /api/stats`, `GET /api/health`
- Серия, лучшая серия и процент за 30 дней вычисляются из таблицы `checkins` — без дублирования данных.

## Быстрый старт
```bash
git clone https://github.com/<user>/ai-course-projects.git
cd ai-course-projects/habitflow
python app.py            # http://127.0.0.1:8000
```

## Инструменты
- Git / GitHub (init → commit → push), VS Code.
- Браузерные ИИ-модели (Claude / ChatGPT / DeepSeek) для генерации и доработки кода.
- Python 3.11, SQLite, Turso (libSQL), Vercel, HTML5/CSS3/vanilla JS.

## Структура
```
ai-course-projects/
├─ mini_project/   # Focus Timer
├─ landing/        # KofeLab landing page
├─ habitflow/      # полный стек: PRD, SPEC, API, БД
└─ deploy/         # конфигурация Vercel + Turso
```
