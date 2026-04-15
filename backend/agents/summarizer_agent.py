from __future__ import annotations

import asyncio
import json

from models.schemas import DocumentSummary
from utils.chunker import chunk_text


class SummarizerAgent:
    @staticmethod
    def _normalize_summary_payload(result: object) -> dict:
        if isinstance(result, dict):
            payload = result
            title = str(payload.get("title") or "").strip()
            # Avoid noisy raw-row titles for tabular files.
            if title.lower().startswith(("sheet:", "row_", "{", "[")) or "|" in title:
                payload["title"] = "Dataset Overview"
            return payload
        if isinstance(result, list) and result and isinstance(result[0], dict):
            return result[0]
        return {
            "title": "Document Summary",
            "key_points": [],
            "important_entities": [],
            "conclusion": "",
            "document_type": "other",
        }

    def __init__(self, llm_service, cache_service):
        self.llm_service = llm_service
        self.cache_service = cache_service

    async def _summarize_chunk(self, chunk_text_value: str, mode: str | None, llm_options: dict | None) -> dict:
        schema = {
            "title": "string",
            "key_points": ["string"],
            "important_entities": ["string"],
            "conclusion": "string",
            "document_type": "string",
            "narrative_summary": "string",
        }
        payload = [
            {"role": "system", "content": "Analyze this document chunk and return a structured summary for this chunk only."},
            {"role": "user", "content": chunk_text_value[:7000]},
        ]
        return await self.llm_service.complete_structured(payload, schema=schema, mode=mode, llm_options=llm_options)

    async def run(
        self,
        full_text: str,
        content_hash: str,
        mode: str = None,
        llm_options: dict | None = None,
        tabular: dict | None = None,
    ) -> DocumentSummary:
        mode_key = mode or (llm_options or {}).get("mode") or self.llm_service.llm_mode
        key = f"summary:{content_hash}:{mode_key}"
        cached = await self.cache_service.get(key)
        if cached:
            return DocumentSummary.model_validate(json.loads(cached))
        schema = {
            "title": "string",
            "key_points": ["string"],
            "important_entities": ["string"],
            "conclusion": "string",
            "document_type": "string",
            "narrative_summary": "string",
            "columns": ["string"],
            "column_types": "object",
            "column_descriptions": "object",
        }
        text = (full_text or "").strip()
        if len(text) <= 6500:
            payload = [
                {
                    "role": "system",
                    "content": (
                        "Analyze this document and return a structured summary. "
                        "Also include a short plain-English narrative summary (3-4 paragraphs). "
                        "If this is tabular data, mention what the dataset is about, row/column counts, and notable data quality patterns. "
                        "Preserve column names and infer types and meanings. "
                        "Write a clean English title (not raw row text)."
                    ),
                },
                {"role": "user", "content": json.dumps({"text": text, "tabular": tabular})},
            ]
            result = await self.llm_service.complete_structured(payload, schema=schema, mode=mode, llm_options=llm_options)
        else:
            chunks = chunk_text(text, chunk_size=5500, overlap=300)
            chunk_summaries: list[dict] = []
            concurrency = 2 if (mode_key or "local") == "local" else 6
            concurrency = int((llm_options or {}).get("concurrency") or concurrency)
            sem = asyncio.Semaphore(max(1, concurrency))

            async def one(chunk_obj: dict) -> dict | None:
                async with sem:
                    try:
                        return await self._summarize_chunk(chunk_obj["text"], mode=mode, llm_options=llm_options)
                    except Exception:
                        return None

            tasks = [one(c) for c in chunks[:40]]
            for partial in await asyncio.gather(*tasks):
                if partial:
                    chunk_summaries.append(partial)
            if not chunk_summaries:
                raise ValueError("Unable to summarize document chunks")
            merge_payload = [
                {
                    "role": "system",
                    "content": (
                        "You are combining multiple partial summaries of one document. "
                        "Return one final structured summary, including a short plain-English narrative summary (3-4 paragraphs)."
                    ),
                },
                {"role": "user", "content": json.dumps({"partials": chunk_summaries, "tabular": tabular})},
            ]
            result = await self.llm_service.complete_structured(
                merge_payload,
                schema=schema,
                mode=mode,
                llm_options=llm_options,
            )
        summary = DocumentSummary.model_validate(self._normalize_summary_payload(result))
        await self.cache_service.set(key, summary.model_dump_json())
        return summary
