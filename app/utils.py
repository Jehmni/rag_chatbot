import logging
from contextvars import ContextVar
from typing import Optional

from pythonjsonlogger import jsonlogger

# contextvar for request id so logging can include it automatically
REQUEST_ID: ContextVar[Optional[str]] = ContextVar("REQUEST_ID", default=None)


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rid = REQUEST_ID.get()
        except Exception:
            rid = None
        record.request_id = rid
        return True


def setup_json_logger(name: str = __name__):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.addFilter(RequestIDFilter())
    return logger


logger = setup_json_logger(__name__)


def trim_to_token_limit(text: str, max_tokens: int = 2048, model: str = "gpt-4o-mini") -> str:
    """Attempt to trim `text` to approximately `max_tokens` tokens.

    If `tiktoken` is available use it for accurate token counting, otherwise
    fall back to a conservative character-based estimate (approx 4 chars/token).
    """
    try:
        import tiktoken
        enc = tiktoken.encoding_for_model(model)
        toks = enc.encode(text)
        if len(toks) <= max_tokens:
            return text
        truncated = enc.decode(toks[-max_tokens:])
        return truncated
    except Exception:
        # fallback: naive character trim
        approx_chars = max_tokens * 4
        if len(text) <= approx_chars:
            return text
        return text[-approx_chars:]
