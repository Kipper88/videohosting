from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates


templates = Jinja2Templates(directory="templates")


@dataclass
class AnonymousUser:
    id: int | None = None
    username: str = ""
    is_authenticated: bool = False


def flash(request: Request, message: str, category: str = "info") -> None:
    flashes = request.session.get("flashes", [])
    flashes.append((category, message))
    request.session["flashes"] = flashes


def pop_flashes(request: Request) -> list[tuple[str, str]]:
    flashes = request.session.pop("flashes", [])
    return [(str(c), str(m)) for c, m in flashes]


def template_response(request: Request, template_name: str, context: dict, status_code: int = 200):
    def url_for(name: str, **params):
        query_params = {}
        path_params = {}
        for key, value in params.items():
            if value is None:
                continue
            if key in {"q", "tab"}:
                query_params[key] = value
            else:
                path_params[key] = value

        base = str(request.url_for(name, **path_params))
        if not query_params:
            return base
        return f"{base}?{urlencode(query_params)}"

    payload = {
        "request": request,
        "url_for": url_for,
        "current_user": getattr(request.state, "current_user", AnonymousUser()),
        "flashes": pop_flashes(request),
    }
    payload.update(context)
    return templates.TemplateResponse(template_name, payload, status_code=status_code)


def redirect_with_flash(request: Request, url: str, message: str, category: str = "info"):
    flash(request, message, category)
    return RedirectResponse(url=url, status_code=303)
