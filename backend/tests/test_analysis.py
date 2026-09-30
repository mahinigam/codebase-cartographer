import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.jev_client import JevResult, JevDecision

@pytest.fixture
def mock_store():
    return MagicMock()

from app.services import analysis
from app.services.analysis import explain_impact, generate_summaries_for_repo, answer_architecture_question
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

@pytest.mark.asyncio
async def test_generate_summaries_skips_gemini_if_jev_triage_fails(monkeypatch) -> None:
    class FakeStore:
        def file_paths(self, repo_path: str) -> list[str]:
            return ["utils.py"]
            
        def files_list(self, repo_path: str | None = None) -> list[dict]:
            return [{"path": "utils.py", "language": "python", "loc": 10}]
            
    class FakeJev:
        enabled = True
        async def triage_for_summary(self, *args, **kwargs):
            from app.services.jev_client import JevResult, JevDecision
            return JevResult({
                "needs_summary": JevDecision({"noul": 0.1}),  # < 0.5 means skip
                "summary_priority": JevDecision({"score": 1})
            })
            
    class FakeLLM:
        pass  # if complete/embed is called, it will crash and fail the test

    monkeypatch.setattr(analysis, "jev_client", FakeJev())
    monkeypatch.setattr(analysis, "llm_client", FakeLLM())
    monkeypatch.setattr(analysis, "_compute_fan_in", lambda *a, **k: {})

    result = await analysis.generate_summaries_for_repo(FakeStore(), "repo", max_files=10)
    
    assert result["requested"] == 0
    assert result["triaged_out"] == 1
    assert result["created"] == 0


@pytest.mark.asyncio
async def test_explain_impact(mock_store, monkeypatch):
    class FakeJev:
        async def evaluate_refactor_safety(self, *a, **k):
            return JevResult({
                "safe_to_refactor": JevDecision({"noul": 0.9}),
                "recommended_strategy": JevDecision({"choice": "rewrite"}),
                "estimated_blast_radius": JevDecision({"score": 5})
            })

    class FakeLLM:
        async def complete(self, *a, **k):
            return "Test explanation"

    monkeypatch.setattr(analysis, "jev_client", FakeJev())
    monkeypatch.setattr(analysis, "llm_client", FakeLLM())

    result = await analysis.explain_impact(mock_store, "a.py", 2)
    assert result["refactor_safety"]["safe_to_refactor"] is True
    assert result["refactor_safety"]["recommended_strategy"] == "rewrite"
    assert result["explanation"] == "Test explanation"




@pytest.mark.asyncio
async def test_explain_impact(monkeypatch):
    mock_store = MagicMock()
    mock_store.impact_for_file.return_value = {"direct_dependents": [], "transitive_dependents": []}
    mock_store.file_detail.return_value = {"load_bearing_score": 10, "complexity": 5, "loc": 100}

    mock_jev = MagicMock()
    
    mock_jev_result = {
        "safe_to_refactor": MagicMock(probability=0.8),
        "recommended_strategy": MagicMock(answer="Strategy"),
        "estimated_blast_radius": MagicMock(value=5.0)
    }
    mock_jev.evaluate_refactor_safety = AsyncMock(return_value=mock_jev_result)
    monkeypatch.setattr("app.services.analysis.jev_client", mock_jev)
    
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value="impact explanation")
    monkeypatch.setattr("app.services.analysis.llm_client", mock_llm)

    res = await explain_impact(mock_store, "a.py", 3, "/repo")
    assert res["refactor_safety"]["safe_to_refactor"] is True
    assert res["explanation"] == "impact explanation"


@pytest.mark.asyncio
async def test_generate_summaries(monkeypatch):
    mock_store = MagicMock()
    mock_store.file_paths.return_value = ["a.py", "b.py"]
    mock_store.files_list.return_value = [
        {"path": "a.py", "language": "python", "loc": 10},
        {"path": "b.py", "language": "python", "loc": 20}
    ]
    mock_store.get_existing_summary.return_value = {"text": "existing"}

    mock_jev = MagicMock()
    mock_jev.enabled = True
    
    # Mock triage_for_summary
    mock_triage_result1 = {
        "needs_summary": MagicMock(probability=0.8),
        "summary_priority": MagicMock(value=10.0)
    }
    mock_triage_result2 = {
        "needs_summary": MagicMock(probability=0.2), # skip
        "summary_priority": MagicMock(value=1.0)
    }
    
    async def mock_triage(file_path, **kwargs):
        if file_path == "a.py":
            return mock_triage_result1
        return mock_triage_result2
        
    mock_jev.triage_for_summary = AsyncMock(side_effect=mock_triage)
    
    # Mock resummarize
    mock_resummarize = {
        "needs_resummarization": MagicMock(probability=0.8),
        "reasoning": MagicMock(answer="changed a lot")
    }
    mock_jev.should_resummarize = AsyncMock(return_value=mock_resummarize)
    monkeypatch.setattr("app.services.analysis.jev_client", mock_jev)
    
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value="new summary")
    mock_llm.embed = AsyncMock(return_value=[0.1, 0.2])
    monkeypatch.setattr("app.services.analysis.llm_client", mock_llm)
    
    mock_summarize = AsyncMock(return_value="file summary text")
    monkeypatch.setattr("app.services.analysis._summarize_file", mock_summarize)
    
    res = await generate_summaries_for_repo(mock_store, "/repo", max_files=5)
    assert res["requested"] == 1
    assert res["triaged_out"] == 1
    assert res["created"] == 1


