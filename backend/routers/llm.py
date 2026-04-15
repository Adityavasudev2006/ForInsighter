from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from services.llm_service import LLMService


router = APIRouter(prefix="/llm", tags=["llm"])
llm_service = LLMService()


class ValidateLLMRequest(BaseModel):
    mode: str
    api_provider: str | None = None
    api_key: str | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    api_model: str | None = None


@router.post("/validate")
async def validate_llm(payload: ValidateLLMRequest):
    result = await llm_service.validate_config(
        mode=payload.mode,
        llm_options={
            "mode": payload.mode,
            "api_provider": payload.api_provider,
            "api_key": payload.api_key,
            "ollama_base_url": payload.ollama_base_url,
            "ollama_model": payload.ollama_model,
            "api_model": payload.api_model,
        },
    )
    return result
