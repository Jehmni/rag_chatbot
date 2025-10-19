import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import aiohttp
from fastapi import Depends, FastAPI, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.azure_checks import validate_azure_endpoints
from app.config import load_clients
from app.deps import get_rag_manager
from app.models import ChatRequest, RAGResponse
from app.ragg_manager import RAGError, RAGManager
from app.utils import logger

from openai import AzureOpenAI

# Optional: create a global Azure OpenAI client if you want it outside RAGManager
azure_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION")
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid4())
        request.state.request_id = request_id
        start = time.time()
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed = (time.time() - start) * 1000
            logger.info(
                "%s %s completed in %.1fms request_id=%s",
                request.method,
                request.url.path,
                elapsed,
                request_id,
            )


app = FastAPI(title="Multi-Client RAG Chatbot", lifespan=None)
app.add_middleware(RequestIDMiddleware)


@asynccontextmanager
async def lifespan(app: FastAPI):
    base = Path(__file__).parent
    clients_path = base / "clients.json"
    clients = load_clients(clients_path)

    # store configs and shared http session on the app state
    app.state.clients_config = clients
    app.state.http_session = aiohttp.ClientSession()
    app.state.rag_managers = {}

    # Load OpenAI config from environment
    openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

    if not (openai_endpoint and openai_api_key and deployment_name):
        raise RuntimeError(
            "OpenAI environment variables not set: "
            "AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME"
        )

    # instantiate a RAGManager per client
    for client_id, cfg in clients.items():
        # inject OpenAI info from environment
        cfg["openai_endpoint"] = openai_endpoint
        cfg["openai_api_key"] = openai_api_key
        cfg["deployment_name"] = deployment_name

        try:
            app.state.rag_managers[client_id] = RAGManager(cfg, session=app.state.http_session)
            logger.info("Initialized RAGManager for client=%s", client_id)
        except Exception:
            logger.exception("Failed to initialize RAGManager for client=%s", client_id)

    # Optional: validate Azure connectivity at startup
    try:
        if os.getenv("AZURE_VALIDATE_ON_STARTUP", "false").lower() in ("1", "true", "yes"):
            logger.info("Running Azure connectivity validation on startup")
            results = await validate_azure_endpoints(clients, app.state.http_session)
            logger.info("Azure validation results: %s", results)
            if os.getenv("DEPLOYMENT_ENV", "dev").lower() == "prod":
                failed = [k for k, ok in results.items() if not ok]
                if failed:
                    raise RuntimeError(f"Azure validation failed for clients: {failed}")
    except Exception:
        logger.exception("Azure validation encountered an error during startup")
        if os.getenv("DEPLOYMENT_ENV", "dev").lower() == "prod":
            raise

    try:
        yield
    finally:
        rag_managers = getattr(app.state, "rag_managers", {})
        for cid, mgr in rag_managers.items():
            close = getattr(mgr, "close", None)
            if close:
                try:
                    await close()
                except Exception:
                    logger.exception("Error closing RAGManager for %s", cid)

        session = getattr(app.state, "http_session", None)
        if session is not None:
            try:
                await session.close()
            except Exception:
                logger.exception("Error closing http session")


app.router.lifespan_context = lifespan


@app.get("/health")
async def health_check():
    """Simple uptime/health endpoint"""
    return {"status": "ok", "message": "Backend is running"}


@app.get("/clients")
async def list_clients():
    """List all configured clients"""
    clients = getattr(app.state, "clients_config", {})
    return {"clients": list(clients.keys())}


@app.post("/chat/{client_id}", response_model=RAGResponse)
async def chat_with_client(
    client_id: str,
    body: ChatRequest,
    rag: RAGManager = Depends(get_rag_manager),  # noqa: B008 (FastAPI Depends in signature)
):
    """Main chat route — runs RAG pipeline for selected client."""
    start = time.time()
    try:
        answer, sources = await rag.answer_query(body.query)
        elapsed_ms = int((time.time() - start) * 1000)
        return RAGResponse(answer=answer, sources=sources, elapsed_ms=elapsed_ms)
    except RAGError as re:
        logger.exception("RAG error for client=%s: %s", client_id, re)
        raise HTTPException(status_code=502, detail=str(re)) from re
    except Exception:
        logger.exception("Unexpected error in chat for client=%s", client_id)
        raise HTTPException(status_code=500, detail="Internal server error") from None
