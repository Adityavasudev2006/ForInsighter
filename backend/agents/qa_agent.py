from __future__ import annotations

import hashlib
import json

from models.schemas import ChatMessage


class QAAgent:
    def __init__(self, llm_service, chroma_service, embedding_service, cache_service=None):
        self.llm_service = llm_service
        self.chroma_service = chroma_service
        self.embedding_service = embedding_service
        self.cache_service = cache_service

    async def run(self, doc_id: str, question: str, history: list[ChatMessage], mode: str = None, llm_options: dict | None = None) -> dict:
        normalized_q = " ".join((question or "").strip().lower().split())
        model_key_parts = [
            (llm_options or {}).get("mode") or mode or "",
            (llm_options or {}).get("api_provider") or "",
            (llm_options or {}).get("ollama_model") or "",
        ]
        model_key = ":".join([p for p in model_key_parts if p]) or (mode or "local")

        embedding = self.embedding_service.embed_one(question)
        hits = self.chroma_service.query(doc_id, embedding, n_results=5)
        hits = sorted(
            hits,
            key=lambda h: (
                h.get("chunk_index") if h.get("chunk_index") is not None else 10**9,
                h.get("page_num") if h.get("page_num") is not None else 10**9,
            ),
        )
        retrieval_fingerprint = "|".join([f"{h.get('chunk_index')}:{h.get('page_num')}" for h in hits])
        retrieval_hash = hashlib.sha256(retrieval_fingerprint.encode("utf-8")).hexdigest()[:16]
        q_hash = hashlib.sha256(normalized_q.encode("utf-8")).hexdigest()[:24]

        cache_key = f"qa:{doc_id}:{model_key}:{q_hash}:{retrieval_hash}"
        cache_index_key = f"qa_keys:{doc_id}"
        if self.cache_service is not None and normalized_q and hits:
            cached = await self.cache_service.get(cache_key)
            if cached:
                try:
                    payload = json.loads(cached)
                    if isinstance(payload, dict) and "answer" in payload and "sources" in payload:
                        payload["cache_hit"] = True
                        return payload
                except Exception:
                    pass

        context = "\n\n".join(
            [
                f"[chunk_index={hit['chunk_index']}, page_num={hit['page_num']}]\n{hit['text']}"
                for hit in hits
            ]
        )
        # Keep prompt deterministic for identical query to maximize cache stability.
        history_messages = history[-6:]
        history_text = "\n".join([f"{msg.role}: {msg.content}" for msg in history_messages])
        messages = [
            {
                "role": "system",
                "content": "Answer using only the provided context. Always cite the chunk_index and page_num.",
            },
            {
                "role": "user",
                "content": f"Chat history:\n{history_text}\n\nContext:\n{context}\n\nQuestion: {question}",
            },
        ]
        answer = await self.llm_service.complete(messages, mode=mode, llm_options=llm_options)
        sources = [
            {
                "chunk_index": hit["chunk_index"],
                "page_num": hit["page_num"] if hit["page_num"] is not None else -1,
                "snippet": hit["text"][:180],
            }
            for hit in hits
        ]
        result = {"answer": answer, "sources": sources, "cache_hit": False}

        if self.cache_service is not None and normalized_q and hits:
            try:
                await self.cache_service.set(cache_key, json.dumps({"answer": answer, "sources": sources}), ttl_seconds=86400 * 100)
                await self.cache_service.sadd(cache_index_key, cache_key)
            except Exception:
                pass
        return result
