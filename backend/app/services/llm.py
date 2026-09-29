import asyncio
import logging

import httpx
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)

    async def complete(self, prompt: str) -> str:
        providers = [settings.llm_provider, settings.fallback_llm_provider]
        for provider in providers:
            if provider == "gemini" and settings.gemini_api_key:
                for _ in range(5):
                    try:
                        return await self._gemini(prompt)
                    except ResourceExhausted:
                        await asyncio.sleep(5)
                        continue
                    except Exception as exc:
                        logger.warning(f"Gemini completion failed: {exc}")
                    break
            elif provider == "ollama":
                try:
                    return await self._ollama(prompt)
                except httpx.HTTPError as exc:
                    logger.warning(f"Ollama completion failed: {exc}")
        return self._deterministic_fallback(prompt)

    async def embed(self, text: str, task: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        providers = [settings.embedding_provider, settings.fallback_embedding_provider]
        for provider in providers:
            if provider == "gemini" and settings.gemini_api_key:
                for _ in range(5):
                    try:
                        return await self._gemini_embed(text, task)
                    except ResourceExhausted:
                        await asyncio.sleep(5)
                        continue
                    except Exception as exc:
                        logger.warning(f"Gemini embedding failed: {exc}")
                    break
            elif provider == "ollama":
                try:
                    return await self._ollama_embed(text)
                except httpx.HTTPError as exc:
                    logger.warning(f"Ollama embedding failed: {exc}")
        return []

    async def _gemini(self, prompt: str) -> str:
        model = genai.GenerativeModel(settings.gemini_model)
        response = await model.generate_content_async(prompt)
        return response.text

    async def _gemini_embed(self, text: str, task: str) -> list[float]:
        model_name = settings.gemini_embedding_model
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
            
        response = await genai.embed_content_async(
            model=model_name,
            content=text,
            task_type=task
        )
        return response['embedding']

    async def _ollama(self, prompt: str) -> str:
        payload = {"model": settings.ollama_model, "prompt": prompt, "stream": False}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
            response.raise_for_status()
        return response.json().get("response", "")

    async def _ollama_embed(self, text: str) -> list[float]:
        payload = {"model": settings.ollama_embedding_model, "prompt": text}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{settings.ollama_base_url}/api/embeddings", json=payload)
            response.raise_for_status()
        return response.json().get("embedding", [])

    @staticmethod
    def _deterministic_fallback(prompt: str) -> str:
        return (
            "AI provider unavailable. Structural retrieval still worked; inspect the cited files, "
            "risk scores, and dependency paths below to continue analysis.\n\n"
            f"Context preview:\n{prompt[:1200]}"
        )


llm_client = LLMClient()
