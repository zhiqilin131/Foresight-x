# AI-agents-Weekend

Foresight-X implementation. Specifications: `foresight_x_product_spec.md`, `foresight_x_technical_architecture.md`.

## Setup

```bash
pip install -e ".[dev]"
pytest
```

Requires Python 3.11+. Stack: **LlamaIndex** (orchestration + RAG), **Chroma**, **Tavily** (web retrieval; tests mock the client), **OpenAI API** (chat + embeddings).

**Environment:** `cp .env.example .env`, then set at least `TAVILY_API_KEY` / `OPENAI_API_KEY` as needed. If `python -c "..."` raises `KeyError: 'TAVILY_API_KEY'`, you are missing `.env` or the variable inside it.

**Smoke test (Tavily):** run `pip install tavily-python` (or `pip install -e ".[dev]"`) in the **same** environment as `python`, then `python scripts/smoke_tavily.py`. If you see `No module named 'tavily'`, the Tavily SDK is not installed for that interpreter. The script does not load Chroma/LlamaIndex.

**Web UI:** React/Vite app in `web/` (API: `pip install -e ".[web]"` then `uvicorn foresight_x.ui.api_server:app --port 8765`; frontend: `cd web && npm install && npm run dev`). See `foresight_x/README.md`.
