from __future__ import annotations

import io
import json

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from weasyprint import HTML

from models.database import Document, SessionLocal


router = APIRouter(prefix="/export", tags=["export"])


@router.get("/{doc_id}")
async def export_document(doc_id: str, format: str = Query(default="json")):
    async with SessionLocal() as session:
        doc = await session.get(Document, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
    payload = {
        "id": doc.id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "doc_type": doc.doc_type,
        "status": doc.status,
        "created_at": doc.created_at.isoformat(),
        "summary": json.loads(doc.summary_json) if doc.summary_json else {},
        "questions": json.loads(doc.questions_json) if doc.questions_json else [],
        "entities": json.loads(doc.entities_json) if doc.entities_json else {},
    }
    if format == "json":
        return Response(
            content=json.dumps(payload, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{doc.id}.json"'},
        )
    if format == "csv":
        rows = []
        entities = payload.get("entities", {})
        for key, values in entities.items():
            rows.append({"type": key, "value": ", ".join(values)})
        for question in payload.get("questions", []):
            rows.append({"type": "question", "value": question.get("text", "")})
        df = pd.DataFrame(rows)
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{doc.id}.csv"'},
        )
    if format == "pdf":
        summary = payload.get("summary", {})
        html = f"""
        <h1>{summary.get("title", doc.filename)}</h1>
        <h3>Key Points</h3>
        <ul>{"".join([f"<li>{item}</li>" for item in summary.get("key_points", [])])}</ul>
        <h3>Important Entities</h3>
        <ul>{"".join([f"<li>{item}</li>" for item in summary.get("important_entities", [])])}</ul>
        <p>{summary.get("conclusion", "")}</p>
        """
        pdf_bytes = HTML(string=html).write_pdf()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{doc.id}.pdf"'},
        )
    raise HTTPException(status_code=400, detail="Unsupported export format")