@pytest.mark.asyncio
async def test_generate_summaries_no_files(monkeypatch):
    mock_store = MagicMock()
    mock_store.file_paths.return_value = []
    res = await generate_summaries_for_repo(mock_store, "/repo")
    assert res["requested"] == 0


@pytest.mark.asyncio
async def test_answer_architecture_question(monkeypatch):
    mock_store = MagicMock()
    mock_store.search_files.return_value = [{
        "path": "a.py", 
        "language": "python", 
        "symbols": [],
        "imports": [],
        "dependents": [],
        "external_deps": [],
        "load_bearing_score": 10,
        "matched_words": ["how"]
    }]
    mock_store.file_detail.return_value = {"path": "a.py"}
    
    mock_jev = MagicMock()
    mock_sys2 = {
        "answer": MagicMock(answer="It works fine."),
        "relevant_files": MagicMock(files=["a.py"])
    }
    mock_jev.system2_query = AsyncMock(return_value=mock_sys2)
    mock_jev.route_query = AsyncMock(return_value={"route": MagicMock(value="system2")})
    monkeypatch.setattr("app.services.analysis.jev_client", mock_jev)
    
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value="It works fine.")
    mock_llm.embed = AsyncMock(return_value=[0.1, 0.2])
    monkeypatch.setattr("app.services.analysis.llm_client", mock_llm)
    
    res = await answer_architecture_question(mock_store, "how?", "/repo")
    assert res["answer"] == "It works fine."
    assert res["evidence"][0]["path"] == "a.py"


def test_format_impact():
    impact = {"target": "a.py", "direct_dependents": ["b.py"], "transitive_dependents": [{"path": "c.py", "distance": 2}]}
    res = analysis._format_impact_as_markdown(impact)
    assert "a.py" in res
    assert "b.py" in res


@pytest.mark.asyncio
async def test_generate_impact_narrative(monkeypatch):
    class FakeLLM:
        async def complete(self, *a, **k): return "narrative"
    monkeypatch.setattr(analysis, "llm_client", FakeLLM())
    assert await analysis._generate_impact_narrative({"target": "a"}, "a") == "narrative"


def test_asks_about_risk():
    assert analysis._asks_about_risk("risk") == True
    assert analysis._asks_about_risk("load bearing") == True
    assert analysis._asks_about_risk("hello") == False


def test_load_bearing_matches(mock_store):
    mock_store.top_load_bearing_files = MagicMock(return_value=[{"path": "a", "language": "python", "load_bearing_score": 10}])
    assert len(analysis._load_bearing_matches(mock_store, "/repo")) == 1


def test_compute_fan_in(mock_store):
    session = mock_store.driver.session.return_value.__enter__.return_value
    session.run.return_value = [{"path": "a.py", "fan_in": 2}]
    assert analysis._compute_fan_in(mock_store, "/repo")["a.py"] == 2


def test_evidence_summary():
    assert "a.py" in analysis._evidence_summary("q", [{"path": "a.py", "summary": "s", "symbols": [], "language": "python", "load_bearing_score": 10, "imports": [], "dependents": [], "external_deps": []}])

@pytest.mark.asyncio
async def test_summarize_file(monkeypatch, tmp_path):
    import app.services.analysis
    
    test_file = tmp_path / "test.py"
    test_file.write_text("print('hello')")
    
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value=" summary ")
    monkeypatch.setattr("app.services.analysis.llm_client", mock_llm)
    
    res = await app.services.analysis._summarize_file(tmp_path, "test.py")
    assert res == "summary"

    # Test not exists
    res_empty = await app.services.analysis._summarize_file(tmp_path, "missing.py")
    assert res_empty == ""

