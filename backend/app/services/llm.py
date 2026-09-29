import asyncio
import logging

import httpx
from google import genai
from google.genai import errors
from google.genai.types import TaskType

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.gemini_client = None
        if settings.gemini_api_key:
            self.gemini_client = genai.Client(api_key=settings.gemini_api_key)

    async def complete(self, prompt: str) -> str:
        providers = [settings.llm_provider, settings.fallback_llm_provider]
        for provider in providers:
            if provider == "gemini" and self.gemini_client:
                for _ in range(5):
                    try:
                        return await self._gemini(prompt)
                    except errors.APIError as exc:
                        if "429" in str(exc):
                            await asyncio.sleep(5)
                            continue
                        logger.warning(f"Gemini completion failed: {exc}")
                        break
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
            if provider == "gemini" and self.gemini_client:
                for _ in range(5):
                    try:
                        return await self._gemini_embed(text, task)
                    except errors.APIError as exc:
                        if "429" in str(exc):
                            await asyncio.sleep(5)
                            continue
                        logger.warning(f"Gemini embedding failed: {exc}")
                        break
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
        response = await self.gemini_client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        return response.text

    async def _gemini_embed(self, text: str, task: str) -> list[float]:
        # Maps the string "RETRIEVAL_DOCUMENT" to TaskType.RETRIEVAL_DOCUMENT etc.
        try:
            task_type = getattr(TaskType, task)
        except AttributeError:
            task_type = TaskType.RETRIEVAL_DOCUMENT
            
        model_name = settings.gemini_embedding_model
        
        response = await self.gemini_client.aio.models.embed_content(
            model=model_name,
            contents=text,
            config={"task_type": task_type}
        )
        return response.embeddings[0].values

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
