from __future__ import annotations

import asyncio
import json
import os
import re
import time
import random
from copy import deepcopy

from dotenv import load_dotenv
import httpx
from litellm import acompletion


load_dotenv()


class LLMService:
    @staticmethod
    def _extract_json_candidate(text: str) -> str | None:
        cleaned = (text or "").strip()
        if not cleaned:
            return None
        fenced = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()
        start_obj = cleaned.find("{")
        start_arr = cleaned.find("[")
        starts = [idx for idx in [start_obj, start_arr] if idx != -1]
        if not starts:
            return None
        start = min(starts)
        sliced = cleaned[start:]
        for end in range(len(sliced), 0, -1):
            candidate = sliced[:end].strip()
            if not candidate:
                continue
            if candidate[0] not in "{[":
                continue
            if candidate[-1] not in "}]":
                continue
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue
        return None

    def __init__(self):
        self.llm_mode = os.getenv("LLM_MODE", "local")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.api_provider = os.getenv("API_PROVIDER", "gemini")
        self.api_model = os.getenv("API_MODEL", "gemini/gemini-1.5-flash")

    def _resolve(self, mode: str | None = None, llm_options: dict | None = None) -> dict:
        options = llm_options or {}
        return {
            "mode": mode or options.get("mode") or self.llm_mode,
            "ollama_base_url": options.get("ollama_base_url") or self.ollama_base_url,
            "ollama_model": options.get("ollama_model") or self.ollama_model,
            "api_provider": options.get("api_provider") or self.api_provider,
            "api_key": options.get("api_key") or (self.gemini_api_key if (options.get("api_provider") or self.api_provider) == "gemini" else self.openai_api_key),
            "api_model": options.get("api_model") or self.api_model,
        }

    @staticmethod
    def _normalize_gemini_model_name(model_name: str) -> str:
        return str(model_name or "").replace("gemini/", "").strip()

    async def _list_gemini_models(self, api_key: str) -> list[str]:
        endpoint = "https://generativelanguage.googleapis.com/v1beta/models"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(endpoint, params={"key": api_key})
            response.raise_for_status()
            body = response.json()
        models = body.get("models", [])
        supported: list[str] = []
        for model in models:
            name = str(model.get("name", ""))
            methods = model.get("supportedGenerationMethods", []) or []
            if "generateContent" not in methods:
                continue
            if name.startswith("models/"):
                name = name.split("/", 1)[1]
            if name:
                supported.append(name)
        return supported

    async def _pick_gemini_model(self, preferred_model: str, api_key: str) -> str:
        preferred = self._normalize_gemini_model_name(preferred_model)
        try:
            models = await self._list_gemini_models(api_key)
        except Exception:
            return preferred or "gemini-1.5-flash"
        if not models:
            return preferred or "gemini-1.5-flash"
        if preferred and preferred in models:
            return preferred
        flash_candidates = [m for m in models if "flash" in m.lower()]
        pro_candidates = [m for m in models if "pro" in m.lower()]
        return (flash_candidates or pro_candidates or models)[0]

    async def _gemini_generate_with_retry(self, endpoint: str, api_key: str, payload: dict) -> dict:
        retryable_codes = {429, 500, 502, 503, 504}
        last_error = ""
        async with httpx.AsyncClient(timeout=90.0) as client:
            for attempt in range(5):
                response = await client.post(endpoint, params={"key": api_key or ""}, json=payload)
                if response.status_code < 400:
                    return response.json()
                last_error = response.text
                if response.status_code not in retryable_codes:
                    response.raise_for_status()
                sleep_seconds = (2**attempt) + random.uniform(0, 0.5)
                await asyncio.sleep(sleep_seconds)
        raise RuntimeError(f"Gemini request failed after retries: {last_error[:400]}")

    async def complete(self, messages: list[dict], mode: str = None, llm_options: dict | None = None) -> str:
        cfg = self._resolve(mode=mode, llm_options=llm_options)
        resolved_mode = cfg["mode"]
        try:
            if resolved_mode == "local":
                response = await acompletion(
                    model=f"ollama/{cfg['ollama_model']}",
                    messages=messages,
                    api_base=cfg["ollama_base_url"],
                )
            else:
                if cfg["api_provider"] == "gemini":
                    model_name = await self._pick_gemini_model(str(cfg["api_model"]), str(cfg["api_key"] or ""))
                    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                    payload = {
                        "contents": [
                            {
                                "role": "user" if msg.get("role") != "assistant" else "model",
                                "parts": [{"text": str(msg.get("content", ""))}],
                            }
                            for msg in messages
                            if msg.get("content")
                        ],
                        "generationConfig": {"temperature": 0.2},
                    }
                    body = await self._gemini_generate_with_retry(endpoint, str(cfg["api_key"] or ""), payload)
                    candidates = body.get("candidates", [])
                    if not candidates:
                        raise RuntimeError(f"Gemini returned no candidates: {body}")
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
                    if not text:
                        raise RuntimeError(f"Gemini returned empty content: {body}")
                    return text
                else:
                    model = cfg["api_model"] if str(cfg["api_model"]).startswith("openai/") else f"openai/{cfg['api_model']}"
                    response = await acompletion(
                        model=model,
                        messages=messages,
                        api_key=cfg["api_key"] or None,
                    )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            message = str(exc)
            if "google.generativeai" in message:
                raise RuntimeError("Gemini SDK path failed unexpectedly. Please retry; backend now uses direct Gemini REST calls.") from exc
            raise

    async def complete_structured(self, messages: list[dict], schema: dict, mode: str = None, llm_options: dict | None = None) -> dict:
        prompt = f"Respond ONLY with valid JSON matching this schema: {json.dumps(schema)}. No markdown, no explanation."
        payload = deepcopy(messages)
        if payload and payload[0].get("role") == "system":
            payload[0]["content"] = f'{payload[0]["content"]}\n\n{prompt}'
        else:
            payload.insert(0, {"role": "system", "content": prompt})
        last_text = ""
        for _ in range(3):
            text = await self.complete(payload, mode=mode, llm_options=llm_options)
            last_text = text
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                candidate = self._extract_json_candidate(text)
                if candidate:
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        pass
                repair_messages = deepcopy(payload)
                repair_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous output was not valid JSON. "
                            "Return ONLY corrected JSON that matches the schema.\n\n"
                            f"Previous output:\n{text}"
                        ),
                    }
                )
                payload = repair_messages
        raise ValueError(f"Failed to parse structured response from LLM. Last response: {last_text[:400]}")

    async def compare(self, messages: list[dict], schema: dict) -> dict:
        async def timed(mode: str):
            start = time.perf_counter()
            out = await self.complete_structured(messages, schema, mode=mode)
            latency_ms = (time.perf_counter() - start) * 1000
            return out, latency_ms

        (local_out, local_ms), (api_out, api_ms) = await asyncio.gather(timed("local"), timed("api"))
        return {"local": local_out, "api": api_out, "local_ms": local_ms, "api_ms": api_ms}

    async def validate_config(self, mode: str, llm_options: dict | None = None) -> dict:
        cfg = self._resolve(mode=mode, llm_options=llm_options)
        try:
            if cfg["mode"] == "local":
                base = str(cfg["ollama_base_url"]).rstrip("/")
                async with httpx.AsyncClient(timeout=12.0) as client:
                    tags = await client.get(f"{base}/api/tags")
                    tags.raise_for_status()
                    models = tags.json().get("models", [])
                model_name = cfg["ollama_model"]
                available = any((item.get("name") or "").split(":")[0] == str(model_name).split(":")[0] for item in models)
                if not available and models:
                    return {"ok": False, "message": f"Model '{model_name}' not found in Ollama. Pull it first."}
                return {"ok": True, "message": "Ollama connection verified."}
            if cfg["api_provider"] == "gemini":
                model_name = await self._pick_gemini_model(str(cfg["api_model"]), str(cfg["api_key"] or ""))
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                try:
                    await self._gemini_generate_with_retry(
                        endpoint,
                        str(cfg["api_key"] or ""),
                        {"contents": [{"parts": [{"text": "ping"}]}]},
                    )
                except Exception as exc:
                    return {"ok": False, "message": f"Gemini validation failed: {str(exc)[:300]}"}
                return {"ok": True, "message": "Gemini API key verified."}
            # openai
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {cfg['api_key'] or ''}"},
                )
                if res.status_code >= 400:
                    return {"ok": False, "message": f"OpenAI validation failed: {res.text[:300]}"}
            return {"ok": True, "message": "OpenAI API key verified."}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}
