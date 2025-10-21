# Project architecture — FastAPI multi-client RAG backend

This file summarizes the repository layout and the role of each major file and folder. Copy or share this with others to explain the architecture.

Repository root
```
fastapi-backend/
├── .github/workflows/      # CI workflows (lint, typecheck, tests)
├── app/                    # Application code
│   ├── __init__.py
│   ├── main.py             # FastAPI app and lifespan startup/shutdown
│   ├── config.py           # Load clients.json, env & optional KeyVault resolution
│   ├── deps.py             # FastAPI dependency helpers (get_rag_manager, etc.)
│   ├── ragg_manager.py     # Per-client RAGManager: embeddings, search, chat
│   ├── index_builder.py    # Utilities to build/refresh search indexes (optional)
│   ├── azure_checks.py     # Optional startup validators for external endpoints
│   ├── utils.py            # Helpers: logging setup, token trimming, request timing
│   ├── models.py          # Pydantic request/response models
│   └── clients.json        # Per-client configuration (endpoints, keys, options)
├── tests/                  # Pytest unit + async tests (aioresponses, pytest-asyncio)
├── Dockerfile              # Container image build instructions
├── requirements.txt        # Runtime dependencies
├── requirements-dev.txt    # Dev/test dependencies (pytest, httpx, ruff, mypy)
├── requirements-optional.txt # Optional integrations (azure-identity, keyvault)
├── .env.example            # Example environment variables
├── README.md               # Project overview and quick start
└── ARCHITECTURE.md         # (this file)
```

High-level architecture

- FastAPI app: `app/main.py` uses an async lifespan to create a shared `aiohttp.ClientSession` and instantiate a cached `RAGManager` per client. RAGManagers are kept in `app.state.rag_managers` and are retrieved via DI helpers in `app/deps.py`.

- RAGManager: `app/ragg_manager.py` encapsulates the retrieval-augmented generation pipeline: embeddings -> vector search -> LLM chat completion. It centralizes retry/backoff, configurable timeouts, and token trimming utilities.

- Configuration: `app/clients.json` holds per-client settings (API endpoints, region, names). `app/config.py` loads clients, resolves env var references, and can optionally fetch secrets from Azure Key Vault when `AZURE_KEY_VAULT_URL` is set.

- Azure readiness: `app/azure_checks.py` contains optional startup checks that validate connectivity to external endpoints (e.g., Azure OpenAI / Cognitive Search). Startup validation is toggled via `AZURE_VALIDATE_ON_STARTUP` and is fatal in `DEPLOYMENT_ENV=prod`.

- Tests & CI: The project includes pytest tests (sync and async) that use TestClient and aioresponses. CI runs ruff, mypy, and pytest in GitHub Actions (`.github/workflows/ci.yml`).

Notes for sharing

- Per-client isolation: Each client gets its own RAGManager instance so credentials, endpoints, and per-client tuning (timeouts/retries) stay isolated.
- Optional Key Vault: Key Vault support is optional; `azure-identity` and `azure-keyvault-secrets` are listed in `requirements-optional.txt` and only used if `AZURE_KEY_VAULT_URL` is configured.
- Extensibility: The RAGManager is intentionally modular; you can swap in different embedding providers, search backends, or LLM endpoints per-client.

How to show someone quickly

1. Open `app/main.py` to show the FastAPI lifespan wiring and where RAGManagers are created.
2. Open `app/ragg_manager.py` to demonstrate the pipeline and retry/timeouts.
3. Open `app/clients.json` to show how multiple clients are configured.

Contact / further steps

If you'd like, I can generate a simple diagram (SVG or PNG) visualizing the request flow (client -> FastAPI -> RAGManager -> embeddings/search -> LLM). Tell me which format you prefer.
