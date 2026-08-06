from __future__ import annotations


class ClassifierAgent:
    def __init__(self, llm_service):
        self.llm_service = llm_service

    async def run(self, text_sample: str, mode: str = None, llm_options: dict | None = None) -> str:
        prompt = (
            "Classify this document as one of: invoice, form, report, research_paper, other. "
            "Return only the label.\n\n"
            f"Document sample:\n{text_sample[:1000]}"
        )
        out = await self.llm_service.complete(
            [{"role": "system", "content": "You are a strict classifier."}, {"role": "user", "content": prompt}],
            mode=mode,
            llm_options=llm_options,
        )
        value = out.strip().lower()
        return value if value in {"invoice", "form", "report", "research_paper", "other"} else "other"
