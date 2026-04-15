from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from agents.orchestrator import Orchestrator
from models.database import Document, SessionLocal
from models.schemas import SearchResult


router = APIRouter(prefix="/search", tags=["search"])
orchestrator = Orchestrator()


class SearchRequest(BaseModel):
    query: str
    doc_ids: list[str] = Field(default_factory=list)


@router.post("", response_model=list[SearchResult])
async def semantic_search(payload: SearchRequest):
    query_embedding = orchestrator.embedding_service.embed_one(payload.query)
    results: list[dict] = []
    if payload.doc_ids:
        for doc_id in payload.doc_ids:
            matches = orchestrator.chroma_service.query(doc_id, query_embedding, n_results=10)
            for item in matches:
                results.append({"doc_id": doc_id, **item})
    else:
        results = orchestrator.chroma_service.query_all(query_embedding, n_results=10)
    doc_lookup: dict[str, str] = {}
    async with SessionLocal() as session:
        query = await session.execute(select(Document.id, Document.filename))
        doc_lookup = {row[0]: row[1] for row in query.all()}
    out = [
        SearchResult(
            doc_id=item["doc_id"],
            filename=doc_lookup.get(item["doc_id"], "unknown"),
            snippet=item["text"][:220],
            score=float(item["distance"]),
            page=int(item["page_num"] or -1),
        )
        for item in sorted(results, key=lambda x: x["distance"])
    ]
    return out
