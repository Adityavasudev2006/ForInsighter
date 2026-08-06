from __future__ import annotations

import asyncio
from collections import OrderedDict

from models.schemas import ExtractedQuestion
from utils.chunker import chunk_text


class QuestionExtractorAgent:
    def __init__(self, llm_service):
        self.llm_service = llm_service

    @staticmethod
    def _normalize_questions_payload(result: object) -> list[dict]:
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        if isinstance(result, dict):
            items = result.get("questions", [])
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return []

    @staticmethod
    def _clean_question_text(text: str) -> str:
        t = (text or "").strip()
        # Remove common list/numbering prefixes.
        for prefix in ("- ", "• ", "* ", "1) ", "1. ", "Q: ", "Q. ", "Question: "):
            if t.lower().startswith(prefix.lower()):
                t = t[len(prefix) :].strip()
        # Collapse whitespace.
        return " ".join(t.split())

    @staticmethod
    def _looks_like_question(text: str, category: str) -> bool:
        t = (text or "").strip()
        if not t:
            return False
        if len(t) > 280:
            return False
        lower = t.lower()
        # True questions typically have '?', or start with interrogatives.
        interrogatives = (
            "what ",
            "why ",
            "how ",
            "when ",
            "where ",
            "who ",
            "which ",
            "is ",
            "are ",
            "do ",
            "does ",
            "did ",
            "can ",
            "could ",
            "would ",
            "should ",
            "please ",
        )
        if "?" in t:
            return True
        # Form fields may not use a question mark.
        if category == "form_field":
            # Avoid obviously non-question prose lines.
            return len(t.split()) <= 18 and not any(sep in t for sep in ("|", "{", "}", "[", "]"))
        return lower.startswith(interrogatives)

    async def run(self, full_text: str, mode: str = None, llm_options: dict | None = None) -> list[ExtractedQuestion]:
        schema = {
            "questions": [
                {"text": "string", "category": "factual|form_field|survey|open_ended", "source_page": 1}
            ]
        }
        chunks = chunk_text(full_text or "", chunk_size=5500, overlap=300)
        if not chunks:
            return []
        collected: OrderedDict[str, ExtractedQuestion] = OrderedDict()
        resolved_mode = mode or (llm_options or {}).get("mode") or "local"
        concurrency = int((llm_options or {}).get("concurrency") or (2 if resolved_mode == "local" else 6))
        sem = asyncio.Semaphore(max(1, concurrency))

        async def one(chunk_obj: dict) -> list[dict]:
            prompt = (
                "Extract all explicit questions from this chunk. For each, return: text, "
                "category (factual/form_field/survey/open_ended), source_page if detectable.\n\n"
                f"{chunk_obj['text']}"
            )
            async with sem:
                try:
                    result = await self.llm_service.complete_structured(
                        [{"role": "user", "content": prompt}],
                        schema=schema,
                        mode=mode,
                        llm_options=llm_options,
                    )
                    return self._normalize_questions_payload(result)
                except Exception:
                    return []

        tasks = [one(c) for c in chunks[:40]]
        for items in await asyncio.gather(*tasks):
            for item in items:
                try:
                    item["text"] = self._clean_question_text(str(item.get("text", "")))
                    q = ExtractedQuestion.model_validate(item)
                except Exception:
                    continue
                if not self._looks_like_question(q.text, q.category):
                    continue
                norm = " ".join(q.text.lower().split())
                if norm and norm not in collected:
                    collected[norm] = q
        return list(collected.values())
