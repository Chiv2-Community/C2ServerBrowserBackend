"""Request-local console log context, including synchronous endpoint workers."""

import logging
from contextvars import ContextVar
from ipaddress import ip_address
from typing import Any, Mapping

request_scope: ContextVar[Mapping[str, Any] | None] = ContextVar(
    "request_log_scope", default=None
)


class ConsoleFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        scope = request_scope.get()
        client = scope.get("client") if scope is not None else None
        try:
            record.requestor_ip = str(ip_address(client[0])) if client else "-"
        except ValueError:
            record.requestor_ip = "-"
        return super().format(record)
