import re
from pathlib import Path

import pandas as pd
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
import camelot
import logging

logger = logging.getLogger(__name__)

_NOISE_PATTERNS = [
    r"\d+/\d+/\d+,\s*\d+:\d+\s*(AM|PM)",  # timestamps: 5/31/26, 11:20 PM
    r"Microsoft \d{4} Annual Report",       # page headers
    r"^https?://\S+",                       # URLs
    r"^\s*$",                               # empty lines
    r"^\s*\d+\s*$",                         # standalone page numbers
]


def _is_noise(text: str) -> bool:
    return any(re.search(p, text) for p in _NOISE_PATTERNS)


def _clean_table_df(df: "pd.DataFrame") -> "pd.DataFrame":
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
    df = df.map(lambda x: x if isinstance(x, str) and x else "")
    rows_before = len(df)
    df = df[~df.apply(lambda row: all(_is_noise(cell) for cell in row), axis=1)]
    df = df[~df.apply(lambda row: all(cell == "" or cell == "y" for cell in row), axis=1)]
    df = df.dropna(how="all")
    df = df.loc[:, ~df.apply(lambda col: col.astype(str).str.match(r"^\d+$").all())]
    logger.debug("Cleaned table: %d rows -> %d rows", rows_before, len(df))
    return df


def load_pdf_text(pdf_path: str) -> list[Document]:
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    loader = PyMuPDFLoader(pdf_path)
    docs = loader.load()
    for doc in docs:
        doc.metadata["type"] = "text"
    logger.info("Loaded %d text pages from PDF", len(docs))
    return docs


def load_pdf_tables(pdf_path: str) -> list[Document]:
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    logger.info("Skipping table extraction (no tables detected)")
    return []

    docs = []
    for i, table in enumerate(tables):
        df = table.df
        page = table.parsing_report["page"]
        df = _clean_table_df(df)
        if df.empty:
            continue
        table_text = df.to_string(index=False, header=False)
        doc = Document(
            page_content=table_text,
            metadata={
                "source": pdf_path,
                "page": page,
                "type": "table",
                "table_index": i,
            },
        )
        docs.append(doc)

    logger.info("Extracted %d table documents", len(docs))
    return docs


def load_all(pdf_path: str) -> list[Document]:
    text_docs = load_pdf_text(pdf_path)
    table_docs = load_pdf_tables(pdf_path)
    all_docs = text_docs + table_docs
    logger.info("Total documents: %d text + %d tables = %d", len(text_docs), len(table_docs), len(all_docs))
    return all_docs
