# AI-agents-Weekend

Foresight-X implementation. Specifications: `foresight_x_product_spec.md`, `foresight_x_technical_architecture.md`.

## Setup

```bash
pip install -e ".[dev]"
pytest
```

Requires Python 3.11+. Stack: **LlamaIndex** (orchestration + RAG), **Chroma**, **Tavily**, **OpenAI API** (chat + embeddings). Copy `.env.example` to `.env` and set `OPENAI_API_KEY` and `TAVILY_API_KEY`.
