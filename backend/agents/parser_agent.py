from __future__ import annotations

from pathlib import Path

from docx import Document as DocxDocument
from PIL import Image

from utils.chunker import chunk_pdf_pages, chunk_text
from utils.excel_parser import parse_excel
from utils.pdf_parser import parse_pdf


class ParserAgent:
    async def run(self, file_path: str, file_type: str) -> dict:
        if file_type == "text":
            text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
            chunks = chunk_text(text)
            return {
                "full_text": text,
                "chunks": chunks,
                "metadata": {"total_pages": None, "total_chunks": len(chunks)},
                "tabular": None,
                "view_manifest": {"mode": "text", "source_mode": "native"},
            }
        if file_type == "docx":
            doc = DocxDocument(file_path)
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
            text = "\n".join(paragraphs)
            chunks = chunk_text(text)
            return {
                "full_text": text,
                "chunks": chunks,
                "metadata": {"total_pages": None, "total_chunks": len(chunks)},
                "tabular": None,
                "view_manifest": {"mode": "html", "source_mode": "native"},
            }
        if file_type == "image":
            with Image.open(file_path) as img:
                width, height = img.size
            filename = Path(file_path).name
            text = (
                f"Image file: {filename}\n"
                f"Resolution: {width}x{height}\n"
                "Describe the contents, important objects, scene context, and any embedded text."
            )
            chunks = chunk_text(text)
            return {
                "full_text": text,
                "chunks": chunks,
                "metadata": {"total_pages": 1, "total_chunks": len(chunks)},
                "tabular": None,
                "view_manifest": {"mode": "image", "source_mode": "native"},
            }
        if file_type == "pdf":
            parsed = parse_pdf(file_path)
            chunks = chunk_pdf_pages(parsed["pages"])
            return {
                "full_text": parsed["full_text"],
                "chunks": chunks,
                "metadata": {"total_pages": parsed["total_pages"], "total_chunks": len(chunks)},
                "tabular": None,
                "view_manifest": {"mode": "pdf", "source_mode": "pdf"},
            }
        parsed = parse_excel(file_path)
        full_text = parsed.get("full_text", "")
        if not full_text and parsed.get("tabular"):
            t = parsed["tabular"]
            full_text = (
                f"Dataset with {t.get('row_count', 0)} rows and {t.get('column_count', 0)} columns. "
                f"Columns: {', '.join((t.get('columns') or [])[:30])}."
            )
        # Larger chunk size for tabular context to reduce embedding overhead.
        chunks = chunk_text(full_text, chunk_size=1200, overlap=120)
        return {
            "full_text": full_text,
            "chunks": chunks,
            "metadata": {"total_pages": None, "total_chunks": len(chunks)},
            "tabular": parsed.get("tabular"),
            "view_manifest": {"mode": "table", "source_mode": "native"},
        }
