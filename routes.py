import os

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required

from models import db, User, Video, VideoReaction, Subscription
from services import allowed_file, generate_thumbnail, moderate_thumbnail_with_ai


bp = Blueprint("main", __name__)


@bp.route("/", endpoint="index")
def index():
    videos = Video.query.order_by(Video.created_at.desc()).all()
    return render_template("index.html", videos=videos)


@bp.route("/upload", methods=["GET", "POST"], endpoint="upload")
def upload():
    if request.method == "GET":
        return render_template("upload.html")

    title = request.form.get("title", "").strip()
    file = request.files.get("file")

    if not title:
        flash("Введите название видео.")
        return redirect(url_for("main.upload"))

    if not file or file.filename == "":
        flash("Выберите видеофайл.")
        return redirect(url_for("main.upload"))

    if not allowed_file(file.filename):
        flash("Недопустимый формат файла. Разрешены: mp4, webm, ogg, mov.")
        return redirect(url_for("main.upload"))

    filename = f"{int(current_app.logger.handlers and 0 or 0)}_{file.filename}"
    # Используем время для уникальности имени (как было раньше)
    from datetime import datetime

    filename = f"{int(datetime.utcnow().timestamp())}_{file.filename}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    thumb_filename = f"{filename}.jpg"
    thumb_path = os.path.join(current_app.config["UPLOAD_FOLDER"], thumb_filename)

    thumbnail_ok = generate_thumbnail(save_path, thumb_path)

    is_approved = True
    moderation_label = None
    moderation_score = None

    if thumbnail_ok:
        is_approved, moderation_label, moderation_score = moderate_thumbnail_with_ai(
            thumb_path
        )

    if not is_approved:
        # Удаляем загруженное видео и превью, если модерация не прошла
        try:
            if os.path.exists(save_path):
                os.remove(save_path)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
        except OSError:
            pass

        flash("Видео отклонено модерацией ИИ.", "error")
        return redirect(url_for("main.upload"))

    video = Video(
        title=title,
        filename=filename,
        thumbnail_filename=thumb_filename if thumbnail_ok else None,
        is_approved=is_approved,
        moderation_label=moderation_label,
        moderation_score=moderation_score,
    )
    db.session.add(video)
    db.session.commit()

    if not thumbnail_ok:
        flash(
            "Видео загружено, но не удалось создать превью (проверьте, что установлен ffmpeg).",
            "error",
        )
    else:
        flash("Видео успешно загружено и прошло модерацию ИИ.")
    return redirect(url_for("main.index"))


@bp.route("/video/<int:video_id>", endpoint="video_detail")
def video_detail(video_id: int):
    video = Video.query.get_or_404(video_id)
    user_reaction = None
    if current_user.is_authenticated:
        user_reaction = VideoReaction.query.filter_by(
            user_id=current_user.id, video_id=video.id
        ).first()
    return render_template("video_detail.html", video=video, user_reaction=user_reaction)


@bp.route("/like/<int:video_id>", methods=["POST"], endpoint="like_video")
@login_required
def like_video(video_id: int):
    """
    Старый эндпоинт лайков оставлен для совместимости, но теперь
    основная логика в API /api/videos/<id>/react. Здесь просто редирект.
    """
    return redirect(url_for("main.video_detail", video_id=video_id))


@bp.route("/uploads/<path:filename>", endpoint="uploaded_file")
def uploaded_file(filename: str):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@bp.route("/api/videos/<int:video_id>/react", methods=["POST"], endpoint="video_react")
@login_required
def video_react(video_id: int):
    """
    AJAX-лайки/дизлайки.
    body: {"action": "like"|"dislike"}.
    """
    video = Video.query.get_or_404(video_id)
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    if action not in {"like", "dislike"}:
        return jsonify({"error": "invalid_action"}), 400

    value = 1 if action == "like" else -1

    reaction = VideoReaction.query.filter_by(
        user_id=current_user.id, video_id=video.id
    ).first()

    if reaction and reaction.value == value:
        # Тот же самый клик — снимаем реакцию
        db.session.delete(reaction)
    else:
        if reaction:
            reaction.value = value
        else:
            reaction = VideoReaction(
                user_id=current_user.id, video_id=video.id, value=value
            )
            db.session.add(reaction)

    db.session.commit()

    # Пересчитываем агрегаты
    likes_count = VideoReaction.query.filter_by(video_id=video.id, value=1).count()
    dislikes_count = VideoReaction.query.filter_by(video_id=video.id, value=-1).count()
    video.likes = likes_count
    video.dislikes = dislikes_count
    db.session.commit()

    return jsonify(
        {
            "likes": likes_count,
            "dislikes": dislikes_count,
            "user_reaction": value if reaction and reaction.value == value else 0,
        }
    )


@bp.route("/u/<string:username>", endpoint="profile")
def profile(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    videos = (
        Video.query.filter_by(user_id=user.id)
        .order_by(Video.created_at.desc())
        .all()
    )
    is_subscribed = False
    if current_user.is_authenticated and current_user.id != user.id:
        is_subscribed = (
            Subscription.query.filter_by(
                follower_id=current_user.id, followed_id=user.id
            ).first()
            is not None
        )

    subscribers_count = Subscription.query.filter_by(followed_id=user.id).count()
    subscriptions_count = Subscription.query.filter_by(follower_id=user.id).count()

    return render_template(
        "profile.html",
        profile_user=user,
        videos=videos,
        is_subscribed=is_subscribed,
        subscribers_count=subscribers_count,
        subscriptions_count=subscriptions_count,
    )


@bp.route("/u/<string:username>/subscribe", methods=["POST"], endpoint="toggle_subscribe")
@login_required
def toggle_subscribe(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    if user.id == current_user.id:
        flash("Нельзя подписаться на себя.", "error")
        return redirect(url_for("main.profile", username=username))

    existing = Subscription.query.filter_by(
        follower_id=current_user.id, followed_id=user.id
    ).first()

    if existing:
        db.session.delete(existing)
        flash("Подписка отменена.", "success")
    else:
        sub = Subscription(follower_id=current_user.id, followed_id=user.id)
        db.session.add(sub)
        flash("Вы подписались на автора.", "success")

    db.session.commit()
    return redirect(url_for("main.profile", username=username))


