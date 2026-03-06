import os
from datetime import datetime

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
from werkzeug.utils import secure_filename

from models import Subscription, User, Video, VideoComment, VideoReaction, db
from services import (
    allowed_file,
    generate_thumbnail,
    moderate_thumbnail_with_ai,
    moderate_video_content_with_ai,
    allowed_image_file,
)
from video_logic import add_comment, get_home_feed, get_related_videos, toggle_reaction

bp = Blueprint("main", __name__)


@bp.route("/", endpoint="index")
def index():
    query = request.args.get("q", "").strip()
    tab = request.args.get("tab", "home")
    only_subscriptions = tab == "subscriptions" and current_user.is_authenticated

    videos = get_home_feed(
        search=query,
        only_subscriptions=only_subscriptions,
        viewer_id=current_user.id if current_user.is_authenticated else None,
    )

    return render_template("index.html", videos=videos, query=query, tab=tab)


@bp.route("/upload", methods=["GET", "POST"], endpoint="upload")
@login_required
def upload():
    if request.method == "GET":
        return render_template("upload.html")

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    file = request.files.get("file")

    if not title:
        flash("Введите название видео.", "error")
        return redirect(url_for("main.upload"))

    if not file or file.filename == "":
        flash("Выберите видеофайл.", "error")
        return redirect(url_for("main.upload"))

    if not allowed_file(file.filename):
        flash("Недопустимый формат файла. Разрешены: mp4, webm, ogg, mov.", "error")
        return redirect(url_for("main.upload"))

    filename = f"{int(datetime.utcnow().timestamp())}_{secure_filename(file.filename)}"
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    thumb_filename = f"{filename}.jpg"
    thumb_path = os.path.join(current_app.config["UPLOAD_FOLDER"], thumb_filename)
    thumbnail_ok = generate_thumbnail(save_path, thumb_path)

    is_approved = True
    moderation_label = None
    moderation_score = None

    is_video_approved, video_moderation_label, video_moderation_score, checked_frames = moderate_video_content_with_ai(
        save_path,
        sample_count=5,
    )

    if not is_video_approved:
        for path in [save_path, thumb_path]:
            if os.path.exists(path):
                os.remove(path)
        flash(
            f"Видео отклонено AI-модерацией на одном из участков (проверено кадров: {checked_frames}).",
            "error",
        )
        return redirect(url_for("main.upload"))

    moderation_label = video_moderation_label
    moderation_score = video_moderation_score

    if thumbnail_ok:
        is_approved, thumb_label, thumb_score = moderate_thumbnail_with_ai(thumb_path)
        if not is_approved:
            for path in [save_path, thumb_path]:
                if os.path.exists(path):
                    os.remove(path)
            flash("Видео отклонено AI-модерацией превью.", "error")
            return redirect(url_for("main.upload"))

        moderation_label = f"{video_moderation_label}+{thumb_label}"
        moderation_score = max(video_moderation_score or 0.0, thumb_score or 0.0)

    video = Video(
        user_id=current_user.id,
        title=title,
        description=description,
        filename=filename,
        thumbnail_filename=thumb_filename if thumbnail_ok else None,
        is_approved=is_approved,
        moderation_label=moderation_label,
        moderation_score=moderation_score,
    )
    db.session.add(video)
    db.session.commit()

    flash("Видео опубликовано.", "success")
    return redirect(url_for("main.video_detail", video_id=video.id))


@bp.route("/video/<int:video_id>", endpoint="video_detail")
def video_detail(video_id: int):
    video = Video.query.get_or_404(video_id)
    video.views += 1
    db.session.commit()

    user_reaction = 0
    if current_user.is_authenticated:
        reaction = VideoReaction.query.filter_by(user_id=current_user.id, video_id=video.id).first()
        user_reaction = reaction.value if reaction else 0

    comments = (
        VideoComment.query.filter_by(video_id=video.id)
        .order_by(VideoComment.created_at.desc())
        .all()
    )

    related_videos = get_related_videos(video.id)

    return render_template(
        "video_detail.html",
        video=video,
        comments=comments,
        related_videos=related_videos,
        user_reaction=user_reaction,
    )


