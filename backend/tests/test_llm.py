import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
from google.genai import errors

from app.core.config import settings
from app.services.llm import LLMClient


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test_key")
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "fallback_llm_provider", "ollama")
    monkeypatch.setattr(settings, "embedding_provider", "gemini")
    monkeypatch.setattr(settings, "fallback_embedding_provider", "ollama")


@pytest.fixture
def llm_client(mock_settings):
    with patch("app.services.llm.genai.Client") as MockClient:
        mock_client_instance = MockClient.return_value
        mock_client_instance.aio.models.generate_content = AsyncMock()
        mock_client_instance.aio.models.embed_content = AsyncMock()
        client = LLMClient()
        client.gemini_client = mock_client_instance
        yield client


@pytest.mark.asyncio
async def test_llm_complete_gemini_success(llm_client):
    mock_response = MagicMock()
    mock_response.text = "Gemini Answer"
    llm_client.gemini_client.aio.models.generate_content.return_value = mock_response

    result = await llm_client.complete("Test prompt")
    
    assert result == "Gemini Answer"
    llm_client.gemini_client.aio.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_llm_complete_gemini_rate_limit_retry(llm_client, monkeypatch):
    # Mock sleep to avoid waiting during tests
    sleep_mock = AsyncMock()
    monkeypatch.setattr("asyncio.sleep", sleep_mock)

    # First call throws 429, second call succeeds
    error = errors.APIError("429 Resource Exhausted", {}, 429)
    mock_response = MagicMock()
    mock_response.text = "Recovered Answer"
    llm_client.gemini_client.aio.models.generate_content.side_effect = [error, mock_response]

    result = await llm_client.complete("Test prompt")
    
    assert result == "Recovered Answer"
    assert llm_client.gemini_client.aio.models.generate_content.call_count == 2
    sleep_mock.assert_called_once_with(5)


@pytest.mark.asyncio
async def test_llm_complete_fallback_to_ollama(llm_client, httpx_mock):
    # Gemini fails with non-retryable error
    llm_client.gemini_client.aio.models.generate_content.side_effect = errors.APIError("500 Internal Error", {}, 500)
    
    httpx_mock.add_response(
        url=f"{settings.ollama_base_url}/api/generate",
        json={"response": "Ollama Answer"}
    )

    result = await llm_client.complete("Test prompt")
    
    assert result == "Ollama Answer"
    llm_client.gemini_client.aio.models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_llm_embed_gemini_success(llm_client):
    mock_response = MagicMock()
    mock_response.embeddings = [MagicMock(values=[0.1, 0.2, 0.3])]
    llm_client.gemini_client.aio.models.embed_content.return_value = mock_response

    result = await llm_client.embed("Test text", task="RETRIEVAL_DOCUMENT")
    
    assert result == [0.1, 0.2, 0.3]
    llm_client.gemini_client.aio.models.embed_content.assert_called_once()


@pytest.mark.asyncio
async def test_llm_embed_fallback_to_ollama(llm_client, httpx_mock):
    # Gemini fails
    llm_client.gemini_client.aio.models.embed_content.side_effect = Exception("General Failure")
    
    httpx_mock.add_response(
        url=f"{settings.ollama_base_url}/api/embeddings",
        json={"embedding": [0.4, 0.5, 0.6]}
    )

    result = await llm_client.embed("Test text")
    
    assert result == [0.4, 0.5, 0.6]
