from flask import Flask
from flask_login import LoginManager

from config import Config
from models import db, init_db, User
from routes import bp as main_bp
from auth import auth_bp

login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Расширения
    db.init_app(app)
    login_manager.init_app(app)

    # Гарантируем наличие каталога загрузок для локального хранения
    import os

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Инициализация БД
    init_db(app)

    # Роуты
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    return app


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="127.0.0.1", port=5000)





