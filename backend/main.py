from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models.database import create_all
from routers import analysis_router, batch_router, chat_router, documents_router, export_router, llm_router, search_router


load_dotenv()
app = FastAPI(title="AI Document Intelligence Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(export_router, prefix="/api")
app.include_router(batch_router, prefix="/api")
app.include_router(llm_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    await create_all()
    Path(os.getenv("UPLOAD_DIR", "./uploads")).mkdir(parents=True, exist_ok=True)


@app.get("/api/health")
async def health():
    return {"status": "ok", "llm_mode": os.getenv("LLM_MODE", "local")}
