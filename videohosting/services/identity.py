from __future__ import annotations

from videohosting.db import SessionLocal, User
from videohosting.web.utils import AnonymousUser


async def resolve_current_user(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return AnonymousUser()

    async with SessionLocal() as session:
        user = await session.get(User, int(user_id))
        if not user:
            request.session.pop("user_id", None)
            return AnonymousUser()

    user.is_authenticated = True
    return user
