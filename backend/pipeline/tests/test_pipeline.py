import pytest
from src.cache import QueryCache


def test_cache_miss_and_hit():
    c = QueryCache()
    c.clear()
    assert c.get("test question") is None
    c.set("test question", {"answer": "test answer", "sources": []})
    result = c.get("test question")
    assert result is not None
    assert result["answer"] == "test answer"


def test_cache_clear():
    c = QueryCache()
    c.set("q1", {"answer": "a1", "sources": []})
    c.clear()
    assert c.get("q1") is None


def test_cache_different_queries():
    c = QueryCache()
    c.set("q1", {"answer": "a1", "sources": []})
    c.set("q2", {"answer": "a2", "sources": []})
    assert c.get("q1")["answer"] == "a1"
    assert c.get("q2")["answer"] == "a2"