@bp.route("/video/<int:video_id>/comments", methods=["POST"], endpoint="video_comment")
@login_required
def video_comment(video_id: int):
    Video.query.get_or_404(video_id)
    text = request.form.get("text", "")
    if not add_comment(video_id=video_id, user_id=current_user.id, text=text):
        flash("Комментарий не может быть пустым.", "error")
    else:
        flash("Комментарий добавлен.", "success")
    return redirect(url_for("main.video_detail", video_id=video_id))


@bp.route("/uploads/<path:filename>", endpoint="uploaded_file")
def uploaded_file(filename: str):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@bp.route("/api/videos/<int:video_id>/react", methods=["POST"], endpoint="video_react")
@login_required
def video_react(video_id: int):
    video = Video.query.get_or_404(video_id)
    action = (request.get_json(silent=True) or {}).get("action")
    if action not in {"like", "dislike"}:
        return jsonify({"error": "invalid_action"}), 400

    likes_count, dislikes_count, user_reaction = toggle_reaction(
        video=video,
        user_id=current_user.id,
        action=action,
    )

    return jsonify(
        {
            "likes": likes_count,
            "dislikes": dislikes_count,
            "user_reaction": user_reaction,
        }
    )


@bp.route("/u/<string:username>", endpoint="profile")
def profile(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    videos = Video.query.filter_by(user_id=user.id).order_by(Video.created_at.desc()).all()

    is_subscribed = False
    if current_user.is_authenticated and current_user.id != user.id:
        is_subscribed = (
            Subscription.query.filter_by(follower_id=current_user.id, followed_id=user.id).first()
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




@bp.route("/u/<string:username>/edit", methods=["GET", "POST"], endpoint="edit_profile")
@login_required
def edit_profile(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    if user.id != current_user.id:
        flash("Можно редактировать только свой профиль.", "error")
        return redirect(url_for("main.profile", username=username))

    if request.method == "POST":
        bio = request.form.get("bio", "").strip()
        avatar = request.files.get("avatar")

        user.bio = bio[:500] if bio else None

        if avatar and avatar.filename:
            if not allowed_image_file(avatar.filename):
                flash("Недопустимый формат аватара. Разрешены: jpg, jpeg, png, webp.", "error")
                return redirect(url_for("main.edit_profile", username=username))

            avatar_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "avatars")
            os.makedirs(avatar_dir, exist_ok=True)
            safe_name = secure_filename(avatar.filename)
            avatar_filename = f"{int(datetime.utcnow().timestamp())}_{safe_name}"
            avatar_path = os.path.join(avatar_dir, avatar_filename)
            avatar.save(avatar_path)
            user.avatar_url = f"avatars/{avatar_filename}"

        db.session.commit()
        flash("Профиль обновлён.", "success")
        return redirect(url_for("main.profile", username=username))

    return render_template("profile_edit.html", profile_user=user)

@bp.route("/u/<string:username>/subscribe", methods=["POST"], endpoint="toggle_subscribe")
@login_required
def toggle_subscribe(username: str):
    user = User.query.filter_by(username=username).first_or_404()
    if user.id == current_user.id:
        flash("Нельзя подписаться на себя.", "error")
        return redirect(url_for("main.profile", username=username))

    existing = Subscription.query.filter_by(follower_id=current_user.id, followed_id=user.id).first()

    if existing:
        db.session.delete(existing)
        flash("Подписка отменена.", "success")
    else:
        db.session.add(Subscription(follower_id=current_user.id, followed_id=user.id))
        flash("Вы подписались на автора.", "success")

    db.session.commit()
    return redirect(url_for("main.profile", username=username))
