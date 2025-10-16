import json

import requests
from openai import AzureOpenAI


def embed_text(text: str, client: AzureOpenAI) -> list:
    """Return embedding for `text` using provided AzureOpenAI client."""
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding


def upload_to_search(index_name: str, docs: list, search_endpoint: str, api_key: str) -> None:
    """Upload documents to Azure Cognitive Search index."""
    url = (
        f"{search_endpoint}/indexes/{index_name}/docs/index?"
        f"api-version=2023-11-01"
    )
    headers = {"Content-Type": "application/json", "api-key": api_key}
    payload = {"value": docs}
    requests.post(url, headers=headers, data=json.dumps(payload))


# NOTE: the following example was removed from module import-time execution. Use
# these helpers from a script or a test where configuration values are available.
