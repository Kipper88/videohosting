## YouClone (FastAPI async prototype)

Асинхронный прототип видеохостинга в стиле YouTube на FastAPI + async SQLAlchemy.

### Что уже есть

- регистрация/логин/логаут;
- загрузка видео с превью и AI-модерацией;
- домашняя лента, поиск и вкладка подписок;
- страница просмотра видео (просмотры, лайки/дизлайки);
- комментарии;
- профили авторов и подписки.

### Новая структура проекта

```text
videohosting/
  api/
    routes/          # HTTP-слой (роутеры)
    router.py        # композиция роутеров
  core/
    config.py        # конфигурация
  db/
    base.py          # declarative base
    models.py        # ORM-модели
    session.py       # engine/session/dependencies
  services/
    files.py         # валидация файлов
    media.py         # ffmpeg/ffprobe
    moderation.py    # AI-модерация
    identity.py      # резолв текущего пользователя
    cleanup.py       # async-удаление файлов
  use_cases/
    video.py         # бизнес-логика фида, реакций, комментариев
  web/
    utils.py         # template helpers, flash messages
  main.py            # создание FastAPI-приложения
app.py               # entrypoint для `uvicorn app:app`
```

### Почему это ближе к структуре крупных проектов

- явное разделение слоёв: API / бизнес-логика / сервисы / доступ к данным;
- единая точка композиции роутов (`api/router.py`);
- зависимости и инфраструктура БД вынесены в отдельный слой (`db/session.py`);
- вспомогательная web-логика изолирована от роутов (`web/utils.py`).

### Запуск

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Откройте: `http://127.0.0.1:8000/`.
