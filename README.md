# FastAPI Multi-Client RAG Backend

This repository contains a minimal FastAPI backend designed to serve multiple clients with a retrieval-augmented-generation (RAG) pipeline backed by Azure Cognitive Search and Azure OpenAI.

## Features
- Multi-client support via `app/clients.json` (resolved at startup)
- RAG pipeline: embeddings -> vector search -> chat completion
- Reuses a single `aiohttp.ClientSession` across requests
- Pydantic models and typed responses
- Startup/shutdown lifecycle to initialize managers and cleanup resources
- Basic retry/backoff using `tenacity`

## Setup
1. Create and activate a venv (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Configure client secrets using environment variables. Example `clients.json` expects env var names like `EX_CLIENT_OPENAI_KEY` and `EX_CLIENT_SEARCH_KEY`.

3. Run the app (dev):
```powershell
uvicorn app.main:app --reload --port 8000 --app-dir .\fastapi-backend
```

## Endpoints
- `GET /health` - basic health
- `GET /clients` - list configured clients
- `POST /chat/{client_id}` - chat endpoint (body: `{ "query": "..." }`)

## Azure integration notes
- `app/clients.json` should contain endpoint URLs and env var names for keys (avoid putting raw keys in source control).
- Example `clients.json` entry:
```json
{
  "example_client": {
    "index_name": "example_index",
    "search_endpoint": "https://<your-search>.search.windows.net",
    "search_api_key_env": "EX_CLIENT_SEARCH_KEY",
    "openai_endpoint": "https://<your-azure-openai>.openai.azure.com",
    "openai_api_key_env": "EX_CLIENT_OPENAI_KEY",
    "deployment_name": "gpt-4o-mini"
  }
}
```

## Next improvements
- Token-based trimming with `tiktoken` (partial support included)
- Add request-id middleware and structured logging context
- Add unit/integration tests (pytest + aioresponses)
- Consider using Azure Key Vault for secret management

## Maintainer notes
This is an iterative scaffold. If you'd like, I can:
- Add token trimming and exact tiktoken usage
- Add retries for specific failure types and circuit-breakers
- Replace REST calls with `azure-ai-openai` SDK usage

*** End of README ***
