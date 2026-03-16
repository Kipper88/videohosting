## YouClone (FastAPI async prototype)

Асинхронный прототип видеохостинга в стиле YouTube на FastAPI + async SQLAlchemy.

### Что уже есть

- регистрация/логин/логаут;
- загрузка видео с превью и AI-модерацией;
- домашняя лента, поиск и вкладка подписок;
- страница просмотра видео (просмотры, лайки/дизлайки);
- комментарии;
- профили авторов и подписки.

### Структура

- `app.py` — создание и конфигурация FastAPI-приложения;
- `auth.py` — маршруты авторизации;
- `main_routes/` — web/API-маршруты;
- `video_logic.py` — асинхронный бизнес-слой (лента, реакции, комментарии);
- `models.py` — асинхронные модели БД и engine/session;
- `services/` — файлы/медиа/модерация.

### Запуск

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Откройте: `http://127.0.0.1:8000/`.
