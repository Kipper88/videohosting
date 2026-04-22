from fastapi import APIRouter, Request

from videohosting.use_cases.video import get_home_feed
from videohosting.web.utils import template_response

router = APIRouter()


@router.get("/", name="main.index")
async def index(request: Request):
    query = request.query_params.get("q", "").strip()
    tab = request.query_params.get("tab", "home")
    user = request.state.current_user
    only_subscriptions = tab == "subscriptions" and user.is_authenticated

    videos = await get_home_feed(
        search=query,
        only_subscriptions=only_subscriptions,
        viewer_id=user.id if user.is_authenticated else None,
    )
    return template_response(request, "index.html", {"videos": videos, "query": query, "tab": tab})
