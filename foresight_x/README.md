# Foresight-X package

Python package implementing the RIS pipeline and Harness. See repository root specs:

- `foresight_x_product_spec.md`
- `foresight_x_technical_architecture.md`

## Install (development)

```bash
pip install -e ".[dev]"
pytest
```

Phase 0 delivers `schemas` and `config` with contract tests under `tests/`.

Phase 1 delivers `retrieval/`: `UserMemory` and `WorldKnowledge` (Chroma + LlamaIndex), `TavilyGateway`, packaged seeds under `retrieval/seeds/`, and tests (`test_memory`, `test_world_cache`, `test_tavily_client`, `test_seed`).

Phase 6 adds UI entry points:

- CLI run: `python -m foresight_x.ui.cli "I got an offer from Company X..."`
- Outcome capture: `python -m foresight_x.ui.cli --record-outcome <decision_id>`
- Streamlit app: `streamlit run foresight_x/ui/app.py`

### Web UI (`web/` — Vite + React)

Requires Python extras **`web`** (FastAPI + Uvicorn) and Node/npm.

1. Install backend: `pip install -e ".[web]"`
2. Start API:

   ```bash
   uvicorn foresight_x.ui.api_server:app --host 127.0.0.1 --port 8765
   ```

3. Frontend (dev server proxies `/api` → port 8765):

   ```bash
   cd web
   npm install
   npm run dev
   ```

4. Open the URL Vite prints (usually `http://localhost:5173`). Use repo-root `.env` for `OPENAI_API_KEY` / `TAVILY_API_KEY` (same as CLI).

Production: `cd web && npm run build` — output in `web/dist/` (serve static files + run the API separately).
