import pytest
from src.retrieval.reranker import rerank


def test_rerank_returns_top_k(sample_docs, sample_question):
    top_k = 2
    result = rerank(sample_question, sample_docs, top_k=top_k)
    assert len(result) == top_k
    assert all(isinstance(d.page_content, str) for d in result)


def test_rerank_orders_by_relevance(sample_docs, sample_question):
    result = rerank(sample_question, sample_docs, top_k=3)
    scores = []
    for doc in result:
        if "revenue" in doc.page_content.lower():
            scores.append(1)
        else:
            scores.append(0)
    assert scores[0] == 1


def test_rerank_empty_docs(sample_question):
    result = rerank(sample_question, [], top_k=5)
    assert result == []


def test_rerank_returns_list(sample_docs, sample_question):
    result = rerank(sample_question, sample_docs, top_k=5)
    assert isinstance(result, list)
