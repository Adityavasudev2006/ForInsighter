from __future__ import annotations

import asyncio
import json
import re
import time

from agents.classifier_agent import ClassifierAgent
from agents.parser_agent import ParserAgent
from agents.qa_agent import QAAgent
from agents.question_extractor_agent import QuestionExtractorAgent
from agents.summarizer_agent import SummarizerAgent
from models.schemas import CompareResult, DocumentSummary, EntityData
from services.cache_service import CacheService
from services.chroma_service import ChromaService
from services.embedding_service import EmbeddingService
from services.llm_service import LLMService
from utils.chunker import chunk_text


class Orchestrator:
    @staticmethod
    def _llm_concurrency(mode: str | None, llm_options: dict | None) -> int:
        resolved = mode or (llm_options or {}).get("mode") or "local"
        # Local Ollama: keep low to avoid lagging the machine.
        if resolved == "local":
            return int((llm_options or {}).get("concurrency") or 2)
        # API mode: moderate concurrency; LLMService already retries 429/5xx for Gemini.
        return int((llm_options or {}).get("concurrency") or 6)

    @staticmethod
    def _gather_limit() -> int:
        # Hard cap to avoid runaway tasks on huge documents.
        return 20
    @staticmethod
    def _fallback_summary(full_text: str, tabular: dict | None = None) -> DocumentSummary:
        if isinstance(tabular, dict):
            rows = int(tabular.get("row_count", 0))
            cols = int(tabular.get("column_count", 0))
            sheets = int(tabular.get("sheet_count", 1))
            columns = [str(c) for c in (tabular.get("columns") or [])[:12]]
            return DocumentSummary(
                title="Dataset Overview",
                key_points=[
                    f"The dataset contains {rows} rows and {cols} columns across {sheets} sheet(s).",
                    f"Primary columns include: {', '.join(columns)}." if columns else "Column metadata is available in the details tab.",
                    f"Total missing values: {int(tabular.get('missing_values_total', 0))}; duplicate rows: {int(tabular.get('duplicate_rows', 0))}.",
                ],
                important_entities=columns[:8],
                conclusion=(
                    "This dataset appears suitable for exploratory analysis, trend profiling, and column-level quality checks."
                ),
                document_type="tabular_dataset",
            )
        text = " ".join((full_text or "").split())
        snippet = text[:3000]
        sentences = re.split(r"(?<=[.!?])\s+", snippet)
        key_points = [sentence.strip() for sentence in sentences if sentence.strip()][:5]
        title = key_points[0][:120] if key_points else "Document Summary"
        emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", snippet)
        entities = sorted(set(emails))[:8]
        conclusion = key_points[-1] if key_points else "Summary generated with fallback strategy."
        return DocumentSummary(
            title=title or "Document Summary",
            key_points=key_points or ["Unable to extract semantic points; fallback summary used."],
            important_entities=entities,
            conclusion=conclusion,
            document_type="other",
        )

    @staticmethod
    def _fallback_entities(full_text: str) -> EntityData:
        text = full_text or ""
        emails = sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)))[:50]
        dates = sorted(set(re.findall(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b", text)))[:50]
        numbers = sorted(set(re.findall(r"\b\d+(?:\.\d+)?\b", text)))[:50]
        names = sorted(set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text)))[:50]
        return EntityData(names=names, dates=dates, numbers=numbers, emails=emails)

    def __init__(self):
        self.llm_service = LLMService()
        self.embedding_service = EmbeddingService()
        self.chroma_service = ChromaService()
        self.cache_service = CacheService()
        self.parser_agent = ParserAgent()
        self.classifier_agent = ClassifierAgent(self.llm_service)
        self.summarizer_agent = SummarizerAgent(self.llm_service, self.cache_service)
        self.question_extractor_agent = QuestionExtractorAgent(self.llm_service)
        self.qa_agent = QAAgent(self.llm_service, self.chroma_service, self.embedding_service, cache_service=self.cache_service)

    @staticmethod
    def _normalize_entities_payload(entities: object) -> dict:
        if isinstance(entities, dict):
            return entities
        if isinstance(entities, list):
            merged = {"names": [], "dates": [], "numbers": [], "emails": []}
            for item in entities:
                if not isinstance(item, dict):
                    continue
                for field in merged:
                    values = item.get(field, [])
                    if isinstance(values, list):
                        for value in values:
                            if isinstance(value, str) and value.strip() and value not in merged[field]:
                                merged[field].append(value.strip())
            return merged
        return {}

    async def _extract_entities(self, full_text: str, mode: str = None, llm_options: dict | None = None) -> EntityData:
        schema = {"names": ["string"], "dates": ["string"], "numbers": ["string"], "emails": ["string"]}
        chunks = chunk_text(full_text or "", chunk_size=5500, overlap=300)
        if not chunks:
            return EntityData()
        merged = {"names": [], "dates": [], "numbers": [], "emails": []}
        concurrency = self._llm_concurrency(mode, llm_options)
        sem = asyncio.Semaphore(max(1, concurrency))

        async def one(chunk_obj: dict) -> dict | None:
            payload = [
                {"role": "system", "content": "Extract entities from this chunk."},
                {"role": "user", "content": chunk_obj["text"]},
            ]
            async with sem:
                try:
                    return await self.llm_service.complete_structured(payload, schema=schema, mode=mode, llm_options=llm_options)
                except Exception:
                    return None

        tasks = [one(c) for c in chunks[: min(40, self._gather_limit() * concurrency)]]
        for result in await asyncio.gather(*tasks):
            if not result:
                continue
            entity_map = self._normalize_entities_payload(result)
            for field in merged:
                values = entity_map.get(field, [])
                if not isinstance(values, list):
                    continue
                for val in values[:50]:
                    if isinstance(val, str) and val.strip() and val not in merged[field]:
                        merged[field].append(val.strip())
        return EntityData.model_validate(merged)

    async def process_document(self, doc_id: str, file_path: str, file_type: str, mode: str = None, llm_options: dict | None = None) -> dict:
        parsed = await self.parser_agent.run(file_path, file_type)
        if not parsed["full_text"].strip():
            raise ValueError("Document parsing produced no text content")
        chunk_texts = [chunk["text"] for chunk in parsed["chunks"]]
        embeddings = self.embedding_service.embed(chunk_texts) if chunk_texts else []
        if embeddings and parsed["chunks"]:
            self.chroma_service.add_chunks(doc_id, parsed["chunks"], embeddings)
        async def safe_doc_type():
            try:
                return await self.classifier_agent.run(parsed["full_text"], mode=mode, llm_options=llm_options)
            except Exception:
                return "other"

        async def safe_summary():
            try:
                return await self.summarizer_agent.run(
                    parsed["full_text"],
                    content_hash=doc_id,
                    mode=mode,
                    llm_options=llm_options,
                    tabular=parsed.get("tabular"),
                )
            except Exception:
                return self._fallback_summary(parsed["full_text"], tabular=parsed.get("tabular"))

        async def safe_questions():
            try:
                return await self.question_extractor_agent.run(parsed["full_text"], mode=mode, llm_options=llm_options)
            except Exception:
                return []

        async def safe_entities():
            try:
                return await self._extract_entities(parsed["full_text"], mode=mode, llm_options=llm_options)
            except Exception:
                return self._fallback_entities(parsed["full_text"])

        doc_type, summary, questions, entities = await asyncio.gather(
            safe_doc_type(),
            safe_summary(),
            safe_questions(),
            safe_entities(),
        )
        return {
            "doc_type": doc_type,
            "summary": summary.model_dump(),
            "questions": [q.model_dump() for q in questions],
            "entities": entities.model_dump(),
            "metadata": parsed["metadata"],
            "profile": parsed.get("tabular"),
            "view_manifest": parsed.get("view_manifest"),
        }

    async def process_document_compare(self, doc_id: str, file_path: str, file_type: str) -> CompareResult:
        async def timed(mode: str):
            start = time.perf_counter()
            res = await self.process_document(doc_id, file_path, file_type, mode=mode)
            latency_ms = (time.perf_counter() - start) * 1000
            return res, latency_ms

        (local_res, local_ms), (api_res, api_ms) = await asyncio.gather(timed("local"), timed("api"))
        return CompareResult(
            local_output=DocumentSummary.model_validate(local_res["summary"]),
            api_output=DocumentSummary.model_validate(api_res["summary"]),
            local_latency_ms=local_ms,
            api_latency_ms=api_ms,
        )
