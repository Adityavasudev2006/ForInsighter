from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import fitz  # PyMuPDF
from weasyprint import HTML
import hashlib
import json
from docx import Document as DocxDocument


def get_derivative_pdf_path(doc_id: str) -> Path:
    base = Path(os.getenv("DERIVATIVE_DIR", "./uploads/derivatives"))
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{doc_id}.pdf"


def generate_pdf_derivative(doc_id: str, file_path: str, file_type: str) -> Path:
    """
    Create a PDF suitable for read-only viewing in the UI.
    - For PDFs: we don't generate; caller should serve original.
    - For Excel: we render sheets to HTML tables and convert to PDF.
    """
    out_path = get_derivative_pdf_path(doc_id)
    if file_type == "pdf":
        return out_path

    parts: list[str] = [
        "<html><head><meta charset='utf-8' />"
        "<style>"
        "body{font-family:Arial, sans-serif;font-size:10pt;color:#111;}"
        "h1{font-size:14pt;margin:0 0 8px 0;}"
        "h2{font-size:12pt;margin:18px 0 6px 0;}"
        "table{border-collapse:collapse;width:100%;table-layout:fixed;}"
        "th,td{border:1px solid #ddd;padding:4px;vertical-align:top;word-wrap:break-word;}"
        "th{background:#f3f4f6;}"
        ".note{color:#555;font-size:9pt;margin-top:6px;}"
        "</style></head><body>"
        f"<h1>Document view (generated)</h1>"
    ]

    if file_type in {"excel", "csv"}:
        if file_type == "csv":
            frames = [("Sheet1", pd.read_csv(file_path))]
        else:
            xls = pd.ExcelFile(file_path)
            frames = []
            for sheet_name in xls.sheet_names:
                try:
                    frames.append((sheet_name, xls.parse(sheet_name=sheet_name)))
                except Exception:
                    continue
        for sheet_name, df in frames:
            parts.append(f"<h2>Sheet: {sheet_name}</h2>")
            max_rows = 500
            if len(df) > max_rows:
                parts.append(f"<div class='note'>Showing first {max_rows} rows of {len(df)}.</div>")
            preview = df.head(max_rows)
            parts.append(preview.to_html(index=False, escape=True))
    elif file_type in {"text", "docx"}:
        if file_type == "docx":
            doc = DocxDocument(file_path)
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        else:
            text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        paras = [p.strip() for p in text.splitlines() if p.strip()]
        for p in paras[:3000]:
            parts.append(f"<p>{p}</p>")
    else:
        raise ValueError(f"Unsupported file_type for derivative: {file_type}")

    parts.append("</body></html>")
    html = "\n".join(parts)
    HTML(string=html).write_pdf(str(out_path))
    return out_path


def merge_pdfs(output_path: str, pdf_paths: list[str]) -> str:
    if not pdf_paths:
        raise ValueError("No PDFs to merge")
    merged = fitz.open()
    try:
        for p in pdf_paths:
            src = fitz.open(p)
            try:
                merged.insert_pdf(src)
            finally:
                src.close()
        merged.save(output_path)
    finally:
        merged.close()
    return output_path


def _highlights_dir(doc_id: str) -> Path:
    base = Path(os.getenv("DERIVATIVE_DIR", "./uploads/derivatives")) / "highlights" / doc_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def generate_highlighted_pdf(base_pdf_path: str, doc_id: str, sources: list[dict]) -> Path:
    """
    Generate a highlighted PDF from a base PDF using (page_num, snippet) search.
    Caches output by hashing sources content.
    """
    payload = json.dumps(sources, sort_keys=True, ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16]
    out_path = _highlights_dir(doc_id) / f"{digest}.pdf"
    if out_path.exists():
        return out_path

    src = Path(base_pdf_path)
    if not src.exists():
        raise FileNotFoundError("Base PDF not found")

    doc = fitz.open(str(src))
    try:
        for s in sources or []:
            snippet = (s.get("snippet") or "").strip()
            if not snippet:
                continue
            page_num = s.get("page_num")
            page_indexes: list[int]
            if isinstance(page_num, int) and page_num > 0:
                page_indexes = [page_num - 1]
            else:
                page_indexes = list(range(doc.page_count))
            for pi in page_indexes[:10]:
                if pi < 0 or pi >= doc.page_count:
                    continue
                page = doc.load_page(pi)
                # Search for the snippet; if too long, search shorter prefix.
                query = snippet if len(snippet) <= 120 else snippet[:120]
                rects = page.search_for(query, quads=False)
                if not rects and len(query) > 40:
                    rects = page.search_for(query[:60], quads=False)
                for rect in rects[:8]:
                    annot = page.add_highlight_annot(rect)
                    annot.set_colors(stroke=(1.0, 1.0, 0.0))
                    annot.update()
                if rects:
                    break
    finally:
        doc.save(str(out_path))
        doc.close()
    return out_path

