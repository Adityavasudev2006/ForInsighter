from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from agents.orchestrator import Orchestrator
from models.database import ChatHistory, Document, SessionLocal
from models.schemas import ChatRequest


router = APIRouter(prefix="/chat", tags=["chat"])
orchestrator = Orchestrator()


def _read_tabular(file_path: str, file_type: str) -> pd.DataFrame | None:
    try:
        if file_type == "csv":
            return pd.read_csv(file_path, low_memory=False, engine="c")
        if file_type == "excel":
            suffix = Path(file_path).suffix.lower()
            if suffix == ".xls":
                return pd.read_excel(file_path, engine="xlrd")
            return pd.read_excel(file_path)
    except Exception:
        return None
    return None


def _quick_tabular_answer(message: str, file_path: str, file_type: str) -> dict | None:
    msg = (message or "").strip()
    if not msg:
        return None
    df = _read_tabular(file_path, file_type)
    if df is None or df.empty:
        return None
    lowered = msg.lower()

    # Pattern: How many times "woman" is mentioned in the gender column?
    m = re.search(r'how many times\s+"([^"]+)"\s+.*\s+in\s+the\s+([a-zA-Z0-9_ ]+)\s+column', lowered)
    if m:
        needle = m.group(1).strip()
        col_name_hint = m.group(2).strip()
        columns = {str(c).lower(): str(c) for c in df.columns}
        col = columns.get(col_name_hint) or next((orig for low, orig in columns.items() if col_name_hint in low), None)
        if col:
            series = df[col].fillna("").astype(str)
            count = int(series.str.contains(re.escape(needle), case=False, regex=True).sum())
            return {
                "answer": f'"{needle}" appears {count} times in the "{col}" column.',
                "sources": [{"chunk_index": 0, "page_num": -1, "snippet": f'{col} contains "{needle}" {count} times'}],
            }

    # Fast row/column summary question
    if "how many rows" in lowered:
        return {
            "answer": f"This dataset has {len(df)} rows.",
            "sources": [{"chunk_index": 0, "page_num": -1, "snippet": f"row_count={len(df)}"}],
        }
    if "how many columns" in lowered:
        return {
            "answer": f"This dataset has {len(df.columns)} columns.",
            "sources": [{"chunk_index": 0, "page_num": -1, "snippet": f"column_count={len(df.columns)}"}],
        }
    return None


@router.post("/{doc_id}")
async def chat_document(
    doc_id: str,
    payload: ChatRequest,
    mode: str = Query(default="local"),
    api_provider: str | None = Query(default=None),
    api_key: str | None = Query(default=None),
    ollama_base_url: str | None = Query(default=None),
    ollama_model: str | None = Query(default=None),
):
    async with SessionLocal() as session:
        doc = await session.get(Document, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        quick = None
        if doc.file_type in {"excel", "csv"}:
            quick = _quick_tabular_answer(payload.message, doc.file_path, doc.file_type)
        if quick is not None:
            user_row = ChatHistory(doc_id=doc_id, role="user", content=payload.message)
            assistant_row = ChatHistory(doc_id=doc_id, role="assistant", content=quick["answer"], sources_json=json.dumps(quick["sources"]))
            session.add_all([user_row, assistant_row])
            await session.commit()
            return quick
        llm_options = {
            "mode": mode,
            "api_provider": api_provider,
            "api_key": api_key,
            "ollama_base_url": ollama_base_url,
            "ollama_model": ollama_model,
        }
        try:
            result = await orchestrator.qa_agent.run(doc_id, payload.message, payload.history, mode=mode, llm_options=llm_options)
        except Exception as exc:
            err_msg = str(exc).strip().replace("\n", " ")
            # API providers can fail transiently (quota/rate/network). Fall back to local mode
            # so Document Chat still returns a usable answer when Ollama is available.
            if mode == "api":
                try:
                    local_options = {
                        "mode": "local",
                        "ollama_base_url": ollama_base_url,
                        "ollama_model": ollama_model,
                    }
                    result = await orchestrator.qa_agent.run(
                        doc_id,
                        payload.message,
                        payload.history,
                        mode="local",
                        llm_options=local_options,
                    )
                    fallback_note = (
                        "Note: API mode failed and this answer was generated in local mode. "
                        f"Reason: {err_msg[:220]}"
                    )
                    result["answer"] = f"{fallback_note}\n\n{result.get('answer', '')}".strip()
                except Exception as fallback_exc:
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Chat request failed in API mode and local fallback also failed. "
                            f"API error: {err_msg[:220]}. Local error: {str(fallback_exc)[:220]}"
                        ),
                    ) from fallback_exc
            else:
                raise HTTPException(status_code=502, detail=f"Chat request failed: {err_msg[:300]}") from exc
        user_row = ChatHistory(doc_id=doc_id, role="user", content=payload.message)
        assistant_row = ChatHistory(
            doc_id=doc_id,
            role="assistant",
            content=result["answer"],
            sources_json=json.dumps(result["sources"]),
        )
        session.add_all([user_row, assistant_row])
        await session.commit()
        return result


@router.get("/{doc_id}/history")
async def chat_history(doc_id: str):
    async with SessionLocal() as session:
        doc = await session.get(Document, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        result = await session.execute(select(ChatHistory).where(ChatHistory.doc_id == doc_id).order_by(ChatHistory.created_at))
        rows = result.scalars().all()
    return [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "sources": json.loads(row.sources_json) if row.sources_json else None,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.delete("/{doc_id}/history")
async def clear_chat_history(doc_id: str):
    async with SessionLocal() as session:
        result = await session.execute(select(ChatHistory).where(ChatHistory.doc_id == doc_id))
        rows = result.scalars().all()
        for row in rows:
            await session.delete(row)
        await session.commit()
    return {"status": "cleared"}
