from app.services.neo4j_store import _search_words


def test_search_words_keeps_architectural_signal() -> None:
    words = _search_words("Which files mention scanner?")

    assert words == ["scanner"]


def test_search_words_filters_generic_query_terms() -> None:
    words = _search_words("What are the riskiest parts of this codebase?")

    assert "codebase" not in words
    assert "what" not in words
    assert "riskiest" in words

