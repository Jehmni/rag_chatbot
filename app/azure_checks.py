import asyncio
import os
from typing import Any, Dict


async def validate_azure_endpoints(clients_config: Dict[str, Any], session) -> Dict[str, bool]:
    """Validate configured Azure endpoints for each client.

    Returns a dict mapping client_id -> bool indicating success.
    This is intentionally best-effort: failures are reported but don't always
    stop startup unless running in production.
    """
    results = {}
    timeout = float(os.getenv("AZURE_CHECK_TIMEOUT", "5"))

    async def _check_client(cid: str, cfg: Dict[str, Any]):
        try:
            openai_endpoint = cfg.get("openai_endpoint")
            if openai_endpoint:
                # simple HEAD/GET to root or health-like path to validate connectivity
                try:
                    async with session.get(openai_endpoint, timeout=timeout) as resp:
                        return resp.status == 200 or resp.status == 401 or resp.status == 403
                except Exception:
                    return False
            return False
        except Exception:
            return False

    tasks = [
        asyncio.create_task(_check_client(cid, cfg)) for cid, cfg in clients_config.items()
    ]

    for cid, task in zip(clients_config.keys(), tasks):
        try:
            results[cid] = bool(await task)
        except Exception:
            results[cid] = False

    return results
