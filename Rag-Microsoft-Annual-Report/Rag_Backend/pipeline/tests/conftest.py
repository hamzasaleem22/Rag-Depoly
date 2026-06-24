import pytest
from pathlib import Path
from langchain_core.documents import Document

TEST_DIR = Path(__file__).parent
FIXTURE_DIR = TEST_DIR / "fixtures"


@pytest.fixture
def sample_docs() -> list[Document]:
    return [
        Document(
            page_content="Microsoft reported total revenue of $245.1 billion for fiscal year 2025.",
            metadata={"page": 5, "type": "text", "source": "test.pdf"},
        ),
        Document(
            page_content="Azure cloud services revenue grew 22% year-over-year.",
            metadata={"page": 12, "type": "text", "source": "test.pdf"},
        ),
        Document(
            page_content="Q1  Q2  Q3  Q4\n60  65  70  75\n",
            metadata={"page": 20, "type": "table", "table_index": 0, "source": "test.pdf"},
        ),
    ]


@pytest.fixture
def sample_question() -> str:
    return "What was Microsoft's total revenue in 2025?"


@pytest.fixture
def mock_llm_response() -> str:
    return "Microsoft reported total revenue of $245.1 billion for fiscal year 2025."
