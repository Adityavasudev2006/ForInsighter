from __future__ import annotations

import re

import fitz


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_pdf(file_path: str) -> dict:
    result = {"pages": [], "full_text": "", "total_pages": 0}
    try:
        with fitz.open(file_path) as doc:
            if doc.needs_pass:
                return result
            full_text_parts: list[str] = []
            for idx, page in enumerate(doc, start=1):
                text = _clean_text(page.get_text("text"))
                # Best-effort OCR fallback when text layer is empty (scanned/image PDFs).
                if not text:
                    try:
                        # PyMuPDF provides OCR via get_textpage_ocr when available.
                        tp = page.get_textpage_ocr(full=True)  # type: ignore[attr-defined]
                        text = _clean_text(tp.extractText() if tp else "")
                    except Exception:
                        text = ""
                result["pages"].append({"page_num": idx, "text": text})
                if text:
                    full_text_parts.append(text)
            result["total_pages"] = len(doc)
            result["full_text"] = "\n".join(full_text_parts).strip()
    except Exception:
        return result
    return result
