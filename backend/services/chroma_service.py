from __future__ import annotations

import os

import chromadb


class ChromaService:
    def __init__(self):
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        self.client = chromadb.PersistentClient(path=persist_dir)

    def _get_collection(self, doc_id: str):
        return self.client.get_or_create_collection(name=doc_id)

    def add_chunks(self, doc_id: str, chunks: list[dict], embeddings: list[list[float]]):
        collection = self._get_collection(doc_id)
        ids = [f"{doc_id}_{chunk['chunk_index']}" for chunk in chunks]
        docs = [chunk["text"] for chunk in chunks]
        metas = [
            {
                "chunk_index": int(chunk["chunk_index"]),
                "page_num": int(chunk.get("page_num", -1)),
            }
            for chunk in chunks
        ]
        collection.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)

    def query(self, doc_id: str, query_embedding: list[float], n_results: int = 5) -> list[dict]:
        collection = self._get_collection(doc_id)
        result = collection.query(query_embeddings=[query_embedding], n_results=n_results)
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        items = []
        for doc, meta, distance in zip(docs, metas, distances):
            items.append(
                {
                    "text": doc,
                    "chunk_index": int(meta.get("chunk_index", -1)),
                    "page_num": None if int(meta.get("page_num", -1)) < 0 else int(meta.get("page_num", -1)),
                    "distance": float(distance),
                }
            )
        return items

    def query_all(self, query_embedding: list[float], n_results: int = 10) -> list[dict]:
        all_items: list[dict] = []
        for collection in self.client.list_collections():
            result = collection.query(query_embeddings=[query_embedding], n_results=n_results)
            docs = result.get("documents", [[]])[0]
            metas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]
            for doc, meta, distance in zip(docs, metas, distances):
                all_items.append(
                    {
                        "doc_id": collection.name,
                        "text": doc,
                        "chunk_index": int(meta.get("chunk_index", -1)),
                        "page_num": None if int(meta.get("page_num", -1)) < 0 else int(meta.get("page_num", -1)),
                        "distance": float(distance),
                    }
                )
        all_items.sort(key=lambda item: item["distance"])
        return all_items[:n_results]

    def delete_collection(self, doc_id: str):
        try:
            self.client.delete_collection(doc_id)
        except Exception:
            return
