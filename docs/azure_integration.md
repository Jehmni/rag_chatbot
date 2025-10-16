# Azure Integration Guide

This document shows minimal example code and recommended environment layout to connect the FastAPI RAG backend to Azure Cognitive Search and Azure OpenAI.

Security-first
- Do NOT store raw secrets in `clients.json` in source control.
- Instead store env var names in `clients.json` (e.g. `openai_api_key_env`) and resolve them at startup using `app.config.load_clients()`.
- For production, use Azure Key Vault or platform secrets (Azure App Settings) and reference them via environment variables.

Recommended environment variables (per client)
- <CLIENT>_SEARCH_KEY: Azure Cognitive Search admin/query API key for the client's index
- <CLIENT>_OPENAI_KEY: Azure OpenAI key (or managed identity token)
- Example names used in the repo: `EX_CLIENT_SEARCH_KEY`, `EX_CLIENT_OPENAI_KEY`

clients.json pattern
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

Python (aiohttp) - Embeddings (REST)
```py
import aiohttp

async def get_embedding(openai_endpoint, api_key, deployment, text):
    url = f"{openai_endpoint}/openai/deployments/{deployment}/embeddings?api-version=2024-02-15-preview"
    headers = {"Content-Type": "application/json", "api-key": api_key}
    payload = {"input": text}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, headers=headers, json=payload, timeout=15) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["data"][0]["embedding"]
```

Azure Cognitive Search - Vector search (REST)
- Endpoint: `https://{search_service}.search.windows.net/indexes/{index}/docs/search?api-version=2023-11-01`
- Payload example (vector search):
```json
{
  "vector": { "value": [0.1,0.2,...], "fields": "contentVector", "k": 5 },
  "select": "content"
}
```

Python (aiohttp) - Search example
```py
async def vector_search(search_endpoint, api_key, index, embedding):
    url = f"{search_endpoint}/indexes/{index}/docs/search?api-version=2023-11-01"
    headers = {"Content-Type": "application/json", "api-key": api_key}
    payload = {"vector": {"value": embedding, "fields": "contentVector", "k": 5}, "select": "content"}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, headers=headers, json=payload, timeout=20) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return [d.get("content") for d in data.get("value", [])]
```

Python (aiohttp) - Chat completions (REST)
```py
async def chat_completion(openai_endpoint, api_key, deployment, messages):
    url = f"{openai_endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-02-15-preview"
    headers = {"Content-Type": "application/json", "api-key": api_key}
    payload = {"messages": messages, "max_tokens": 400, "temperature": 0.2}
    async with aiohttp.ClientSession() as s:
        async with s.post(url, headers=headers, json=payload, timeout=30) as resp:
            resp.raise_for_status()
            d = await resp.json()
            return d["choices"][0]["message"]["content"]
```

Notes and best practices
- Use retries + exponential backoff for network calls (we include `tenacity` in requirements and `ragg_manager` uses it).
- Prefer the official Azure SDK `azure-ai-openai` if you want typed clients and easier auth, but REST keeps the code dependency-light.
- Token accounting: use `tiktoken` where possible (optional) to trim context to token budgets. Our code falls back to a safe character-based trim if `tiktoken` isn't available.
- For production, prefer managed identities (MSI) or Key Vault instead of plain API keys.

Troubleshooting
- If you see 401/403 from Azure endpoints, verify the correct key and endpoint and ensure the deployment name is correct.
- If embeddings fail to build locally due to `tiktoken`, install Rust toolchain or skip optional deps and rely on character-based trimming.

