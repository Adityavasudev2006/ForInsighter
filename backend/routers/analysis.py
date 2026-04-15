from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from agents.orchestrator import Orchestrator
from models.database import Document, SessionLocal
from models.schemas import CompareResult, DocumentSummary, EntityData, ExtractedQuestion
from services.chart_service import ChartService


router = APIRouter(prefix="/analysis", tags=["analysis"])
orchestrator = Orchestrator()
chart_service = ChartService()


@router.post("/{doc_id}/summarize", response_model=DocumentSummary)
async def summarize_document(
    doc_id: str,
    mode: str = Query(default="local"),
    refresh: bool = Query(default=False),
    api_provider: str | None = Query(default=None),
    api_key: str | None = Query(default=None),
    ollama_base_url: str | None = Query(default=None),
    ollama_model: str | None = Query(default=None),
):
    async with SessionLocal() as session:
        doc = await session.get(Document, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        if refresh:
            key = f"summary:{doc.content_hash or doc.id}:{mode}"
            await orchestrator.cache_service.delete(key)
        if doc.summary_json and not refresh:
            return DocumentSummary.model_validate(json.loads(doc.summary_json))
        full_text = ""
        parsed = await orchestrator.parser_agent.run(doc.file_path, doc.file_type)
        full_text = parsed["full_text"]
        llm_options = {
            "mode": mode,
            "api_provider": api_provider,
            "api_key": api_key,
            "ollama_base_url": ollama_base_url,
            "ollama_model": ollama_model,
        }
        summary = await orchestrator.summarizer_agent.run(full_text, doc.content_hash or doc.id, mode=mode, llm_options=llm_options)
        if doc.profile_json:
            try:
                summary = summary.model_copy(update=json.loads(doc.profile_json))
            except Exception:
                pass
        doc.summary_json = summary.model_dump_json()
        await session.commit()
        return summary


@router.post("/{doc_id}/compare", response_model=CompareResult)
async def compare_document(
    doc_id: str,
    api_provider: str | None = Query(default=None),
    api_key: str | None = Query(default=None),
    ollama_base_url: str | None = Query(default=None),
    ollama_model: str | None = Query(default=None),
):
    async with SessionLocal() as session:
        doc = await session.get(Document, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
    return await orchestrator.process_document_compare(doc_id, doc.file_path, doc.file_type)


@router.get("/{doc_id}/questions", response_model=list[ExtractedQuestion])
async def get_questions(doc_id: str):
    async with SessionLocal() as session:
        doc = await session.get(Document, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
    if not doc.questions_json:
        return []
    return [ExtractedQuestion.model_validate(item) for item in json.loads(doc.questions_json)]


@router.get("/{doc_id}/entities", response_model=EntityData)
async def get_entities(doc_id: str):
    async with SessionLocal() as session:
        doc = await session.get(Document, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
    if not doc.entities_json:
        return EntityData()
    return EntityData.model_validate(json.loads(doc.entities_json))


@router.get("/{doc_id}/charts")
async def get_charts(doc_id: str):
    async with SessionLocal() as session:
        doc = await session.get(Document, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
    profile = json.loads(doc.profile_json) if doc.profile_json else None
    return {"charts": chart_service.build_charts(profile)}
