from src.ingestion.chunker import chunk_documents


def test_chunk_documents_returns_chunks(sample_docs):
    chunks = chunk_documents(sample_docs, chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 0
    assert all(isinstance(c.page_content, str) for c in chunks)


def test_chunk_documents_preserves_metadata(sample_docs):
    chunks = chunk_documents(sample_docs, chunk_size=200, chunk_overlap=20)
    for c in chunks:
        assert "page" in c.metadata
        assert "type" in c.metadata


def test_chunk_documents_empty_input():
    chunks = chunk_documents([], chunk_size=200, chunk_overlap=20)
    assert chunks == []


def test_chunk_size_respected(sample_docs):
    chunk_size = 50
    chunks = chunk_documents(sample_docs, chunk_size=chunk_size, chunk_overlap=0)
    for c in chunks:
        assert len(c.page_content) <= chunk_size * 1.1
