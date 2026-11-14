"""Request-local console log context, including synchronous endpoint workers."""

import logging
from contextvars import ContextVar
from typing import Any, Mapping

from server_browser_backend.ip_address import canonical_address

request_scope: ContextVar[Mapping[str, Any] | None] = ContextVar(
    "request_log_scope", default=None
)


def requestor_ip(scope: Mapping[str, Any] | None) -> str:
    client = scope.get("client") if scope is not None else None
    return normalize_ip(client[0] if client else "")


def normalize_ip(address: str) -> str:
    try:
        return str(canonical_address(address))
    except ValueError:
        return "-"


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        scope = request_scope.get()
        record.requestor_ip = requestor_ip(scope)
        if scope is None and record.exc_info:
            record.requestor_ip = getattr(record.exc_info[1], "_request_log_ip", "-")
        elif (
            scope is None
            and record.name == "uvicorn.access"
            and record.msg == '%s - "%s %s HTTP/%s" %d'
            and isinstance(record.args, tuple)
            and len(record.args) == 5
            and isinstance(record.args[0], str)
        ):
            # Uvicorn may send its fallback 500 after the ASGI context is reset.
            address = record.args[0].rpartition(":")[0]
            record.requestor_ip = normalize_ip(address)
        return super().format(record)
