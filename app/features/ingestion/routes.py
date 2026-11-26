"""HTTP endpoints for founder uploads (private files) and deletes."""

from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.container import Container
from app.features.ingestion import service
from app.web import get_container

router = APIRouter(tags=["ingestion"])

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ALLOWED = (".pdf", ".docx", ".txt", ".csv", ".md")


def _check_business_id(business_id: str) -> None:
    if not _ID.match(business_id):
        raise HTTPException(status_code=400, detail="business_id may use letters, digits, - and _")


@router.post("/businesses/{business_id}/documents")
async def upload(
    business_id: str,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    container: Container = Depends(get_container),
) -> dict:
    """Save a founder's file privately and index it for that business only."""
    _check_business_id(business_id)
    name = _SAFE.sub("_", Path(file.filename or "upload").name)
    if not name.lower().endswith(ALLOWED):
        raise HTTPException(status_code=400, detail=f"allowed types: {', '.join(ALLOWED)}")
    limit = container.settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        detail = f"file is over {container.settings.max_upload_mb} MB"
        raise HTTPException(status_code=413, detail=detail)
    folder = container.settings.data_dir / service.UPLOADS_DIR / business_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(data)
    result = service.ingest_upload(container, path, business_id, title=title)
    if result.status == "failed":
        raise HTTPException(status_code=422, detail=result.error)
    return asdict(result)


@router.delete("/businesses/{business_id}/documents/{name}")
def delete(business_id: str, name: str, container: Container = Depends(get_container)) -> dict:
    """Delete a founder's file, its chunks and its vectors."""
    _check_business_id(business_id)
    safe = _SAFE.sub("_", Path(name).name)
    source = f"{service.UPLOADS_DIR}/{business_id}/{safe}"
    service.delete_source(container, source)
    path = container.settings.data_dir / source
    if path.exists():
        path.unlink()
    return {"deleted": source}
