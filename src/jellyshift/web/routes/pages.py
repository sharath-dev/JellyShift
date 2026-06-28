from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from jellyshift.web.services import review_store, run_index, settings_service

router = APIRouter()


def _state(request: Request):
    return request.app.state.jellyshift


def _templates(request: Request):
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
def invocations_page(
    request: Request,
    page: int = 1,
    status: str | None = None,
    media_type: str | None = None,
    search: str | None = None,
) -> HTMLResponse:
    state = _state(request)
    items, total = run_index.list_invocations(
        config_dir=state.config_dir,
        log_file=state.config.log_file,
        page=page,
        per_page=50,
        status=status,
        media_type=media_type,
        search=search,
    )
    return _templates(request).TemplateResponse(
        request,
        "invocations.html",
        {
            "items": items,
            "total": total,
            "page": page,
            "per_page": 50,
            "status": status or "",
            "media_type": media_type or "",
            "search": search or "",
        },
    )


@router.get("/invocations/{run_id}", response_class=HTMLResponse)
def invocation_detail_page(request: Request, run_id: str) -> HTMLResponse:
    state = _state(request)
    record = run_index.get_invocation(
        config_dir=state.config_dir,
        log_file=state.config.log_file,
        run_id=run_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Invocation not found")

    review_link = None
    if record.inputs:
        for item in review_store.list_items(state.config.review_dir):
            if item.original_path == record.inputs.content_path or item.moved_to == record.inputs.content_path:
                review_link = item.id
                break

    return _templates(request).TemplateResponse(
        request,
        "invocation_detail.html",
        {
            "record": record,
            "review_link": review_link,
        },
    )


@router.get("/review", response_class=HTMLResponse)
def review_page(request: Request) -> HTMLResponse:
    state = _state(request)
    items = review_store.list_items(state.config.review_dir)
    return _templates(request).TemplateResponse(
        request,
        "review.html",
        {"items": items},
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request) -> HTMLResponse:
    state = _state(request)
    settings = settings_service.load_settings(state.config_path)
    return _templates(request).TemplateResponse(
        request,
        "settings.html",
        {"settings": settings},
    )
