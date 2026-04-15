from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    failed = "failed"


class DocumentType(str, Enum):
    invoice = "invoice"
    form = "form"
    report = "report"
    research_paper = "research_paper"
    other = "other"


class DocumentSummary(BaseModel):
    title: str
    key_points: list[str]
    important_entities: list[str]
    conclusion: str
    document_type: str
    # 2-3 paragraphs in plain English, for the UI Summary tab.
    narrative_summary: str | list[str] | None = None
    # For tabular documents (Excel/CSV): persisted schema enrichment.
    columns: list[str] | None = None
    column_types: dict[str, str] | None = None
    column_descriptions: dict[str, str] | None = None
    # Extended dataset summary profile
    row_count: int | None = None
    column_count: int | None = None
    file_size_bytes: int | None = None
    sheet_count: int | None = None
    missing_values_per_column: dict[str, int] | None = None
    missing_values_total: int | None = None
    unique_values_per_column: dict[str, int] | None = None
    numerical_stats: dict[str, dict[str, float | int | list[float] | None]] | None = None
    categorical_stats: dict[str, dict[str, str | int | float | None]] | None = None
    duplicate_rows: int | None = None
    inconsistent_formats: list[str] | None = None
    invalid_values: list[str] | None = None


class ViewManifest(BaseModel):
    mode: Literal["pdf", "html", "text", "table", "image"]
    view_url: str | None = None
    highlight_url: str | None = None
    source_mode: Literal["pdf", "native"] = "pdf"
    line_map: dict[str, str] | None = None


class ExtractedQuestion(BaseModel):
    text: str
    category: str
    source_page: int | None = None


class EntityData(BaseModel):
    names: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    numbers: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)


class SourceRef(BaseModel):
    # Backward/forward compatible with current frontend payloads
    # (frontend uses chunk_index/page_num; older schema used chunk_id/page).
    chunk_index: int | None = None
    page_num: int | None = None
    chunk_id: int | None = None
    page: int | None = None
    snippet: str
    line_ref: str | None = None
    cell_ref: str | None = None


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    doc_type: str | None = None
    status: DocumentStatus
    created_at: datetime
    summary: DocumentSummary | None = None
    questions: list[ExtractedQuestion] | None = None
    entities: EntityData | None = None
    processing_error: str | None = None
    view_manifest: ViewManifest | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    sources: list[SourceRef] | None = None


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


class CompareResult(BaseModel):
    local_output: DocumentSummary
    api_output: DocumentSummary
    local_latency_ms: float
    api_latency_ms: float


class SearchResult(BaseModel):
    doc_id: str
    filename: str
    snippet: str
    score: float
    page: int


class BatchRequest(BaseModel):
    doc_ids: list[str]


class BatchStatusResponse(BaseModel):
    task_id: str
    status: str
    total: int
    completed: int
    failed: int


class UploadLinkRequest(BaseModel):
    url: str
