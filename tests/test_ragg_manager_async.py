
import aiohttp
import pytest
from aioresponses import aioresponses

from app.ragg_manager import RAGManager


@pytest.mark.asyncio
async def test_ragg_manager_search_and_answer(tmp_path):
    # Prepare a fake client config
    cfg = {
        "search_endpoint": "https://fake-search.search.windows.net",
        "search_api_key": "fake-search-key",
        "index_name": "test-index",
        "openai_endpoint": "https://fake-openai.openai.azure.com",
        "openai_api_key": "fake-openai-key",
        "deployment_name": "test-deploy",
        "embedding_deployment": "embed-deploy"
    }

    async with aiohttp.ClientSession() as session:
        mgr = RAGManager(cfg, session=session)

        # Mock embedding endpoint
        embed_url = (
            f"{cfg['openai_endpoint']}/openai/deployments/"
            f"{cfg['embedding_deployment']}/embeddings?api-version=2024-02-15-preview"
        )
        search_url = (
            f"{cfg['search_endpoint']}/indexes/{cfg['index_name']}/docs/search?"
            f"api-version=2023-11-01"
        )
        chat_url = (
            f"{cfg['openai_endpoint']}/openai/deployments/"
            f"{cfg['deployment_name']}/chat/completions?api-version=2024-02-15-preview"
        )

        with aioresponses() as m:
            m.post(embed_url, payload={"data": [{"embedding": [0.1, 0.2, 0.3]}]})
            m.post(search_url, payload={"value": [{"content": "doc1"}, {"content": "doc2"}]})
            m.post(chat_url, payload={"choices": [{"message": {"content": "answered text"}}]})

            ans, sources = await mgr.answer_query("hello world")
            assert ans == "answered text"
            assert isinstance(sources, list)
            assert "doc1" in sources
