from src.generation.prompt import get_prompt, format_context
from src.config import config


def test_get_prompt_returns_template():
    prompt = get_prompt()
    messages = prompt.format_messages(
        context="test context", question="test question"
    )
    assert len(messages) == 2
    assert messages[0].type == "system"
    assert messages[1].type == "human"


def test_format_context_returns_string(sample_docs):
    result = format_context(sample_docs)
    assert isinstance(result, str)
    assert "Source 1" in result
    assert "Source 2" in result
    assert "Page" in result


def test_format_context_empty():
    result = format_context([])
    assert result == ""


def test_format_context_includes_page_numbers(sample_docs):
    result = format_context(sample_docs)
    for doc in sample_docs:
        page = str(doc.metadata.get("page", ""))
        if page:
            assert page in result
