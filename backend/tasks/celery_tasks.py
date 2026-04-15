from __future__ import annotations

import asyncio
import json
import os

from celery import Celery
from sqlalchemy import select

from agents.orchestrator import Orchestrator
from models.database import BatchJob, Document, SessionLocal


redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("doc_platform", broker=redis_url, backend=redis_url)
orchestrator = Orchestrator()


async def _save_document_result(doc_id: str, result: dict):
    async with SessionLocal() as session:
        doc = await session.get(Document, doc_id)
        if doc is None:
            return
        summary_payload = dict(result["summary"])
        if isinstance(result.get("profile"), dict):
            summary_payload.update(result["profile"])
        doc.summary_json = json.dumps(summary_payload)
        doc.questions_json = json.dumps(result["questions"])
        doc.entities_json = json.dumps(result["entities"])
        if result.get("profile") is not None:
            doc.profile_json = json.dumps(result["profile"])
        if result.get("view_manifest") is not None:
            doc.view_manifest_json = json.dumps(result["view_manifest"])
        doc.doc_type = result["doc_type"]
        doc.status = "done"
        doc.processing_error = None
        await session.commit()


@celery_app.task(name="process_document_task")
def process_document_task(doc_id, file_path, file_type, mode, llm_options=None):
    async def runner():
        async with SessionLocal() as session:
            doc = await session.get(Document, doc_id)
            if doc is None:
                return
            doc.status = "processing"
            await session.commit()
        try:
            result = await orchestrator.process_document(doc_id, file_path, file_type, mode=mode, llm_options=llm_options or {})
            await _save_document_result(doc_id, result)
        except Exception as exc:
            async with SessionLocal() as session:
                doc = await session.get(Document, doc_id)
                if doc is not None:
                    doc.status = "failed"
                    doc.processing_error = str(exc)[:2000]
                    await session.commit()

    asyncio.run(runner())


@celery_app.task(name="process_batch_task")
def process_batch_task(task_id, doc_ids, mode):
    async def runner():
        async with SessionLocal() as session:
            batch = await session.get(BatchJob, task_id)
            if batch is None:
                return
            batch.status = "processing"
            await session.commit()
        for doc_id in doc_ids:
            ok = True
            async with SessionLocal() as session:
                doc = await session.get(Document, doc_id)
                if doc is None:
                    ok = False
                else:
                    file_path, file_type = doc.file_path, doc.file_type
            if ok:
                try:
                    process_document_task(doc_id, file_path, file_type, mode)
                except Exception:
                    ok = False
            async with SessionLocal() as session:
                batch = await session.get(BatchJob, task_id)
                if batch is None:
                    continue
                if ok:
                    batch.completed += 1
                else:
                    batch.failed += 1
                if (batch.completed + batch.failed) >= batch.total:
                    batch.status = "done"
                await session.commit()

    asyncio.run(runner())
