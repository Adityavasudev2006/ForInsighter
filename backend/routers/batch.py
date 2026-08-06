from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException

from models.database import BatchJob, Document, SessionLocal
from models.schemas import BatchRequest, BatchStatusResponse
from tasks.celery_tasks import process_batch_task


router = APIRouter(prefix="/batch", tags=["batch"])


@router.post("")
async def start_batch(payload: BatchRequest):
    async with SessionLocal() as session:
        for doc_id in payload.doc_ids:
            doc = await session.get(Document, doc_id)
            if doc is None:
                raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
        task_id = str(uuid.uuid4())
        row = BatchJob(
            task_id=task_id,
            doc_ids_json=json.dumps(payload.doc_ids),
            status="queued",
            total=len(payload.doc_ids),
            completed=0,
            failed=0,
        )
        session.add(row)
        await session.commit()
    process_batch_task.delay(task_id, payload.doc_ids, "local")
    return {"task_id": task_id}


@router.get("/{task_id}", response_model=BatchStatusResponse)
async def batch_status(task_id: str):
    async with SessionLocal() as session:
        batch = await session.get(BatchJob, task_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch task not found")
    return BatchStatusResponse(
        task_id=batch.task_id,
        status=batch.status,
        total=batch.total,
        completed=batch.completed,
        failed=batch.failed,
    )
