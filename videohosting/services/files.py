def _has_allowed_extension(filename: str, allowed_extensions: set[str]) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def allowed_file(filename: str) -> bool:
    return _has_allowed_extension(filename, {"mp4", "webm", "ogg", "mov"})


def allowed_image_file(filename: str) -> bool:
    return _has_allowed_extension(filename, {"jpg", "jpeg", "png", "webp"})
