from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from models import db, User


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if not username or not email or not password:
            flash("Заполните все поля.", "error")
            return redirect(url_for("auth.register"))

        if password != password2:
            flash("Пароли не совпадают.", "error")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(username=username).first():
            flash("Пользователь с таким ником уже существует.", "error")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=email).first():
            flash("Пользователь с таким email уже существует.", "error")
            return redirect(url_for("auth.register"))

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()

        flash("Регистрация прошла успешно. Теперь вы можете войти.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth_register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email_or_username = request.form.get("login", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter(
            (User.email == email_or_username.lower())
            | (User.username == email_or_username)
        ).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Неверный логин или пароль.", "error")
            return redirect(url_for("auth.login"))

        login_user(user)
        flash("Вы вошли в аккаунт.", "success")
        return redirect(url_for("main.index"))

    return render_template("auth_login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы вышли из аккаунта.", "success")
    return redirect(url_for("main.index"))


