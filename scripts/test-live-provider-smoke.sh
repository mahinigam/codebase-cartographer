#!/usr/bin/env bash
set -euo pipefail

if [[ "${RUN_LIVE_PROVIDER_SMOKE:-}" != "1" ]]; then
  echo "Set RUN_LIVE_PROVIDER_SMOKE=1 to allow a real provider request." >&2
  exit 2
fi

case "${LLM_PROVIDER:-}" in
  gemini)
    if [[ -z "${GEMINI_API_KEY:-}" ]]; then
      echo "GEMINI_API_KEY is required." >&2
      exit 2
    fi
    ;;
  ollama)
    if [[ -z "${OLLAMA_BASE_URL:-}" ]]; then
      echo "OLLAMA_BASE_URL is required." >&2
      exit 2
    fi
    ;;
  *)
    echo "LLM_PROVIDER must be gemini or ollama." >&2
    exit 2
    ;;
esac

echo "WARNING: this sends one live request to ${LLM_PROVIDER}; provider usage may incur cost."

cd backend
uv run python - <<'PY'
import asyncio
import logging

from app.core.config import settings
from app.services.llm import LLMClient


async def smoke() -> None:
    logging.disable(logging.CRITICAL)
    client = LLMClient()
    try:
        result = await asyncio.wait_for(
            (
                client._gemini("Reply with the single word READY.")
                if settings.llm_provider == "gemini"
                else client._ollama("Reply with the single word READY.")
            ),
            timeout=45,
        )
    except Exception as exc:
        raise SystemExit(
            f"Provider smoke failed ({type(exc).__name__}); details suppressed."
        ) from None
    if not result.strip():
        raise SystemExit("Selected provider did not return a live completion.")
    print(f"{settings.llm_provider} provider responded; response omitted.")


asyncio.run(smoke())
PY
