import os
import sys
import textwrap
import argparse
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import camelot
from sentence_transformers import CrossEncoder
import uvicorn

load_dotenv()

GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")

if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
if HF_TOKEN:
    os.environ["HF_TOKEN"] = HF_TOKEN

BASE_DIR = Path(__file__).resolve().parent
PDF_PATH = str(BASE_DIR / "Microsoft 2025 Annual Report.pdf")
FAISS_INDEX_PATH = str(BASE_DIR / "faiss_index")

embeddings = None
vectorstore = None
retriever = None
reranker_model = None
llm = None
chunks = []
table_docs = []


def install_dependencies():
    system_pkgs = ["ghostscript"]
    python_pkgs = [
        "langchain",
        "langchain-community",
        "langchain-google-genai",
        "langchain-huggingface",
        "pymupdf",
        "faiss-cpu",
        "sentence-transformers",
        "camelot-py[cv]",
        "google-generativeai",
        "fastapi",
        "uvicorn",
        "python-dotenv",
    ]

    print("Installing system packages...")
    for pkg in system_pkgs:
        subprocess.run(
            ["apt-get", "install", "-y", "-qq", pkg],
            capture_output=True,
        )

    print("Installing Python packages...")
    for pkg in python_pkgs:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", pkg],
            capture_output=True,
        )

    print("All dependencies installed.")


def load_pdf_text():
    global text_docs
    loader = PyMuPDFLoader(PDF_PATH)
    text_docs = loader.load()
    for doc in text_docs:
        doc.metadata["type"] = "text"
    print(f"Loaded {len(text_docs)} pages of narrative text")
    return text_docs


def load_pdf_tables():
    global table_docs
    tables = camelot.read_pdf(PDF_PATH, pages="all", flavor="lattice")
    print(f"Found {tables.n} tables using lattice flavor")

    if tables.n == 0:
        tables = camelot.read_pdf(PDF_PATH, pages="all", flavor="stream")
        print(f"Found {tables.n} tables using stream flavor")

    table_docs = []
    for i, table in enumerate(tables):
        df = table.df
        page = table.parsing_report["page"]
        table_text = df.to_string(index=False)
        doc = Document(
            page_content=table_text,
            metadata={"source": PDF_PATH, "page": page, "type": "table", "table_index": i},
        )
        table_docs.append(doc)

    print(f"Extracted {len(table_docs)} table documents")
    return table_docs


def chunk_documents(all_docs):
    global chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=250,
        separators=["\n\n", "\n", ".", " "],
        length_function=len,
    )
    chunks = splitter.split_documents(all_docs)
    print(f"Total chunks after splitting: {len(chunks)}")
    return chunks


def build_vectorstore():
    global embeddings, vectorstore, retriever
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    vectorstore = FAISS.from_documents(chunks, embeddings)
    os.makedirs(os.path.dirname(FAISS_INDEX_PATH), exist_ok=True)
    vectorstore.save_local(FAISS_INDEX_PATH)
    print(f"FAISS index created and saved to {FAISS_INDEX_PATH}")
    print(f"Index contains {vectorstore.index.ntotal} vectors")

    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 10, "fetch_k": 20, "lambda_mult": 0.5},
    )
    return vectorstore


def load_vectorstore():
    global embeddings, vectorstore, retriever, chunks
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    vectorstore = FAISS.load_local(
        FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True
    )
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 10, "fetch_k": 20, "lambda_mult": 0.5},
    )
    chunks = [None] * vectorstore.index.ntotal
    print(f"Loaded FAISS index from {FAISS_INDEX_PATH}")
    print(f"Index contains {vectorstore.index.ntotal} vectors")
    return vectorstore


def init_reranker():
    global reranker_model
    reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    print("Reranker model loaded")
    return reranker_model


def rerank_docs(query, docs, top_k=5):
    pairs = [[query, doc.page_content] for doc in docs]
    scores = reranker_model.predict(pairs)
    scored = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in scored[:top_k]]


def init_llm():
    global llm
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=1024,
        google_api_key=GEMINI_API_KEY,
    )
    return llm


prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a financial analyst assistant. Answer questions based ONLY on the provided context.
If the context doesn't contain the answer, say "I cannot find this information in the document.Kindly ask relevent informations"
Cite the page numbers from the metadata when possible.
Context:
{context}"""),
    ("human", "{question}"),
])


def format_docs_for_prompt(docs):
    formatted = []
    for i, doc in enumerate(docs):
        page = doc.metadata.get("page", "N/A")
        doc_type = doc.metadata.get("type", "text")
        formatted.append(f"[Source {i+1}] (Page {page}, Type: {doc_type})\n{doc.page_content}")
    return "\n\n---\n\n".join(formatted)


def rag_pipeline(question):
    retrieved = retriever.invoke(question)
    top_docs = rerank_docs(question, retrieved, top_k=5)
    context = format_docs_for_prompt(top_docs)
    messages = prompt.format_messages(context=context, question=question)
    response = llm.invoke(messages)
    sources = [
        {"page": d.metadata.get("page"), "type": d.metadata.get("type"), "content": d.page_content[:200]}
        for d in top_docs
    ]
    if isinstance(response.content, str):
        answer = response.content
    else:
        answer = " ".join(p.get("text", str(p)) if isinstance(p, dict) else str(p) for p in response.content)
    return {"answer": answer, "sources": sources}


def ingest_pipeline():
    print("Loading PDF text...")
    text_docs = load_pdf_text()
    print("Loading PDF tables...")
    table_docs = load_pdf_tables()
    all_docs = text_docs + table_docs
    print(f"Total documents: {len(all_docs)}")
    chunk_documents(all_docs)
    build_vectorstore()
    init_reranker()
    init_llm()
    print("Ingestion complete.")
    return {"chunks": len(chunks), "tables": len(table_docs)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.path.exists(FAISS_INDEX_PATH):
        load_vectorstore()
    else:
        ingest_pipeline()
    init_reranker()
    init_llm()
    yield

app = FastAPI(title="RAG Backend — Microsoft 2025 Annual Report", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    sources: list


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "chunks": len(chunks),
        "tables": len(table_docs),
    }


@app.post("/ingest")
async def ingest():
    result = ingest_pipeline()
    return {"message": "Ingested successfully", **result}


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    result = rag_pipeline(request.question)
    return QueryResponse(answer=result["answer"], sources=result["sources"])


def run_server():
    if os.path.exists(FAISS_INDEX_PATH):
        load_vectorstore()
    else:
        ingest_pipeline()
    init_reranker()
    init_llm()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


def run_test_queries(questions=None):
    if questions is None:
        questions = [
            "What was Microsoft's total revenue in 2025?",
            "What did Satya Nadella say about AI?",
            "How much did Azure revenue grow?",
            "What is the Secure Future Initiative?",
            "How many datacenters does Microsoft operate?",
        ]

    for q in questions:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        result = rag_pipeline(q)
        print(f"A: {textwrap.fill(result['answer'], width=80)}")
        pages = [s["page"] for s in result["sources"] if s["page"]]
        print(f"Sources: {pages}")


def main():
    parser = argparse.ArgumentParser(description="RAG Pipeline — Microsoft 2025 Annual Report")
    parser.add_argument(
        "--install", action="store_true", help="Install system & Python dependencies"
    )
    parser.add_argument(
        "--ingest", action="store_true", help="Run ingestion (PDF -> chunks -> FAISS)"
    )
    parser.add_argument(
        "--server", action="store_true", help="Start FastAPI server"
    )
    parser.add_argument(
        "--query", type=str, nargs="*", help="Run one or more test queries"
    )
    parser.add_argument(
        "--no-reindex", action="store_true",
        help="Skip re-indexing; load existing FAISS index (use with --query or --server)"
    )

    args = parser.parse_args()

    if args.install:
        install_dependencies()
        return

    if args.ingest:
        ingest_pipeline()
        return

    if args.server:
        run_server()
        return

    if args.query is not None:
        if args.no_reindex:
            load_vectorstore()
        else:
            ingest_pipeline()
        init_reranker()
        init_llm()
        run_test_queries(args.query if args.query else None)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
