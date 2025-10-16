import asyncio
from typing import List, Optional, Tuple

import aiohttp
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

# Import trim helper at module load to avoid dynamic imports on hot paths


class RAGError(Exception):
    """Custom exception for RAG pipeline errors."""
    pass


class RAGManager:
    def __init__(
        self,
        client_config: dict,
        session: aiohttp.ClientSession,
        *,
        embedding_deployment: Optional[str] = None,
        # allow per-client or global overrides
        embedding_timeout: int = 15,
        search_timeout: int = 20,
        chat_timeout: int = 30,
        retry_attempts: int = 3,
        retry_min_wait: int = 1,
        retry_max_wait: int = 8,
    ):
        self.search_endpoint = client_config.get("search_endpoint")
        self.search_api_key = client_config.get("search_api_key")
        self.index_name = client_config.get("index_name")

        self.openai_endpoint = client_config.get("openai_endpoint")
        self.openai_api_key = client_config.get("openai_api_key")
        self.deployment_name = client_config.get("deployment_name")

        # optional: embedding deployment name can differ from chat deployment
        self.embedding_deployment = (
            embedding_deployment
            or client_config.get("embedding_deployment")
            or self.deployment_name
        )

        # shared aiohttp session provided by the app
        self._session = session

        # timeouts and retry policy (can be overridden per client)
        self.embedding_timeout = int(client_config.get("embedding_timeout", embedding_timeout))
        self.search_timeout = int(client_config.get("search_timeout", search_timeout))
        self.chat_timeout = int(client_config.get("chat_timeout", chat_timeout))
        self.retry_attempts = int(client_config.get("retry_attempts", retry_attempts))
        self.retry_min_wait = int(client_config.get("retry_min_wait", retry_min_wait))
        self.retry_max_wait = int(client_config.get("retry_max_wait", retry_max_wait))

        # central tenacity retry factory for use in coroutines
        def _make_retry():
            return AsyncRetrying(
                retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError, RAGError)),
                wait=wait_exponential(min=self.retry_min_wait, max=self.retry_max_wait),
                stop=stop_after_attempt(self.retry_attempts),
            )

        self._retry_factory = _make_retry

    async def generate_embedding(self, query: str) -> List[float]:
        """Generate embeddings using Azure OpenAI embeddings endpoint (REST)."""
        url = (
            f"{self.openai_endpoint}/openai/deployments/"
            f"{self.embedding_deployment}/embeddings?api-version=2024-02-15-preview"
        )
        headers = {"Content-Type": "application/json", "api-key": self.openai_api_key}
        payload = {"input": query}

        async for attempt in self._retry_factory():
            with attempt:
                try:
                    async with self._session.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.embedding_timeout),
                    ) as resp:
                        text = await resp.text()
                        if resp.status != 200:
                            raise RAGError(f"Embedding failed ({resp.status}): {text}")
                        data = await resp.json()
                        return data["data"][0]["embedding"]
                except asyncio.TimeoutError as err:
                    raise RAGError("Embedding generation timed out.") from err
                except aiohttp.ClientError as err:
                    raise RAGError(f"Embedding request failed: {err}") from err

    async def search_documents(self, query: str, k: int = 5) -> List[str]:
        """Perform vector search on Azure Cognitive Search using the generated embedding."""
        embedding = await self.generate_embedding(query)

        url = (
            f"{self.search_endpoint}/indexes/{self.index_name}/docs/search?"
            f"api-version=2023-11-01"
        )
        headers = {"Content-Type": "application/json", "api-key": self.search_api_key}
        payload = {
            "vector": {
                "value": embedding,
                "fields": "contentVector",
                "k": k,
            },
            "select": "content",
        }

        async for attempt in self._retry_factory():
            with attempt:
                try:
                    async with self._session.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.search_timeout),
                    ) as resp:
                        text = await resp.text()
                        if resp.status != 200:
                            raise RAGError(f"Search failed ({resp.status}): {text}")
                        results = await resp.json()
                        docs = [doc.get("content", "") for doc in results.get("value", [])]
                        return docs
                except asyncio.TimeoutError as err:
                    raise RAGError("Search request timed out.") from err
                except aiohttp.ClientError as err:
                    raise RAGError(f"Search request failed: {err}") from err

    async def generate_answer(self, query: str, context: str, max_tokens: int = 400) -> str:
        """Generate final AI answer using Azure OpenAI chat completions (REST). Returns content string."""
        url = (
            f"{self.openai_endpoint}/openai/deployments/"
            f"{self.deployment_name}/chat/completions?api-version=2024-02-15-preview"
        )
        headers = {"Content-Type": "application/json", "api-key": self.openai_api_key}

        # Trim context to token limit using helper (tiktoken optional)
        try:
            # default token budget: reserve tokens for prompt + answer
            utils_mod = __import__('app.utils', fromlist=['trim_to_token_limit'])
            context = utils_mod.trim_to_token_limit(
                context, max_tokens=3000
            )
        except Exception:
            # fallback to naive char trim
            if len(context) > 7000:
                context = context[-7000:]

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that answers based on context."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {query}",
            },
        ]

        payload = {
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }

        async for attempt in self._retry_factory():
            with attempt:
                try:
                    async with self._session.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=self.chat_timeout),
                    ) as resp:
                        text = await resp.text()
                        if resp.status != 200:
                            raise RAGError(f"Chat generation failed ({resp.status}): {text}")
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
                except asyncio.TimeoutError as err:
                    raise RAGError("Chat generation timed out.") from err
                except aiohttp.ClientError as err:
                    raise RAGError(f"Chat request failed: {err}") from err

    async def answer_query(self, query: str) -> Tuple[str, List[str]]:
        """Full RAG pipeline: search -> generate answer. Returns (answer, sources)."""
        docs = await self.search_documents(query)
        context = "\n\n".join(docs) if docs else "No relevant documents found."
        answer = await self.generate_answer(query, context)
        return answer, docs

    async def close(self):
        """If manager manages resources, close them. Currently a no-op."""
        return
