import argparse
import textwrap
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")


def _ensure_index():
    from src.pipeline import ingest, is_indexed
    if not is_indexed():
        print("No index found, running ingestion first...")
        ingest()


def _print_answer(q: str, result: dict):
    print(f"\n{'=' * 60}")
    print(f"Q: {q}")
    print(f"A: {textwrap.fill(result['answer'], width=80)}")
    pages = [s["page"] for s in result["sources"] if s.get("page")]
    print(f"Sources: {pages}")


def main():
    parser = argparse.ArgumentParser(
        description="RAG Pipeline — Microsoft 2025 Annual Report"
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
        "--repl", action="store_true", help="Interactive REPL (stay loaded between queries)"
    )

    args = parser.parse_args()

    if args.ingest:
        from src.pipeline import ingest
        result = ingest()
        print(f"Ingested {result['chunks']} chunks, {result['tables']} tables")
        return

    if args.server:
        import uvicorn
        from src.config import config
        uvicorn.run(
            "src.api.server:app",
            host=config.server.host,
            port=config.server.port,
            log_level=config.server.log_level,
        )
        return

    if args.repl:
        _ensure_index()
        from src.pipeline import query
        print("\nREPL mode — type your questions. Type 'exit', 'quit', or press Ctrl+C to stop.")
        while True:
            try:
                q = input(">>> ")
            except EOFError:
                break
            if q.lower() in ("exit", "quit", "/exit", "/quit"):
                break
            if not q.strip():
                continue
            result = query(q)
            _print_answer(q, result)
        return

    if args.query is not None:
        _ensure_index()
        from src.pipeline import query
        questions = args.query if args.query else [
            "What was Microsoft's total revenue in 2025?",
            "What did Satya Nadella say about AI?",
            "How much did Azure revenue grow?",
        ]
        for q in questions:
            result = query(q)
            _print_answer(q, result)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
