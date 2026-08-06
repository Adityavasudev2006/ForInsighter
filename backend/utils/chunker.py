from __future__ import annotations


SEPARATORS = ["\n\n", "\n", ". ", " "]


def _split_with_separators(text: str, chunk_size: int) -> list[str]:
    pieces = [text.strip()]
    for separator in SEPARATORS:
        next_pieces: list[str] = []
        for piece in pieces:
            if len(piece) <= chunk_size:
                next_pieces.append(piece)
                continue
            split_piece = piece.split(separator)
            for idx, part in enumerate(split_piece):
                part = part.strip()
                if not part:
                    continue
                suffix = ". " if separator == ". " and idx < len(split_piece) - 1 else ""
                next_pieces.append(f"{part}{suffix}".strip())
        pieces = next_pieces
    return [piece for piece in pieces if piece]


def _compose_chunks(parts: list[str], chunk_size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current} {part}".strip()
        if not current:
            current = part
            continue
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        chunks.append(current.strip())
        current = current[-overlap:].strip() + " " + part if overlap > 0 else part
        current = current.strip()
        if len(current) > chunk_size:
            chunks.append(current[:chunk_size].strip())
            current = current[chunk_size - overlap :].strip() if overlap < chunk_size else current[chunk_size:].strip()
    if current:
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk]


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[dict]:
    if not text.strip():
        return []
    parts = _split_with_separators(text, chunk_size)
    chunks = _compose_chunks(parts, chunk_size, overlap)
    return [{"text": chunk, "chunk_index": idx} for idx, chunk in enumerate(chunks)]


def chunk_pdf_pages(pages: list[dict], chunk_size: int = 512, overlap: int = 64) -> list[dict]:
    all_chunks: list[dict] = []
    index = 0
    for page in pages:
        page_num = int(page.get("page_num", 0))
        text = str(page.get("text", "")).strip()
        for chunk in chunk_text(text, chunk_size=chunk_size, overlap=overlap):
            all_chunks.append(
                {
                    "text": chunk["text"],
                    "chunk_index": index,
                    "page_num": page_num,
                }
            )
            index += 1
    return all_chunks
