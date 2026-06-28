from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from jellyshift.web.services import review_store, run_index, runner, settings_service
from jellyshift.web.services.review_store import ReviewItem

router = APIRouter()


def _state(request: Request):
    return request.app.state.jellyshift


def _review_item_dict(item: ReviewItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "filename": item.filename,
        "path": str(item.path),
        "original_path": item.original_path,
        "moved_to": item.moved_to,
        "reason": item.reason,
        "torrent_name": item.torrent_name,
        "notes": item.notes,
        "added_at": item.added_at,
        "size_bytes": item.size_bytes,
    }


def _run_dict(record) -> dict[str, Any]:
    data = {
        "run_id": record.run_id,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "status": record.status,
        "summary": record.summary(),
        "error": record.error,
        "inputs": asdict(record.inputs) if record.inputs else None,
        "media": {
            "classified_as": record.media.classified_as,
            "tmdb_match": record.media.tmdb_match,
            "files_moved": [asdict(f) for f in record.media.files_moved],
            "files_skipped": record.media.files_skipped,
            "sent_to_review": record.media.sent_to_review,
            "review_reason": record.media.review_reason,
        },
    }
    return data


class ReviewPatch(BaseModel):
    notes: str | None = None
    new_name: str | None = None


class ProcessRequest(BaseModel):
    category: str = Field(..., pattern="^(movie|tv)$")
    dry_run: bool = False
    force: bool = False


class SettingsUpdate(BaseModel):
    tmdb_api_key: str | None = None
    movies_root: str
    tv_root: str
    review_dir: str
    category_map: dict[str, str]
    tmdb_similarity_threshold: float = 0.6
    include_episode_title: bool = True
    dry_run: bool = False
    log_level: str = "INFO"
    log_file: str | None = None
    log_max_bytes: int = 5242880
    log_backup_count: int = 3
    hook: dict[str, Any] = Field(default_factory=dict)
    web: dict[str, Any] = Field(default_factory=dict)


class PathTestRequest(BaseModel):
    path: str


@router.get("/invocations")
def list_invocations_api(
    request: Request,
    page: int = 1,
    per_page: int = 50,
    status: str | None = None,
    media_type: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    state = _state(request)
    items, total = run_index.list_invocations(
        config_dir=state.config_dir,
        log_file=state.config.log_file,
        page=page,
        per_page=per_page,
        status=status,
        media_type=media_type,
        search=search,
    )
    return {
        "items": [_run_dict(r) for r in items],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/invocations/{run_id}")
def get_invocation_api(request: Request, run_id: str) -> dict[str, Any]:
    state = _state(request)
    record = run_index.get_invocation(
        config_dir=state.config_dir,
        log_file=state.config.log_file,
        run_id=run_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Invocation not found")
    data = _run_dict(record)
    data["log_lines"] = record.log_lines
    return data


@router.get("/review")
def list_review_api(request: Request) -> dict[str, Any]:
    state = _state(request)
    items = review_store.list_items(state.config.review_dir)
    return {"items": [_review_item_dict(i) for i in items]}


@router.get("/review/{item_id}")
def get_review_api(request: Request, item_id: str) -> dict[str, Any]:
    state = _state(request)
    item = review_store.get_item(state.config.review_dir, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    return _review_item_dict(item)


@router.patch("/review/{item_id}")
def patch_review_api(request: Request, item_id: str, body: ReviewPatch) -> dict[str, Any]:
    state = _state(request)
    item = None
    if body.notes is not None:
        item = review_store.update_notes(state.config.review_dir, item_id, body.notes)
    if body.new_name is not None:
        try:
            item = review_store.rename_item(state.config.review_dir, item_id, body.new_name)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        item = review_store.get_item(state.config.review_dir, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    return _review_item_dict(item)


@router.delete("/review/{item_id}")
def delete_review_api(request: Request, item_id: str) -> dict[str, bool]:
    state = _state(request)
    if not review_store.delete_item(state.config.review_dir, item_id):
        raise HTTPException(status_code=404, detail="Review item not found")
    return {"deleted": True}


@router.post("/review/{item_id}/process")
def process_review_api(
    request: Request, item_id: str, body: ProcessRequest
) -> dict[str, Any]:
    state = _state(request)
    item = review_store.get_item(state.config.review_dir, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")

    result = runner.run_jellyshift(
        app_dir=state.app_dir,
        config_file=state.config_path,
        content_path=item.path,
        torrent_name=item.torrent_name or item.filename,
        category=body.category,
        dry_run=body.dry_run,
        force=body.force,
    )
    return {
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


@router.get("/settings")
def get_settings_api(request: Request) -> dict[str, Any]:
    state = _state(request)
    view = settings_service.load_settings(state.config_path)
    return view.to_dict(include_key=False)


@router.put("/settings")
def put_settings_api(request: Request, body: SettingsUpdate) -> dict[str, Any]:
    state = _state(request)
    payload = body.model_dump()
    view = settings_service.save_settings(state.config_path, payload)
    state.config = state.config.__class__.load(state.config_path)
    return view.to_dict(include_key=False)


@router.post("/settings/test-path")
def test_path_api(body: PathTestRequest) -> dict[str, Any]:
    ok, message = runner.test_path_writable(body.path)
    return {"ok": ok, "message": message}
