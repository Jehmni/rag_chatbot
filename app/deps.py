from fastapi import HTTPException, Request

from app.ragg_manager import RAGManager


async def get_rag_manager(request: Request, client_id: str) -> RAGManager:
    """Dependency that returns the RAGManager for a client or raises 404."""
    managers = getattr(request.app.state, "rag_managers", {})
    mgr = managers.get(client_id)
    if mgr is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return mgr
