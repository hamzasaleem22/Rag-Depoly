from langchain_core.prompts import ChatPromptTemplate
from src.config import config

_prompt: ChatPromptTemplate | None = None


def get_prompt() -> ChatPromptTemplate:
    global _prompt
    if _prompt is None:
        _prompt = ChatPromptTemplate.from_messages([
            ("system", config.prompt.system),
            ("human", config.prompt.human),
        ])
    return _prompt


def format_context(docs) -> str:
    formatted = []
    for i, doc in enumerate(docs):
        page = doc.metadata.get("page", "N/A")
        doc_type = doc.metadata.get("type", "text")
        formatted.append(
            f"[Source {i + 1}] (Page {page}, Type: {doc_type})\n{doc.page_content}"
        )
    return "\n\n---\n\n".join(formatted)
