from typing import List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str


class RAGResponse(BaseModel):
    answer: str
    sources: Optional[List[str]] = None
    elapsed_ms: Optional[int] = None
