## Movier (FastAPI async platform)

Асинхронный видеохостинг на FastAPI + async SQLAlchemy.

### Основные возможности

- роли: user / moderator / admin;
- ручная модерация (опционально, `MANUAL_MODERATION`);
- жалобы на видео;
- древовидные комментарии + лайки/дизлайки комментариев;
- Shorts-лента с бесконечной подгрузкой;
- история просмотров без дубликатов;
- базовые рекомендации по тегам и популярности за последние 24 часа.

### Структура

- `videohosting/main.py` — создание FastAPI-приложения;
- `videohosting/api/routes/` — HTTP-слой;
- `videohosting/use_cases/` — бизнес-логика;
- `videohosting/db/` — ORM и async session;
- `videohosting/services/` — медиа/файлы/identity;
- `videohosting/web/` — шаблонные helper'ы.

### Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```
