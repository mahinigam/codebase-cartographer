import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    async def complete(self, prompt: str) -> str:
        if settings.llm_provider == "gemini" and settings.gemini_api_key:
            for _ in range(5):
                try:
                    return await self._gemini(prompt)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 429:
                        await asyncio.sleep(5)
                        continue
                    logger.warning(f"Gemini completion failed: {exc}")
                except httpx.HTTPError as exc:
                    logger.warning(f"Gemini completion request failed: {exc}")
                break
        if settings.fallback_llm_provider == "ollama":
            try:
                return await self._ollama(prompt)
            except httpx.HTTPError as exc:
                logger.warning(f"Ollama completion failed: {exc}")
        return self._deterministic_fallback(prompt)

    async def embed(self, text: str, task: str = "RETRIEVAL_DOCUMENT") -> list[float]:
        if settings.embedding_provider == "gemini" and settings.gemini_api_key:
            for _ in range(5):
                try:
                    return await self._gemini_embed(text, task)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 429:
                        await asyncio.sleep(5)
                        continue
                    logger.warning(f"Gemini embedding failed: {exc}")
                except httpx.HTTPError as exc:
                    logger.warning(f"Gemini embedding request failed: {exc}")
                break
        if settings.fallback_embedding_provider == "ollama":
            try:
                return await self._ollama_embed(text)
            except httpx.HTTPError as exc:
                logger.warning(f"Ollama embedding failed: {exc}")
        return []

    async def _gemini(self, prompt: str) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    async def _ollama(self, prompt: str) -> str:
        payload = {"model": settings.ollama_model, "prompt": prompt, "stream": False}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
            response.raise_for_status()
        return response.json().get("response", "")

    async def _gemini_embed(self, text: str, task: str) -> list[float]:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_embedding_model}:embedContent?key={settings.gemini_api_key}"
        )
        payload = {"content": {"parts": [{"text": text}]}, "taskType": task}
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        data = response.json()
        return data.get("embedding", {}).get("values", [])

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

