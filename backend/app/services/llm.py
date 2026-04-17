import httpx

from app.core.config import settings


class LLMClient:
    async def complete(self, prompt: str) -> str:
        if settings.llm_provider == "gemini" and settings.gemini_api_key:
            try:
                return await self._gemini(prompt)
            except httpx.HTTPError:
                pass
        if settings.fallback_llm_provider == "ollama":
            try:
                return await self._ollama(prompt)
            except httpx.HTTPError:
                pass
        return self._deterministic_fallback(prompt)

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

    @staticmethod
    def _deterministic_fallback(prompt: str) -> str:
        return (
            "AI provider unavailable. Structural retrieval still worked; inspect the cited files, "
            "risk scores, and dependency paths below to continue analysis.\n\n"
            f"Context preview:\n{prompt[:1200]}"
        )


llm_client = LLMClient()

