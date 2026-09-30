from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.jev_client import JevClient, JevDecision, JevResult


@pytest.fixture
def jev_client():
    client = JevClient()
    client.enabled = True
    return client


@pytest.mark.asyncio
async def test_jev_decide_success(jev_client):
    with patch("app.services.jev_client.AsyncTypeSafeClient") as MockClient:
        mock_instance = MockClient.return_value
        
        # Create a mock response
        mock_response = MagicMock()
        mock_ans1 = MagicMock()
        mock_ans1.model_dump.return_value = {"choice": "core-business-logic"}
        mock_ans2 = MagicMock()
        mock_ans2.model_dump.return_value = {"noul": 0.95}
        
        mock_response.answers = {
            "architectural_role": mock_ans1,
            "is_test": mock_ans2
        }
        mock_instance.system_one = AsyncMock(return_value=mock_response)
        
        result = await jev_client.decide(
            state={"file_path": "test.py"},
            questions={"architectural_role": {}, "is_test": {}}
        )
        
        assert isinstance(result, JevResult)
        assert result.architectural_role.answer == "core-business-logic"
        assert result.is_test.probability == 0.95


@pytest.mark.asyncio
async def test_jev_decide_failure(jev_client, caplog):
    with patch("app.services.jev_client.AsyncTypeSafeClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.system_one = AsyncMock(side_effect=Exception("API Timeout"))
        
        result = await jev_client.decide(
            state={"file_path": "test.py"},
            questions={"architectural_role": {}}
        )
        
        assert result is None
        assert "Jev API request failed: API Timeout" in caplog.text


@pytest.mark.asyncio
async def test_jev_bond_classify_file(jev_client):
    with patch.object(jev_client, "decide") as mock_decide:
        mock_decide.return_value = JevResult({
            "architectural_role": JevDecision({"choice": "utility-helper", "confidence": 0.88})
        })
        
        result = await jev_client.classify_file(
            file_path="utils.py",
            language="python",
            loc=50,
            complexity=2,
            fan_in=10,
            fan_out=1,
            symbols=["parse", "format"],
            imports=[],
            external_deps=[],
            snippet="def parse(): pass"
        )
        
        assert result.architectural_role.answer == "utility-helper"
        assert result.architectural_role.confidence == 0.88
        
        # Verify state payload was constructed properly
        call_args = mock_decide.call_args[0]
        state = call_args[0]
        assert state["file_path"] == "utils.py"
        assert state["loc"] == 50


@pytest.mark.asyncio
async def test_jev_bond_score_semantic_risk(jev_client):
    with patch.object(jev_client, "decide") as mock_decide:
        mock_decide.return_value = JevResult({
            "semantic_risk": JevDecision({"score": 7}),
            "risk_category": JevDecision({"choice": "structural-chokepoint"})
        })
        
        result = await jev_client.score_semantic_risk(
            file_path="core.py",
            language="python",
            loc=500,
            complexity=25,
            fan_in=100,
            fan_out=5,
            churn_count=20,
            symbols=[],
            imports=[],
            dependents=[],
            external_deps=[]
        )
        
        assert result.semantic_risk.value == 7
        assert result.risk_category.answer == "structural-chokepoint"


@pytest.mark.asyncio
async def test_jev_bond_triage_for_summary(jev_client):
    with patch.object(jev_client, "decide") as mock_decide:
        mock_decide.return_value = JevResult({
            "needs_summary": JevDecision({"noul": 0.1}),
            "summary_priority": JevDecision({"score": 2})
        })
        
        result = await jev_client.triage_for_summary(
            file_path="index.ts",
            language="typescript",
            loc=5,
            complexity=1,
            fan_in=50,
            fan_out=2,
            symbols=[]
        )
        
        assert result.needs_summary.probability == 0.1
        assert result.summary_priority.value == 2


@pytest.mark.asyncio
async def test_jev_bond_detect_test_file(jev_client):
    with patch.object(jev_client, "decide") as mock_decide:
        mock_decide.return_value = JevResult({
            "is_test": JevDecision({"noul": 0.9}),
            "test_category": JevDecision({"choice": "unit-test"})
        })
        
        result = await jev_client.detect_test_file(
            "test.py", "python", [], [], [], ""
        )
        assert result.is_test.probability == 0.9
        assert result.test_category.answer == "unit-test"


@pytest.mark.asyncio
async def test_jev_bond_route_query(jev_client):
    with patch.object(jev_client, "decide") as mock_decide:
        mock_decide.return_value = JevResult({
            "intent": JevDecision({"choice": "risk-assessment"}),
            "needs_ai_generation": JevDecision({"noul": 0.2})
        })
        
        result = await jev_client.route_query("What is risky?")
        assert result.intent.answer == "risk-assessment"
        assert result.needs_ai_generation.probability == 0.2


@pytest.mark.asyncio
async def test_jev_bond_assess_cluster(jev_client):
    with patch.object(jev_client, "decide") as mock_decide:
        mock_decide.return_value = JevResult({
            "cohesion": JevDecision({"score": 4}),
            "coupling": JevDecision({"score": 2}),
            "extraction_readiness": JevDecision({"choice": "ready-to-extract"})
        })
        
        result = await jev_client.assess_cluster("api", 5, 2.0, 5.0, [], 10, 2, 2)
        assert result.cohesion.value == 4
        assert result.coupling.value == 2


@pytest.mark.asyncio
async def test_jev_bond_evaluate_refactor_safety(jev_client):
    with patch.object(jev_client, "decide") as mock_decide:
        mock_decide.return_value = JevResult({
            "safe_to_refactor": JevDecision({"noul": 0.1}),
            "recommended_strategy": JevDecision({"choice": "strangler-fig-pattern"}),
            "estimated_blast_radius": JevDecision({"score": 9})
        })
        
        result = await jev_client.evaluate_refactor_safety("core.py", [], [], 8.0, 50, 1000)
        assert result.safe_to_refactor.probability == 0.1
        assert result.estimated_blast_radius.value == 9


@pytest.mark.asyncio
async def test_jev_bond_detect_framework(jev_client):
    with patch.object(jev_client, "decide") as mock_decide:
        mock_decide.return_value = JevResult({
            "framework": JevDecision({"choice": "react"}),
            "layer": JevDecision({"choice": "presentation-ui"})
        })
        
        result = await jev_client.detect_framework("App.tsx", "typescript", ["react"], [], [])
        assert result.framework.answer == "react"


@pytest.mark.asyncio
async def test_jev_bond_should_resummarize(jev_client):
    with patch.object(jev_client, "decide") as mock_decide:
        mock_decide.return_value = JevResult({
            "needs_resummarize": JevDecision({"noul": 0.8}),
            "change_significance": JevDecision({"score": 6})
        })
        
        result = await jev_client.should_resummarize("app.py", "python", 10, 50, 1, 5, "a", "b", "sum")
        assert result.needs_resummarize.probability == 0.8


@pytest.mark.asyncio
async def test_jev_bond_detect_dead_code(jev_client):
    with patch.object(jev_client, "decide") as mock_decide:
        mock_decide.return_value = JevResult({
            "is_dead_code": JevDecision({"noul": 0.95}),
            "dead_code_category": JevDecision({"choice": "abandoned-feature"})
        })
        
        result = await jev_client.detect_dead_code("old.py", "python", 10, 0, 0, 0, None, [], [])
        assert result.is_dead_code.probability == 0.95
