import pytest

from app.services import analysis
from app.services.neo4j_store import _search_words


def test_search_words_keeps_architectural_signal() -> None:
    words = _search_words("Which files mention scanner?")

    assert words == ["scanner"]


def test_search_words_filters_generic_query_terms() -> None:
    words = _search_words("What are the riskiest parts of this codebase?")

    assert "codebase" not in words
    assert "what" not in words
    assert "riskiest" in words


@pytest.mark.asyncio
async def test_risk_question_falls_back_to_load_bearing_files(monkeypatch) -> None:
    class FakeStore:
        def search_files(self, question: str, repo_path: str | None = None) -> list[dict]:
            return []

        def top_load_bearing_files(
            self, limit: int = 10, repo_path: str | None = None
        ) -> list[dict]:
            return [
                {
                    "path": "backend/app/indexing/scanner.py",
                    "language": "python",
                    "load_bearing_score": 66.19,
                }
            ]

        def semantic_search(
            self, embedding: list[float], limit: int = 6, repo_path: str | None = None
        ) -> list[dict]:
            return []

    class FakeLlm:
        async def embed(self, text: str, task: str) -> list[float]:
            return []

        async def complete(self, prompt: str) -> str:
            return "AI provider unavailable"

    monkeypatch.setattr(analysis, "llm_client", FakeLlm())

    result = await analysis.answer_architecture_question(
        FakeStore(), "What are the riskiest parts of this codebase?", "repo"
    )

    assert result["evidence"][0]["path"] == "backend/app/indexing/scanner.py"
    assert "backend/app/indexing/scanner.py" in result["answer"]


@pytest.mark.asyncio
async def test_summarize_file_rejects_paths_outside_repo(tmp_path) -> None:
    secret = tmp_path.parent / "secret.py"
    secret.write_text("password = 'not-for-llm'", encoding="utf-8")
    (tmp_path / "ok.py").write_text("print('ok')\n", encoding="utf-8")

    summary = await analysis._summarize_file(tmp_path, "../secret.py")

    assert summary == ""
